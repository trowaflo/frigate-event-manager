"""Intégration Frigate Event Manager pour Home Assistant.

Couche légère qui délègue toute la logique métier au addon Go
via son API HTTP locale, découverte automatiquement via le Supervisor.
"""

from __future__ import annotations

import logging
import os

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import ADDON_PORT, ADDON_SLUG, DOMAIN, SUPERVISOR_URL

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Initialise l'intégration depuis une config entry."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {"url": entry.data["url"]}
    _LOGGER.debug("Frigate Event Manager connecté sur %s", entry.data["url"])
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Supprime la config entry."""
    hass.data[DOMAIN].pop(entry.entry_id, None)
    return True


async def get_addon_url() -> str | None:
    """Récupère l'URL du addon Go via le Supervisor.

    Retourne l'URL complète (ex: http://172.30.33.x:5555) ou None
    si le Supervisor n'est pas disponible ou l'addon non trouvé.
    """
    token = os.environ.get("SUPERVISOR_TOKEN")
    if not token:
        return None

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{SUPERVISOR_URL}/addons/{ADDON_SLUG}/info",
                headers={"Authorization": f"Bearer {token}"},
                timeout=aiohttp.ClientTimeout(total=5),
            ) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()
                ip = data.get("data", {}).get("ip_address")
                if ip:
                    return f"http://{ip}:{ADDON_PORT}"
    except aiohttp.ClientError:
        pass

    return None
