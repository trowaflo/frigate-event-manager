"""Switch entity — enable/disable notifications per camera."""

from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import FEMConfigEntry
from .const import DOMAIN
from .coordinator import FrigateEventManagerCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FEMConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create one switch entity per configured camera."""
    for subentry_id, coordinator in entry.runtime_data.items():
        async_add_entities(
            [FrigateNotificationSwitch(coordinator, subentry_id)],
            config_subentry_id=subentry_id,
        )


class FrigateNotificationSwitch(
    CoordinatorEntity[FrigateEventManagerCoordinator], SwitchEntity
):
    """Enable or disable notifications for a camera."""

    _attr_has_entity_name = True
    _attr_translation_key = "notifications"
    _attr_icon = "mdi:bell"

    def __init__(
        self,
        coordinator: FrigateEventManagerCoordinator,
        subentry_id: str,
    ) -> None:
        """Initialize the switch for the given camera."""
        super().__init__(coordinator)
        cam_name = coordinator.camera
        self._attr_unique_id = f"fem_{cam_name}_switch"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, subentry_id)},
            name=f"Caméra {cam_name}",
            manufacturer="Frigate",
        )

    @property
    def is_on(self) -> bool:
        """Return the enabled state from coordinator.data."""
        data = self.coordinator.data
        if data:
            return bool(data.get("enabled", True))
        return self.coordinator.camera_state.enabled

    async def async_turn_on(self, **kwargs) -> None:
        """Enable notifications for this camera."""
        self.coordinator.set_camera_enabled(True)

    async def async_turn_off(self, **kwargs) -> None:
        """Disable notifications for this camera."""
        self.coordinator.set_camera_enabled(False)
