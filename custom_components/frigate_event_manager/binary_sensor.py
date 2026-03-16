"""Entité binary_sensor pour Frigate Event Manager — mouvement par caméra.

Un binary_sensor par caméra : ON quand un événement Frigate de type "new" est actif,
OFF quand l'événement se termine (type "end").
"""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
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
    """Crée les binary_sensors à partir des caméras découvertes.

    Note comportementale : les entités sont créées une seule fois au chargement
    de la plateforme, à partir de coordinator.data au moment du setup. Si aucun
    événement MQTT n'a encore été reçu (coordinator.data vide), aucune entité
    n'est créée. Les caméras découvertes ultérieurement via MQTT n'apparaissent
    pas automatiquement — un reload de l'intégration est nécessaire pour les
    enregistrer. La découverte dynamique post-démarrage est prévue en T-508.
    """
    coordinator: FrigateEventManagerCoordinator = hass.data[DOMAIN][entry.entry_id]

    sensors = [
        FrigateMotionSensor(coordinator, cam["name"])
        for cam in coordinator.data or []
    ]
    async_add_entities(sensors)


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
        cam_name: str,
    ) -> None:
        """Initialise le binary_sensor pour la caméra donnée."""
        super().__init__(coordinator)
        self._cam_name = cam_name
        self._attr_name = "Mouvement"
        self._attr_unique_id = f"fem_{cam_name}_motion"

    @property
    def is_on(self) -> bool | None:
        """Retourne True si un mouvement est actif sur cette caméra."""
        for cam in self.coordinator.data or []:
            if cam["name"] == self._cam_name:
                return cam.get("motion", False)
        return None
