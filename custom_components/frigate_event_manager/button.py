"""Entité bouton — activation du mode silencieux par caméra."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
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
    """Crée une entité bouton silencieux par caméra configurée."""
    for subentry_id, coordinator in entry.runtime_data.items():
        async_add_entities(
            [
                SilentButton(coordinator, subentry_id),
                CancelSilentButton(coordinator, subentry_id),
            ],
            config_subentry_id=subentry_id,
        )


class SilentButton(
    CoordinatorEntity[FrigateEventManagerCoordinator], ButtonEntity
):
    """Bouton pour activer le mode silencieux sur une caméra."""

    _attr_has_entity_name = True
    _attr_translation_key = "silent_button"
    _attr_icon = "mdi:bell-sleep"

    def __init__(
        self,
        coordinator: FrigateEventManagerCoordinator,
        subentry_id: str,
    ) -> None:
        """Initialise le bouton pour la caméra donnée."""
        super().__init__(coordinator)
        cam_name = coordinator.camera
        self._attr_unique_id = f"fem_{cam_name}_silent"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, subentry_id)},
            name=f"Caméra {cam_name}",
            manufacturer="Frigate",
        )

    async def async_press(self) -> None:
        """Active le mode silencieux pour cette caméra."""
        self.coordinator.activate_silent_mode()


class CancelSilentButton(
    CoordinatorEntity[FrigateEventManagerCoordinator], ButtonEntity
):
    """Bouton pour annuler le mode silencieux actif sur une caméra."""

    _attr_has_entity_name = True
    _attr_translation_key = "cancel_silent_button"
    _attr_icon = "mdi:bell-cancel"

    def __init__(
        self,
        coordinator: FrigateEventManagerCoordinator,
        subentry_id: str,
    ) -> None:
        """Initialise le bouton d'annulation de silence pour la caméra donnée."""
        super().__init__(coordinator)
        cam_name = coordinator.camera
        self._attr_unique_id = f"fem_{cam_name}_cancel_silent"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, subentry_id)},
            name=f"Caméra {cam_name}",
            manufacturer="Frigate",
        )

    async def async_press(self) -> None:
        """Annule le mode silencieux actif pour cette caméra."""
        await self.coordinator.async_cancel_silent()
