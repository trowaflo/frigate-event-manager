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
    """Crée les switches à partir des caméras découvertes.

    Note comportementale : les entités sont créées une seule fois au chargement
    de la plateforme, à partir de coordinator.data au moment du setup. Si aucun
    événement MQTT n'a encore été reçu (coordinator.data vide), aucune entité
    n'est créée. Les caméras découvertes ultérieurement via MQTT n'apparaissent
    pas automatiquement — un reload de l'intégration est nécessaire pour les
    enregistrer. La découverte dynamique post-démarrage est prévue en T-484.
    """
    coordinator: FrigateEventManagerCoordinator = hass.data[DOMAIN][entry.entry_id]

    switches = [
        FrigateNotificationSwitch(coordinator, cam["name"])
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
    ) -> None:
        super().__init__(coordinator)
        self._cam_name = cam_name
        self._attr_name = "Notifications"
        self._attr_unique_id = f"fem_{cam_name}_notifications"

    @property
    def is_on(self) -> bool:
        """Retourne l'état enabled de la caméra depuis le coordinator."""
        for cam in self.coordinator.data or []:
            if cam["name"] == self._cam_name:
                return cam.get("enabled", True)
        return True

    async def async_turn_on(self, **kwargs) -> None:
        """Active les notifications pour cette caméra."""
        self.coordinator.set_camera_enabled(self._cam_name, True)

    async def async_turn_off(self, **kwargs) -> None:
        """Désactive les notifications pour cette caméra."""
        self.coordinator.set_camera_enabled(self._cam_name, False)
