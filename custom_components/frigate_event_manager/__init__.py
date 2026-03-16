"""Intégration Frigate Event Manager pour Home Assistant.

Écoute les événements Frigate via MQTT natif HA, filtre et dispatche
vers les handlers (notifications, entités).
"""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_CAMERA, DOMAIN
from .coordinator import FrigateEventManagerCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["switch", "binary_sensor"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Initialise l'intégration depuis une config entry."""
    # Entrée globale (URL + notify_target) — pas d'entités ni de coordinator
    if CONF_CAMERA not in entry.data:
        _LOGGER.debug(
            "Frigate Event Manager — entrée globale initialisée (url: %s)",
            entry.data.get("url"),
        )
        return True

    # Entrée caméra — setup coordinator + forward platforms
    coordinator = FrigateEventManagerCoordinator(hass, entry)

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Démarrage de la souscription MQTT
    # La reconnexion est gérée nativement par l'intégration MQTT de HA
    await coordinator.async_start()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    _LOGGER.debug(
        "Frigate Event Manager — caméra %r initialisée",
        entry.data[CONF_CAMERA],
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Supprime la config entry et décharge les plateformes."""
    # Entrée globale — rien à décharger
    if CONF_CAMERA not in entry.data:
        return True

    coordinator: FrigateEventManagerCoordinator | None = hass.data.get(DOMAIN, {}).get(
        entry.entry_id
    )

    # Désabonnement MQTT avant le déchargement des plateformes
    if coordinator is not None:
        await coordinator.async_stop()

    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unloaded
