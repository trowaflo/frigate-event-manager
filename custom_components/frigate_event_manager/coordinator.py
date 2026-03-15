"""DataUpdateCoordinator pour Frigate Event Manager."""

from __future__ import annotations

import logging
from datetime import timedelta

import aiohttp

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL = timedelta(seconds=30)


class FrigateEventManagerCoordinator(DataUpdateCoordinator[list[dict]]):
    """Interroge /api/cameras toutes les 30 secondes."""

    def __init__(self, hass: HomeAssistant, url: str) -> None:
        """Initialise le coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )
        self._url = url

    async def _async_update_data(self) -> list[dict]:
        """Récupère la liste des caméras depuis l'addon Go."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self._url}/api/cameras",
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    if resp.status != 200:
                        raise UpdateFailed(f"HTTP {resp.status} depuis /api/cameras")
                    return await resp.json()
        except aiohttp.ClientError as err:
            raise UpdateFailed(f"Erreur connexion addon: {err}") from err
