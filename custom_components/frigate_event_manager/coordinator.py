"""DataUpdateCoordinator MQTT pour Frigate Event Manager.

Souscrit au topic Frigate via MQTT natif HA et maintient l'état
d'une caméra unique. Pas de polling — push uniquement.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

from homeassistant.components import mqtt
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import CONF_CAMERA, CONF_NOTIFY_TARGET, DEFAULT_MQTT_TOPIC, DOMAIN

_LOGGER = logging.getLogger(__name__)


@dataclass
class FrigateEvent:
    """Représentation d'un événement Frigate parsé depuis le payload MQTT."""

    type: str          # "new" | "update" | "end"
    camera: str
    severity: str      # "alert" | "detection"
    objects: list[str] = field(default_factory=list)
    zones: list[str] = field(default_factory=list)
    score: float = 0.0
    thumb_path: str = ""
    review_id: str = ""
    start_time: float = 0.0
    end_time: float | None = None


@dataclass
class CameraState:
    """État courant d'une caméra, mis à jour à chaque événement Frigate."""

    name: str
    last_severity: str | None = None
    last_objects: list[str] = field(default_factory=list)
    event_count_24h: int = 0
    last_event_time: float | None = None
    motion: bool = False        # True sur type=new, False sur type=end
    enabled: bool = True        # contrôle notifications (switch HA)

    def as_dict(self) -> dict[str, Any]:
        """Sérialise l'état en dict pour coordinator.data."""
        return {
            "name": self.name,
            "last_severity": self.last_severity,
            "last_objects": self.last_objects,
            "event_count_24h": self.event_count_24h,
            "last_event_time": self.last_event_time,
            "motion": self.motion,
            "enabled": self.enabled,
        }


def _to_float(value: Any, *, default: float | None) -> float | None:
    """Convertit une valeur en float de manière sécurisée.

    Retourne `default` si la valeur est None, falsy, ou non-numérique.
    Protège contre les strings non-numériques comme 'N/A'.
    """
    if value is None:
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def _parse_event(payload: str) -> FrigateEvent | None:
    """Parse un payload MQTT Frigate JSON → FrigateEvent.

    Retourne None si le payload est invalide ou manque de champs obligatoires.
    Les champs optionnels sont ignorés silencieusement.
    """
    try:
        raw: dict[str, Any] = json.loads(payload)
    except (json.JSONDecodeError, TypeError) as err:
        _LOGGER.warning("Payload MQTT non-JSON ignoré : %s", err)
        return None

    if not isinstance(raw, dict):
        _LOGGER.warning("Payload MQTT ignoré : dict attendu, reçu %s", type(raw).__name__)
        return None

    # Validation des champs obligatoires
    event_type = raw.get("type")
    if event_type not in ("new", "update", "end"):
        _LOGGER.warning("Champ 'type' manquant ou invalide dans le payload Frigate : %r", event_type)
        return None

    # Frigate encapsule les données dans une clé "after" (ou "before")
    after: dict[str, Any] = raw.get("after") or raw.get("before") or {}
    camera = after.get("camera") or raw.get("camera")
    if not camera:
        _LOGGER.warning("Champ 'camera' introuvable dans le payload Frigate")
        return None

    return FrigateEvent(
        type=event_type,
        camera=str(camera),
        severity=str(after.get("severity") or raw.get("severity") or "detection"),
        objects=list(after.get("objects") or raw.get("objects") or []),
        zones=list(after.get("current_zones") or raw.get("zones") or []),
        score=_to_float(
            after.get("score") if after.get("score") is not None else raw.get("score"),
            default=0.0,
        ),
        thumb_path=str(after.get("thumb_path") or raw.get("thumb_path") or ""),
        review_id=str(after.get("id") or raw.get("review_id") or ""),
        start_time=_to_float(
            after.get("start_time") if after.get("start_time") is not None else raw.get("start_time"),
            default=0.0,
        ),
        end_time=_to_float(
            after.get("end_time") if after.get("end_time") is not None else raw.get("end_time"),
            default=None,
        ),
    )


def _resolve_notify_target(hass: HomeAssistant, entry: ConfigEntry) -> str | None:
    """Résout le notify_target pour une config entry caméra.

    Priorité :
    1. entry.data["notify_target"] si non-None
    2. notify_target de l'entrée globale (unique_id == DOMAIN)
    3. None si aucun trouvé
    """
    local = entry.data.get(CONF_NOTIFY_TARGET)
    if local:
        return local

    global_entry = hass.config_entries.async_entry_for_domain_unique_id(DOMAIN, DOMAIN)
    if global_entry is not None:
        return global_entry.data.get(CONF_NOTIFY_TARGET)

    return None


