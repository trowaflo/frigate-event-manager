"""Entité binary_sensor — détection de mouvement par caméra."""

from __future__ import annotations

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
    """Crée une entité binary_sensor par caméra configurée."""
    for subentry_id, coordinator in entry.runtime_data.items():
        async_add_entities(
            [FrigateMotionSensor(coordinator, subentry_id)],
            config_subentry_id=subentry_id,
        )


class FrigateMotionSensor(
    CoordinatorEntity[FrigateEventManagerCoordinator], BinarySensorEntity
):
    """Indique si un mouvement est actif sur une caméra Frigate.

    ON lors d'un événement type=new, OFF lors de type=end.
    """

    _attr_has_entity_name = True
    _attr_device_class = BinarySensorDeviceClass.MOTION
    _attr_icon = "mdi:motion-sensor"

    def __init__(
        self,
        coordinator: FrigateEventManagerCoordinator,
        subentry_id: str,
    ) -> None:
        """Initialise le binary_sensor pour la caméra donnée."""
        super().__init__(coordinator)
        cam_name = coordinator.camera
        self._attr_name = "Mouvement"
        self._attr_unique_id = f"fem_{cam_name}_motion"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, subentry_id)},
            name=f"Caméra {cam_name}",
            manufacturer="Frigate",
        )

    @property
    def is_on(self) -> bool | None:
        """Retourne True si un mouvement est actif."""
        data = self.coordinator.data
        if data:
            return bool(data.get("motion", False))
        return self.coordinator.camera_state.motion
