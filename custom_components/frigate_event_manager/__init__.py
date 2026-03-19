"""Intégration Frigate Event Manager pour Home Assistant."""

from __future__ import annotations

import logging

from homeassistant.components import mqtt
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import (
    CONF_NOTIF_MESSAGE,
    CONF_NOTIF_TITLE,
    CONF_NOTIFY_TARGET,
    CONF_PASSWORD,
    CONF_TAP_ACTION,
    CONF_URL,
    CONF_USERNAME,
    DEFAULT_TAP_ACTION,
    MEDIA_URL_TTL,
    PERSISTENT_NOTIFICATION,
    PROXY_CLIENT_KEY,
    PROXY_PATH_PREFIX,
    PROXY_VIEW_KEY,
    SIGNER_DOMAIN_KEY,
    SUBENTRY_TYPE_CAMERA,
)
from .coordinator import FrigateEventManagerCoordinator
from .domain.signer import MediaSigner
from .frigate_client import FrigateClient
from .ha_mqtt import HaMqttAdapter
from .media_proxy import FrigateMediaProxyView
from .notifier import HANotifier

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["switch", "binary_sensor", "button", "sensor"]

type FEMConfigEntry = ConfigEntry[dict[str, FrigateEventManagerCoordinator]]


async def async_migrate_entry(hass: HomeAssistant, entry: FEMConfigEntry) -> bool:
    """Migration des config entries vers la version actuelle."""
    _LOGGER.debug(
        "Migration de la version %d.%d vers 3.1",
        entry.version,
        entry.minor_version,
    )

    if entry.version == 2:
        # v2 -> v3 : suppression de notify_target global de entry.data
        new_data = {k: v for k, v in entry.data.items() if k != "notify_target"}
        hass.config_entries.async_update_entry(
            entry, data=new_data, version=3, minor_version=1
        )
        _LOGGER.info("Migration v2 -> v3 terminée")
        return True

    if entry.version == 3:
        return True

    # Version inconnue (supérieure) — bloquer le chargement pour éviter des données incompatibles
    _LOGGER.error(
        "Version de config entry %d non supportée — downgrade non pris en charge",
        entry.version,
    )
    return False


async def async_setup_entry(hass: HomeAssistant, entry: FEMConfigEntry) -> bool:
    """Initialise l'intégration depuis une config entry."""
    if not await mqtt.async_wait_for_mqtt_client(hass):
        raise ConfigEntryNotReady(
            "MQTT non disponible — configurez l'intégration MQTT d'abord."
        )

    # Signer HMAC — généré une fois, réutilisé entre les reloads de l'intégration
    if SIGNER_DOMAIN_KEY not in hass.data:
        ha_url = hass.config.external_url or hass.config.internal_url or ""
        if ha_url:
            proxy_base = f"{ha_url.rstrip('/')}{PROXY_PATH_PREFIX}"
            hass.data[SIGNER_DOMAIN_KEY] = MediaSigner(proxy_base, ttl=MEDIA_URL_TTL)
        else:
            _LOGGER.warning(
                "URL externe HA non configurée — presigned URLs médias désactivées"
            )

    signer = hass.data.get(SIGNER_DOMAIN_KEY)

    # Client Frigate pour le proxy (mis à jour à chaque reload)
    frigate_client = FrigateClient(
        entry.data[CONF_URL],
        entry.data.get(CONF_USERNAME),
        entry.data.get(CONF_PASSWORD),
    )
    hass.data[PROXY_CLIENT_KEY] = frigate_client

    # View proxy — enregistrée une seule fois dans le serveur HTTP de HA
    if signer and PROXY_VIEW_KEY not in hass.data:
        hass.http.register_view(FrigateMediaProxyView())
        hass.data[PROXY_VIEW_KEY] = True

    coordinators: dict[str, FrigateEventManagerCoordinator] = {}

    for subentry_id, subentry in entry.subentries.items():
        if subentry.subentry_type == SUBENTRY_TYPE_CAMERA:
            # notify_target depuis subentry uniquement — fallback persistent_notification
            notify_target = subentry.data.get(CONF_NOTIFY_TARGET) or PERSISTENT_NOTIFICATION
            notifier = HANotifier(
                hass,
                notify_target,
                title_tpl=subentry.data.get(CONF_NOTIF_TITLE) or None,
                message_tpl=subentry.data.get(CONF_NOTIF_MESSAGE) or None,
                signer=signer,
                frigate_url=entry.data.get(CONF_URL),
                tap_action=subentry.data.get(CONF_TAP_ACTION, DEFAULT_TAP_ACTION),
            )
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
    old_coordinators: dict[str, FrigateEventManagerCoordinator] = getattr(entry, "runtime_data", {})

    # Nettoyer les stores des subentries supprimées (avant unload, entry.subentries est déjà à jour)
    for subentry_id, coordinator in old_coordinators.items():
        if subentry_id not in entry.subentries:
            await coordinator._store.async_remove()

    for coordinator in old_coordinators.values():
        await coordinator.async_stop()

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
