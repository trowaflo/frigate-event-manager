"""Intégration Frigate Event Manager pour Home Assistant.

Couche légère qui délègue toute la logique métier au addon Go
via son API HTTP locale.
"""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

DOMAIN = "frigate_event_manager"

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Initialise l'intégration depuis une config entry."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "url": entry.data["url"],
        "port": entry.data["port"],
    }
    _LOGGER.debug(
        "Frigate Event Manager connecté sur %s:%s",
        entry.data["url"],
        entry.data["port"],
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Supprime la config entry."""
    hass.data[DOMAIN].pop(entry.entry_id, None)
    return True
