"""Entité switch pour Frigate Event Manager — notifications par caméra."""

from __future__ import annotations

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
    """Crée une entité switch pour la caméra de cette config entry."""
    coordinator: FrigateEventManagerCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([FrigateNotificationSwitch(coordinator)])


class FrigateNotificationSwitch(
    CoordinatorEntity[FrigateEventManagerCoordinator], SwitchEntity
):
    """Active ou désactive les notifications pour une caméra."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:bell"

    def __init__(
        self,
        coordinator: FrigateEventManagerCoordinator,
    ) -> None:
        super().__init__(coordinator)
        cam_name = coordinator.camera
        self._attr_name = f"Notifications {cam_name}"
        self._attr_unique_id = f"fem_{cam_name}_switch"

    @property
    def is_on(self) -> bool:
        """Retourne l'état enabled de la caméra depuis le coordinator."""
        data = self.coordinator.data
        if data:
            return data.get("enabled", True)
        return self.coordinator.camera_state.enabled

    async def async_turn_on(self, **kwargs) -> None:
        """Active les notifications pour cette caméra."""
        self.coordinator.set_camera_enabled(True)

    async def async_turn_off(self, **kwargs) -> None:
        """Désactive les notifications pour cette caméra."""
        self.coordinator.set_camera_enabled(False)
