"""Frigate Event Manager integration for Home Assistant."""

from __future__ import annotations

import logging

from homeassistant.components import mqtt
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import (
    CONF_CRITICAL_SOUND,
    CONF_CRITICAL_VOLUME,
    CONF_NOTIF_MESSAGE,
    CONF_NOTIF_TITLE,
    CONF_NOTIFY_TARGET,
    CONF_PASSWORD,
    CONF_TAP_ACTION,
    CONF_URL,
    CONF_USERNAME,
    DEFAULT_CRITICAL_SOUND,
    DEFAULT_CRITICAL_VOLUME,
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

PLATFORMS = ["switch", "binary_sensor", "button", "sensor", "select"]

type FEMConfigEntry = ConfigEntry[dict[str, FrigateEventManagerCoordinator]]


async def async_migrate_entry(hass: HomeAssistant, entry: FEMConfigEntry) -> bool:
    """Migrate config entries to the current version."""
    _LOGGER.debug(
        "migrating from version %d.%d",
        entry.version,
        entry.minor_version,
    )

    if entry.version == 2:
        # v2 -> v3: remove global notify_target from entry.data
        new_data = {k: v for k, v in entry.data.items() if k != "notify_target"}
        hass.config_entries.async_update_entry(
            entry, data=new_data, version=3, minor_version=1
        )
        _LOGGER.info("migration v2 -> v3 complete")
        return True

    if entry.version == 3:
        # v3 -> v4: tuning parameters remain in subentry.data — no transformation.
        hass.config_entries.async_update_entry(entry, version=4, minor_version=1)
        _LOGGER.info("migration v3 -> v4 complete")
        return True

    if entry.version == 4:
        # v4 -> v5: tuning parameters (cooldown, debounce, severity, tap_action,
        # notif_title, notif_message, critical_template) remain in subentry.data —
        # transparent migration, all keys are already present.
        hass.config_entries.async_update_entry(entry, version=5, minor_version=1)
        _LOGGER.info("migration v4 -> v5 complete")
        return True

    if entry.version == 5:
        return True

    # Unknown (higher) version — block loading to avoid incompatible data
    _LOGGER.error(
        "config entry version %d not supported — downgrade not handled",
        entry.version,
    )
    return False


async def async_setup_entry(hass: HomeAssistant, entry: FEMConfigEntry) -> bool:
    """Set up the integration from a config entry."""
    if not await mqtt.async_wait_for_mqtt_client(hass):
        raise ConfigEntryNotReady(
            "MQTT not available — configure the MQTT integration first."
        )

    # HMAC signer — generated once, reused across integration reloads
    if SIGNER_DOMAIN_KEY not in hass.data:
        ha_url = hass.config.external_url or hass.config.internal_url or ""
        if ha_url:
            proxy_base = f"{ha_url.rstrip('/')}{PROXY_PATH_PREFIX}"
            hass.data[SIGNER_DOMAIN_KEY] = MediaSigner(proxy_base, ttl=MEDIA_URL_TTL)
        else:
            _LOGGER.warning(
                "HA external URL not configured — presigned media URLs disabled"
            )

    signer = hass.data.get(SIGNER_DOMAIN_KEY)

    # Frigate client for the proxy (updated on each reload)
    frigate_client = FrigateClient(
        entry.data[CONF_URL],
        entry.data.get(CONF_USERNAME),
        entry.data.get(CONF_PASSWORD),
    )
    hass.data[PROXY_CLIENT_KEY] = frigate_client

    # Proxy view — registered once in the HA HTTP server
    if signer and PROXY_VIEW_KEY not in hass.data:
        hass.http.register_view(FrigateMediaProxyView())
        hass.data[PROXY_VIEW_KEY] = True

    coordinators: dict[str, FrigateEventManagerCoordinator] = {}

    for subentry_id, subentry in entry.subentries.items():
        if subentry.subentry_type == SUBENTRY_TYPE_CAMERA:
            # notify_target from subentry only — fallback to persistent_notification
            notify_target = subentry.data.get(CONF_NOTIFY_TARGET) or PERSISTENT_NOTIFICATION
            notifier = HANotifier(
                hass,
                notify_target,
                title_tpl=subentry.data.get(CONF_NOTIF_TITLE) or None,
                message_tpl=subentry.data.get(CONF_NOTIF_MESSAGE) or None,
                signer=signer,
                frigate_url=entry.data.get(CONF_URL),
                tap_action=subentry.data.get(CONF_TAP_ACTION, DEFAULT_TAP_ACTION),
                critical_sound=subentry.data.get(CONF_CRITICAL_SOUND, DEFAULT_CRITICAL_SOUND),
                critical_volume=subentry.data.get(CONF_CRITICAL_VOLUME, DEFAULT_CRITICAL_VOLUME),
            )
            coordinator = FrigateEventManagerCoordinator(
                hass, entry, subentry,
                notifier=notifier,
                event_source=HaMqttAdapter(hass),
            )
            await coordinator.async_start()
            coordinators[subentry_id] = coordinator

    entry.runtime_data = coordinators

    # Reload the integration when a subentry is added/removed
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    _LOGGER.debug(
        "Frigate Event Manager initialized — %d camera(s) configured",
        len(coordinators),
    )
    return True


async def _async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the integration when a subentry is added/modified/removed."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: FEMConfigEntry) -> bool:
    """Unload the integration and stop all MQTT subscriptions."""
    old_coordinators: dict[str, FrigateEventManagerCoordinator] = getattr(entry, "runtime_data", {})

    # Clean up stores for removed subentries (before unload, entry.subentries is already updated)
    for subentry_id, coordinator in old_coordinators.items():
        if subentry_id not in entry.subentries:
            await coordinator.async_remove_store()

    for coordinator in old_coordinators.values():
        await coordinator.async_stop()

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
