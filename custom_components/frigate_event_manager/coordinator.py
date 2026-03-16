"""DataUpdateCoordinator MQTT pour Frigate Event Manager — push uniquement."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

from homeassistant.components import mqtt
from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import CONF_CAMERA, CONF_NOTIFY_TARGET, DEFAULT_MQTT_TOPIC, DOMAIN

_LOGGER = logging.getLogger(__name__)


@dataclass
class FrigateEvent:
    """Représentation d'un événement Frigate parsé depuis le payload MQTT."""

    type: str           # "new" | "update" | "end"
    camera: str
    severity: str       # "alert" | "detection"
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
    last_event_time: float | None = None
    motion: bool = False    # True sur type=new, False sur type=end
    enabled: bool = True    # contrôle notifications (switch HA)

    def as_dict(self) -> dict[str, Any]:
        """Sérialise l'état en dict pour coordinator.data."""
        return {
            "name": self.name,
            "last_severity": self.last_severity,
            "last_objects": self.last_objects,
            "last_event_time": self.last_event_time,
            "motion": self.motion,
            "enabled": self.enabled,
        }


def _to_float(value: Any, *, default: float | None) -> float | None:
    """Convertit une valeur en float de manière sécurisée."""
    if value is None:
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def _parse_event(payload: str) -> FrigateEvent | None:
    """Parse un payload MQTT Frigate JSON → FrigateEvent."""
    try:
        raw: dict[str, Any] = json.loads(payload)
    except (json.JSONDecodeError, TypeError) as err:
        _LOGGER.warning("Payload MQTT non-JSON ignoré : %s", err)
        return None

    if not isinstance(raw, dict):
        return None

    event_type = raw.get("type")
    if event_type not in ("new", "update", "end"):
        return None

    after: dict[str, Any] = raw.get("after") or raw.get("before") or {}
    camera = after.get("camera") or raw.get("camera")
    if not camera:
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


class FrigateEventManagerCoordinator(DataUpdateCoordinator[dict]):
    """Coordinator MQTT — push uniquement, par caméra (subentry)."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        subentry: ConfigSubentry,
    ) -> None:
        """Initialise le coordinator pour une caméra donnée."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{subentry.data[CONF_CAMERA]}",
            update_interval=None,
            config_entry=entry,
        )
        self._camera: str = subentry.data[CONF_CAMERA]
        self._camera_state = CameraState(name=self._camera)
        self._unsubscribe_mqtt: Any = None

        from .notifier import HANotifier  # noqa: PLC0415
        from .throttle import Throttler  # noqa: PLC0415

        # notify_target : subentry en priorité, sinon config entry globale
        notify_target = (
            subentry.data.get(CONF_NOTIFY_TARGET)
            or entry.data.get(CONF_NOTIFY_TARGET)
        )
        self._notifier: Any = HANotifier(hass, notify_target) if notify_target else None
        self._throttler = Throttler()

    @property
    def camera(self) -> str:
        """Nom de la caméra gérée par ce coordinator."""
        return self._camera

    @property
    def camera_state(self) -> CameraState:
        """Accès direct au CameraState."""
        return self._camera_state

    def set_camera_enabled(self, enabled: bool) -> None:
        """Active ou désactive les notifications pour cette caméra."""
        self._camera_state.enabled = enabled
        self.async_set_updated_data(self._camera_state.as_dict())

    async def async_start(self) -> None:
        """Souscrit au topic MQTT Frigate."""
        self._unsubscribe_mqtt = await mqtt.async_subscribe(
            self.hass,
            DEFAULT_MQTT_TOPIC,
            self._handle_mqtt_message,
        )
        _LOGGER.info("Souscrit MQTT — caméra=%s topic=%s", self._camera, DEFAULT_MQTT_TOPIC)

    async def async_stop(self) -> None:
        """Désabonnement MQTT."""
        if self._unsubscribe_mqtt is not None:
            self._unsubscribe_mqtt()
            self._unsubscribe_mqtt = None
            _LOGGER.debug("Désabonné MQTT — caméra=%s", self._camera)

    @callback
    def _handle_mqtt_message(self, message: Any) -> None:
        """Callback MQTT — parse, filtre par caméra, met à jour l'état, notifie."""
        event = _parse_event(message.payload)
        if event is None or event.camera != self._camera:
            return

        state = self._camera_state

        if event.type in ("new", "update"):
            state.last_severity = event.severity
            state.last_objects = event.objects
            state.last_event_time = event.start_time
            if event.type == "new":
                state.motion = True
        elif event.type == "end":
            state.motion = False
            state.last_event_time = event.end_time or event.start_time

        _LOGGER.debug(
            "Événement traité — caméra=%s type=%s sévérité=%s objets=%s",
            event.camera, event.type, event.severity, event.objects,
        )

        if (
            event.type == "new"
            and state.enabled
            and self._notifier is not None
            and self._throttler.should_notify(self._camera)
        ):
            self.hass.async_create_task(self._notifier.async_notify(event))
            self._throttler.record(self._camera)

        self.async_set_updated_data(state.as_dict())

    async def _async_update_data(self) -> dict:
        """Non utilisé — coordinator en mode push MQTT uniquement."""
        return self.data or {}
