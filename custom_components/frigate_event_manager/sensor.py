"""Sensor — silent mode reactivation timestamp per camera."""

from __future__ import annotations

import time
from datetime import datetime, timezone

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
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
    """Create one timestamp sensor per configured camera."""
    for subentry_id, coordinator in entry.runtime_data.items():
        async_add_entities(
            [SilentUntilSensor(coordinator, subentry_id)],
            config_subentry_id=subentry_id,
        )


class SilentUntilSensor(
    CoordinatorEntity[FrigateEventManagerCoordinator], SensorEntity
):
    """End timestamp of silent mode. None if silence is inactive.

    Exposes the notification reactivation date/time as a TIMESTAMP
    sensor, compatible with HA automations.
    """

    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:timer-outline"
    _attr_translation_key = "silent_until"

    def __init__(
        self,
        coordinator: FrigateEventManagerCoordinator,
        subentry_id: str,
    ) -> None:
        """Initialize the sensor for the given camera."""
        super().__init__(coordinator)
        cam_name = coordinator.camera
        self._attr_unique_id = f"fem_{cam_name}_silent_until"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, subentry_id)},
            name=f"Caméra {cam_name}",
            manufacturer="Frigate",
        )

    @property
    def native_value(self) -> datetime | None:
        """Return the end of silence date, None if silence is inactive."""
        silent_until = self.coordinator.silent_until
        if time.time() >= silent_until:
            return None
        return datetime.fromtimestamp(silent_until, tz=timezone.utc)
