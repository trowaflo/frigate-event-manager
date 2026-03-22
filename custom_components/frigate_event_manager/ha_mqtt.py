"""HA MQTT adapter — implements EventSourcePort via homeassistant.components.mqtt."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from homeassistant.components import mqtt
from homeassistant.core import HomeAssistant


class HaMqttAdapter:
    """Outgoing adapter — subscribes to the native Home Assistant MQTT broker."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the adapter with the HA instance."""
        self._hass = hass

    async def async_subscribe(
        self,
        topic: str,
        callback: Callable[[Any], None],
    ) -> Callable[[], None]:
        """Subscribe to the MQTT topic. Returns the unsubscribe function."""
        return await mqtt.async_subscribe(self._hass, topic, callback)
