"""Intégration Frigate Event Manager pour Home Assistant.

Écoute les événements Frigate via MQTT natif HA, filtre et dispatche
vers les handlers (notifications, entités).
"""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_MQTT_TOPIC, DOMAIN
from .coordinator import FrigateEventManagerCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["switch", "binary_sensor"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Initialise l'intégration depuis une config entry."""
    # Le coordinator reçoit la ConfigEntry complète (pas entry.data)
    # pour accéder à entry.data[CONF_MQTT_TOPIC] et à l'entry_id
    coordinator = FrigateEventManagerCoordinator(hass, entry)

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Démarrage de la souscription MQTT (remplace async_config_entry_first_refresh)
    # La reconnexion est gérée nativement par l'intégration MQTT de HA
    await coordinator.async_start()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    _LOGGER.debug(
        "Frigate Event Manager initialisé (topic: %s)",
        entry.data.get(CONF_MQTT_TOPIC),
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Supprime la config entry et décharge les plateformes."""
    coordinator: FrigateEventManagerCoordinator = hass.data[DOMAIN].get(entry.entry_id)

    # Désabonnement MQTT avant le déchargement des plateformes
    if coordinator is not None:
        await coordinator.async_stop()

    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unloaded