class FrigateEventManagerCoordinator(DataUpdateCoordinator[dict]):
    """Coordinator MQTT — push uniquement, pas de polling.

    S'abonne au topic Frigate via MQTT natif HA.
    Gère une seule caméra (entry.data["camera"]).
    Maintient un CameraState exposé via coordinator.data comme dict.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
    ) -> None:
        """Initialise le coordinator sans intervalle de polling."""
        if CONF_CAMERA not in entry.data:
            raise ValueError(f"Config entry {entry.entry_id} n'a pas de clé '{CONF_CAMERA}'")
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{entry.data[CONF_CAMERA]}",
            update_interval=None,  # MQTT push — aucun polling
        )
        self._entry = entry
        self._camera: str = entry.data[CONF_CAMERA]
        self._mqtt_topic: str = DEFAULT_MQTT_TOPIC
        self._camera_state = CameraState(name=self._camera)
        self._unsubscribe_mqtt: Any = None

        # Imports locaux pour éviter les imports circulaires
        # (filter.py et notifier.py importent FrigateEvent depuis coordinator.py)
        from .filter import FilterChain, LabelFilter, TimeFilter, ZoneFilter  # noqa: PLC0415
        from .notifier import HANotifier  # noqa: PLC0415
        from .throttle import Throttler  # noqa: PLC0415

        # Filtres désactivés par défaut (liste vide = tout accepter — T-512 via options flow)
        self._filter_chain = FilterChain([
            ZoneFilter(zone_multi=[]),
            LabelFilter(labels=[]),
            TimeFilter(disabled_hours=[]),
        ])
        self._throttler = Throttler()

        # Résolution du notify_target avec fallback sur l'entrée globale
        notify_target = _resolve_notify_target(hass, entry)
        if notify_target is None:
            _LOGGER.warning(
                "Coordinator caméra '%s' : notify_target absent — les notifications seront désactivées.",
                self._camera,
            )
        self._notifier: Any = (
            HANotifier(hass, notify_target) if notify_target else None
        )

    @property
    def camera(self) -> str:
        """Nom de la caméra gérée par ce coordinator."""
        return self._camera

    @property
    def camera_state(self) -> CameraState:
        """Accès direct au CameraState de la caméra."""
        return self._camera_state

    def set_camera_enabled(self, enabled: bool) -> None:
        """Active ou désactive les notifications pour la caméra.

        Notifie les listeners HA après la mise à jour.
        """
        self._camera_state.enabled = enabled
        self.async_set_updated_data(self._camera_state.as_dict())

    async def async_start(self) -> None:
        """Souscrit au topic MQTT Frigate.

        Appelé depuis async_setup_entry après l'enregistrement du coordinator.
        La reconnexion MQTT est gérée nativement par HA, pas besoin de retry.
        """
        self._unsubscribe_mqtt = await mqtt.async_subscribe(
            self.hass,
            self._mqtt_topic,
            self._handle_mqtt_message,
        )
        _LOGGER.info(
            "Coordinator Frigate Event Manager souscrit au topic MQTT : %s (caméra : %s)",
            self._mqtt_topic,
            self._camera,
        )

    async def async_stop(self) -> None:
        """Désabonnement MQTT — appelé depuis async_unload_entry."""
        if self._unsubscribe_mqtt is not None:
            self._unsubscribe_mqtt()
            self._unsubscribe_mqtt = None
            _LOGGER.debug(
                "Coordinator Frigate Event Manager désabonné de MQTT (caméra : %s)",
                self._camera,
            )

    @callback
    def _handle_mqtt_message(self, message: Any) -> None:
        """Callback MQTT — appelé dans la boucle asyncio HA.

        Parse le payload, filtre par nom de caméra, met à jour l'état,
        envoie une notification si autorisé, puis notifie les entités HA.
        """
        event = _parse_event(message.payload)
        if event is None:
            # Payload invalide déjà loggé dans _parse_event
            return

        # Filtrage par caméra — ignorer les événements des autres caméras
        if event.camera != self._camera:
            return

        state = self._camera_state

        # Mise à jour de l'état selon le type d'événement
        if event.type in ("new", "update"):
            state.last_severity = event.severity
            state.last_objects = event.objects
            state.last_event_time = event.start_time
            if event.type == "new":
                state.motion = True
                state.event_count_24h += 1
        elif event.type == "end":
            state.motion = False
            state.last_event_time = event.end_time or event.start_time

        _LOGGER.debug(
            "Événement Frigate traité — caméra=%s type=%s sévérité=%s objets=%s",
            event.camera,
            event.type,
            event.severity,
            event.objects,
        )

        # Envoi de notification si activé, filtres passés, throttle OK
        if (
            event.type == "new"
            and state.enabled
            and self._notifier is not None
            and self._filter_chain.apply(event)
            and self._throttler.should_notify(self._camera)
        ):
            self.hass.async_create_task(
                self._notifier.async_notify(event)
            )
            self._throttler.record(self._camera)

        # Notifie les entités HA avec les données fraîches
        self.async_set_updated_data(state.as_dict())

    async def _async_update_data(self) -> dict:
        """Non utilisé — le coordinator est en mode push MQTT uniquement."""
        return self.data or {}
