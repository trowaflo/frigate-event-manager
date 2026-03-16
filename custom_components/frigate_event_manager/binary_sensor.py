"""Entité binary_sensor pour Frigate Event Manager — mouvement par caméra.

Un binary_sensor par config entry caméra : ON quand un événement Frigate
de type "new" est actif, OFF quand l'événement se termine (type "end").
"""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.config_entries import ConfigEntry, ConfigEntryNotReady
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import FrigateEventManagerCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Crée une entité binary_sensor pour la caméra de cette config entry."""
    coordinator = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    if coordinator is None:
        raise ConfigEntryNotReady(f"Coordinator non trouvé pour {entry.entry_id}")
    async_add_entities([FrigateMotionSensor(coordinator)])


class FrigateMotionSensor(
    CoordinatorEntity[FrigateEventManagerCoordinator], BinarySensorEntity
):
    """Détecte le mouvement actif sur une caméra Frigate.

    Passe à ON lors d'un événement de type "new", revient à OFF sur "end".
    Repose sur le champ `motion` de CameraState maintenu par le coordinator.
    """

    _attr_has_entity_name = True
    _attr_device_class = BinarySensorDeviceClass.MOTION
    _attr_icon = "mdi:motion-sensor"

    def __init__(
        self,
        coordinator: FrigateEventManagerCoordinator,
    ) -> None:
        """Initialise le binary_sensor pour la caméra donnée."""
        super().__init__(coordinator)
        cam_name = coordinator.camera
        self._attr_name = "Mouvement"
        self._attr_unique_id = f"fem_{cam_name}_motion"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, cam_name)},
            name=f"Caméra {cam_name}",
            manufacturer="Frigate",
        )

    @property
    def is_on(self) -> bool | None:
        """Retourne True si un mouvement est actif sur cette caméra."""
        data = self.coordinator.data
        if data:
            return data.get("motion", False)
        return self.coordinator.camera_state.motion
