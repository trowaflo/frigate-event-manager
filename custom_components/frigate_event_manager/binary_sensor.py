"""Binary sensor entity — motion detection and silent mode per camera."""

from __future__ import annotations

import time

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
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
    """Create binary sensor entities per configured camera."""
    for subentry_id, coordinator in entry.runtime_data.items():
        async_add_entities(
            [
                FrigateMotionSensor(coordinator, subentry_id),
                SilentStateSensor(coordinator, subentry_id),
            ],
            config_subentry_id=subentry_id,
        )


class FrigateMotionSensor(
    CoordinatorEntity[FrigateEventManagerCoordinator], BinarySensorEntity
):
    """Indicates whether motion is active on a Frigate camera.

    ON on event type=new, OFF on type=end.
    """

    _attr_has_entity_name = True
    _attr_translation_key = "motion"
    _attr_device_class = BinarySensorDeviceClass.MOTION
    _attr_icon = "mdi:motion-sensor"

    def __init__(
        self,
        coordinator: FrigateEventManagerCoordinator,
        subentry_id: str,
    ) -> None:
        """Initialize the binary sensor for the given camera."""
        super().__init__(coordinator)
        cam_name = coordinator.camera
        self._attr_unique_id = f"fem_{cam_name}_motion"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, subentry_id)},
            name=f"Caméra {cam_name}",
            manufacturer="Frigate",
        )

    @property
    def is_on(self) -> bool | None:
        """Return True if motion is active."""
        data = self.coordinator.data
        if data:
            return bool(data.get("motion", False))
        return self.coordinator.camera_state.motion


class SilentStateSensor(
    CoordinatorEntity[FrigateEventManagerCoordinator], BinarySensorEntity
):
    """Indicates whether silent mode is active for this camera.

    ON if _silent_until is in the future, OFF otherwise.
    """

    _attr_has_entity_name = True
    _attr_device_class = BinarySensorDeviceClass.RUNNING
    _attr_icon = "mdi:bell-sleep"
    _attr_translation_key = "silent_state"

    def __init__(
        self,
        coordinator: FrigateEventManagerCoordinator,
        subentry_id: str,
    ) -> None:
        """Initialize the silent binary sensor for the given camera."""
        super().__init__(coordinator)
        cam_name = coordinator.camera
        self._attr_unique_id = f"fem_{cam_name}_silent_state"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, subentry_id)},
            name=f"Caméra {cam_name}",
            manufacturer="Frigate",
        )

    @property
    def is_on(self) -> bool:
        """Return True if silent mode is active."""
        return time.time() < self.coordinator.silent_until
