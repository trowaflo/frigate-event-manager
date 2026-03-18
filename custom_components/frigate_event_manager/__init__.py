"""Intégration Frigate Event Manager pour Home Assistant."""

from __future__ import annotations

import logging

from homeassistant.components import mqtt
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import CONF_NOTIFY_TARGET, SUBENTRY_TYPE_CAMERA
from .coordinator import FrigateEventManagerCoordinator
from .ha_mqtt import HaMqttAdapter
from .notifier import HANotifier

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["switch", "binary_sensor"]

type FEMConfigEntry = ConfigEntry[dict[str, FrigateEventManagerCoordinator]]


async def async_setup_entry(hass: HomeAssistant, entry: FEMConfigEntry) -> bool:
    """Initialise l'intégration depuis une config entry."""
    if not await mqtt.async_wait_for_mqtt_client(hass):
        raise ConfigEntryNotReady(
            "MQTT non disponible — configurez l'intégration MQTT d'abord."
        )

    coordinators: dict[str, FrigateEventManagerCoordinator] = {}

    for subentry_id, subentry in entry.subentries.items():
        if subentry.subentry_type == SUBENTRY_TYPE_CAMERA:
            notify_target = (
                subentry.data.get(CONF_NOTIFY_TARGET)
                or entry.data.get(CONF_NOTIFY_TARGET)
            )
            notifier = HANotifier(hass, notify_target) if notify_target else None
            coordinator = FrigateEventManagerCoordinator(
                hass, entry, subentry,
                notifier=notifier,
                event_source=HaMqttAdapter(hass),
            )
            await coordinator.async_start()
            coordinators[subentry_id] = coordinator

    entry.runtime_data = coordinators

    # Recharge l'intégration quand une subentry est ajoutée/supprimée
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    _LOGGER.debug(
        "Frigate Event Manager initialisé — %d caméra(s) configurée(s)",
        len(coordinators),
    )
    return True


async def _async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Recharge l'intégration quand une subentry est ajoutée/modifiée/supprimée."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: FEMConfigEntry) -> bool:
    """Décharge l'intégration et arrête toutes les souscriptions MQTT."""
    for coordinator in getattr(entry, "runtime_data", {}).values():
        await coordinator.async_stop()

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
