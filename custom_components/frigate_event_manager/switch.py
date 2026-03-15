"""Entité switch pour Frigate Event Manager — notifications par caméra."""

from __future__ import annotations

import aiohttp

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import FrigateEventManagerCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Crée les switches à partir des caméras découvertes."""
    coordinator: FrigateEventManagerCoordinator = hass.data[DOMAIN][entry.entry_id]
    url: str = entry.data["url"]

    switches = [
        FrigateNotificationSwitch(coordinator, cam["name"], url)
        for cam in coordinator.data or []
    ]
    async_add_entities(switches)


class FrigateNotificationSwitch(
    CoordinatorEntity[FrigateEventManagerCoordinator], SwitchEntity
):
    """Active ou désactive les notifications pour une caméra."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:bell"

    def __init__(
        self,
        coordinator: FrigateEventManagerCoordinator,
        cam_name: str,
        addon_url: str,
    ) -> None:
        super().__init__(coordinator)
        self._cam_name = cam_name
        self._addon_url = addon_url
        self._attr_name = "Notifications"
        self._attr_unique_id = f"fem_{cam_name}_notifications"

    @property
    def is_on(self) -> bool:
        for cam in self.coordinator.data or []:
            if cam["name"] == self._cam_name:
                return cam.get("enabled", True)
        return True

    async def async_turn_on(self, **kwargs) -> None:
        await self._set_enabled(True)

    async def async_turn_off(self, **kwargs) -> None:
        await self._set_enabled(False)

    async def _set_enabled(self, enabled: bool) -> None:
        async with aiohttp.ClientSession() as session:
            await session.patch(
                f"{self._addon_url}/api/cameras/{self._cam_name}",
                json={"enabled": enabled},
                timeout=aiohttp.ClientTimeout(total=5),
            )
        await self.coordinator.async_request_refresh()
