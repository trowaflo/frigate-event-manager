"""DataUpdateCoordinator MQTT pour Frigate Event Manager — push uniquement."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components import mqtt
from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import CONF_CAMERA, DEFAULT_MQTT_TOPIC, DOMAIN
from .domain.filter import FilterChain
from .domain.model import CameraState, _parse_event
from .domain.ports import NotifierPort
from .domain.throttle import Throttler

_LOGGER = logging.getLogger(__name__)


class FrigateEventManagerCoordinator(DataUpdateCoordinator[dict]):
    """Coordinator MQTT — push uniquement, par caméra (subentry)."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        subentry: ConfigSubentry,
        notifier: NotifierPort | None = None,
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
        self._notifier: NotifierPort | None = notifier
        self._throttler = Throttler()
        self._filter_chain = FilterChain([])

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
            and self._filter_chain.apply(event)
            and self._throttler.should_notify(self._camera)
        ):
            self.hass.async_create_task(self._notifier.async_notify(event))
            self._throttler.record(self._camera)

        self.async_set_updated_data(state.as_dict())

    async def _async_update_data(self) -> dict:
        """Non utilisé — coordinator en mode push MQTT uniquement."""
        return self.data or {}
