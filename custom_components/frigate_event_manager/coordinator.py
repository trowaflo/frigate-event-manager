"""DataUpdateCoordinator MQTT pour Frigate Event Manager — push uniquement."""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import replace
from typing import Any

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    CONF_CAMERA,
    CONF_COOLDOWN,
    CONF_DEBOUNCE,
    CONF_DISABLED_HOURS,
    CONF_LABELS,
    CONF_SILENT_DURATION,
    CONF_ZONES,
    DEFAULT_DEBOUNCE,
    DEFAULT_MQTT_TOPIC,
    DEFAULT_SILENT_DURATION,
    DEFAULT_THROTTLE_COOLDOWN,
    DOMAIN,
)
from .domain.filter import FilterChain, LabelFilter, TimeFilter, ZoneFilter
from .domain.model import CameraState, _parse_event
from .domain.ports import EventSourcePort, NotifierPort
from .domain.throttle import Throttler

_LOGGER = logging.getLogger(__name__)


class FrigateEventManagerCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator MQTT — push uniquement, par caméra (subentry)."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        subentry: ConfigSubentry,
        *,
        notifier: NotifierPort | None = None,
        event_source: EventSourcePort,
    ) -> None:
        """Initialise le coordinator pour une caméra donnée.

        event_source doit être injecté : HaMqttAdapter en production, fake en tests.
        """
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
        self._notifier: NotifierPort | None = notifier
        self._event_source: EventSourcePort = event_source
        self._throttler = Throttler(
            cooldown=subentry.data.get(CONF_COOLDOWN, DEFAULT_THROTTLE_COOLDOWN)
        )
        zones = subentry.data.get(CONF_ZONES, [])
        labels = subentry.data.get(CONF_LABELS, [])
        disabled_hours = subentry.data.get(CONF_DISABLED_HOURS, [])
        self._filter_chain = FilterChain([
            ZoneFilter(zones),
            LabelFilter(labels),
            TimeFilter(disabled_hours),
        ])

        # Debounce
        self._debounce_seconds: int = subentry.data.get(CONF_DEBOUNCE, DEFAULT_DEBOUNCE)
        self._debounce_task: asyncio.Task | None = None
        self._pending_objects: set[str] = set()
        self._pending_event: Any = None  # FrigateEvent dernier reçu

        # Tracker des reviews actifs — pour éviter motion=False prématuré si multi-events
        self._active_reviews: set[str] = set()

        # Silent mode
        self._silent_duration: int = subentry.data.get(CONF_SILENT_DURATION, DEFAULT_SILENT_DURATION)
        self._silent_until: float = 0.0
        self._cancel_silent: Any = None
        # Persistance du silent mode via HA Store — survie au redémarrage
        self._store: Store = Store(
            hass,
            1,
            f"frigate_event_manager_{self._camera}",
        )

    @property
    def camera(self) -> str:
        """Nom de la caméra gérée par ce coordinator."""
        return self._camera

    @property
    def camera_state(self) -> CameraState:
        """Accès direct au CameraState."""
        return self._camera_state

    @property
    def silent_until(self) -> float:
        """Timestamp de fin du mode silencieux (0.0 si inactif)."""
        return self._silent_until

    def set_camera_enabled(self, enabled: bool) -> None:
        """Active ou désactive les notifications pour cette caméra."""
        self._camera_state.enabled = enabled
        self.async_set_updated_data(self._camera_state.as_dict())

    def _on_silent_expired(self, _: Any) -> None:
        """Réinitialise le mode silencieux après expiration du timer."""
        self._silent_until = 0.0
        self._cancel_silent = None
        self.hass.async_create_task(self._store.async_save({"silent_until": 0.0}))
        self.async_set_updated_data(self._camera_state.as_dict())

    def activate_silent_mode(self) -> None:
        """Active le mode silencieux pour la durée configurée."""
        if self._cancel_silent is not None:
            self._cancel_silent()
        self._silent_until = time.time() + self._silent_duration * 60

        self._cancel_silent = async_call_later(
            self.hass,
            self._silent_duration * 60,
            self._on_silent_expired,
        )
        # Persister la valeur pour survivre à un redémarrage HA
        self.hass.async_create_task(
            self._store.async_save({"silent_until": self._silent_until})
        )
        self.async_set_updated_data(self._camera_state.as_dict())
        _LOGGER.info(
            "Mode silencieux activé — caméra=%s durée=%d min",
            self._camera,
            self._silent_duration,
        )

    async def async_start(self) -> None:
        """Souscrit au topic MQTT Frigate via l'adaptateur injecté."""
        self._unsubscribe_mqtt = await self._event_source.async_subscribe(
            DEFAULT_MQTT_TOPIC,
            self._handle_mqtt_message,
        )
        _LOGGER.info("Souscrit MQTT — caméra=%s topic=%s", self._camera, DEFAULT_MQTT_TOPIC)

        # Restaurer le mode silencieux depuis le Store si encore actif
        stored = await self._store.async_load() or {}
        silent_until = float(stored.get("silent_until", 0.0))
        if silent_until > time.time():
            self._silent_until = silent_until
            remaining = silent_until - time.time()
            _LOGGER.info(
                "Mode silencieux restauré — caméra=%s restant=%.0fs",
                self._camera,
                remaining,
            )

            self._cancel_silent = async_call_later(
                self.hass,
                remaining,
                self._on_silent_expired,
            )

    async def async_stop(self) -> None:
        """Désabonnement MQTT."""
        if self._debounce_task is not None:
            self._debounce_task.cancel()
            self._debounce_task = None
        if self._cancel_silent is not None:
            self._cancel_silent()
            self._cancel_silent = None
        if self._unsubscribe_mqtt is not None:
            self._unsubscribe_mqtt()
            self._unsubscribe_mqtt = None
            _LOGGER.debug("Désabonné MQTT — caméra=%s", self._camera)

    @callback
    def _handle_mqtt_message(self, message: Any) -> None:
        """Callback MQTT — parse, filtre par caméra, met à jour l'état, notifie."""
        event = _parse_event(message.payload)
        if event is None:
            _LOGGER.debug("Payload MQTT ignoré — non parseable (caméra=%s)", self._camera)
            return
        if event.camera != self._camera:
            return

        state = self._camera_state

        if event.type in ("new", "update"):
            state.last_severity = event.severity
            state.last_objects = event.objects
            state.last_event_time = event.start_time
            if event.type == "new":
                if event.review_id:
                    self._active_reviews.add(event.review_id)
                state.motion = True
        elif event.type == "end":
            if event.review_id:
                self._active_reviews.discard(event.review_id)
            # motion reste True si d'autres reviews sont encore actifs
            state.motion = len(self._active_reviews) > 0
            state.last_event_time = event.end_time or event.start_time

        _LOGGER.debug(
            "Événement traité — caméra=%s type=%s sévérité=%s objets=%s",
            event.camera, event.type, event.severity, event.objects,
        )

        if event.type in ("new", "update"):
            if (
                state.enabled
                and self._notifier is not None
                and self._filter_chain.apply(event)
                and self._throttler.should_notify(self._camera)
                and time.time() > self._silent_until
            ):
                if self._debounce_seconds == 0:
                    # Envoi immédiat — record() après await pour éviter le cooldown en cas d'échec
                    async def _notify_and_record(evt: Any) -> None:
                        await self._notifier.async_notify(evt)
                        self._throttler.record(self._camera)

                    self.hass.async_create_task(_notify_and_record(event))
                else:
                    # Accumulation pour debounce
                    self._pending_objects.update(event.objects)
                    self._pending_event = event
                    if self._debounce_task is not None:
                        self._debounce_task.cancel()
                    self._debounce_task = self.hass.async_create_task(
                        self._debounce_send()
                    )
        elif event.type == "end":
            # Annulation du debounce + libération du cooldown à la fin de l'événement
            if self._debounce_task is not None:
                self._debounce_task.cancel()
                self._debounce_task = None
            self._pending_objects.clear()
            self._pending_event = None
            self._throttler.release(self._camera)

        self.async_set_updated_data(state.as_dict())

    async def _debounce_send(self) -> None:
        """Envoie la notification groupée après la fenêtre de debounce."""
        try:
            await asyncio.sleep(self._debounce_seconds)
        except asyncio.CancelledError:
            return

        if self._pending_event is None or self._notifier is None:
            return

        # Event synthétique avec tous les objets accumulés
        grouped_event = replace(
            self._pending_event,
            objects=list(self._pending_objects),
        )
        await self._notifier.async_notify(grouped_event)
        self._throttler.record(self._camera)

        # Réinitialisation
        self._pending_objects.clear()
        self._pending_event = None
        self._debounce_task = None

    async def _async_update_data(self) -> dict[str, Any]:
        """Non utilisé — coordinator en mode push MQTT uniquement."""
        return self.data or {}
