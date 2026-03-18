"""Adaptateur MQTT HA — implémente EventSourcePort via homeassistant.components.mqtt."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from homeassistant.components import mqtt
from homeassistant.core import HomeAssistant


class HaMqttAdapter:
    """Adaptateur sortant — souscrit au broker MQTT natif Home Assistant."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialise l'adaptateur avec l'instance HA."""
        self._hass = hass

    async def async_subscribe(
        self,
        topic: str,
        callback: Callable[[Any], None],
    ) -> Callable[[], None]:
        """Souscrit au topic MQTT. Retourne la fonction de désabonnement."""
        return await mqtt.async_subscribe(self._hass, topic, callback)
