"""Entités text — non enregistrées (configuration déplacée dans le config flow)."""

from __future__ import annotations

from homeassistant.components.text import TextEntity, TextMode
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import FEMConfigEntry
from .const import DOMAIN
from .coordinator import FrigateEventManagerCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FEMConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Aucune entité text créée — paramètres gérés dans le config flow."""


class _FEMTextBase(
    CoordinatorEntity[FrigateEventManagerCoordinator],
    TextEntity,
    RestoreEntity,
):
    """Base commune aux entités text FEM (templates Jinja2)."""

    _attr_has_entity_name = True
    _attr_mode = TextMode.TEXT
    _attr_native_max = 1024

    def __init__(
        self,
        coordinator: FrigateEventManagerCoordinator,
        subentry_id: str,
        initial: str,
    ) -> None:
        """Initialise l'entité text."""
        super().__init__(coordinator)
        cam_name = coordinator.camera
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, subentry_id)},
            name=f"Caméra {cam_name}",
            manufacturer="Frigate",
            config_subentry_id=subentry_id,
        )
        self._attr_native_value = initial

    async def async_added_to_hass(self) -> None:
        """Restaure la valeur depuis l'état précédent si disponible."""
        await super().async_added_to_hass()
        state = await self.async_get_last_state()
        if state is not None and state.state not in ("unknown", "unavailable"):
            self._attr_native_value = state.state
            self._apply_value(state.state)

    def _apply_value(self, value: str) -> None:
        """Applique la valeur sur le coordinator — à implémenter dans chaque sous-classe."""
        raise NotImplementedError


class NotifTitleText(_FEMTextBase):
    """Template Jinja2 du titre de notification."""

    _attr_translation_key = "notif_title"
    _attr_icon = "mdi:format-title"

    def __init__(
        self,
        coordinator: FrigateEventManagerCoordinator,
        subentry_id: str,
        initial: str,
    ) -> None:
        """Initialise l'entité titre de notification."""
        super().__init__(coordinator, subentry_id, initial)
        cam_name = coordinator.camera
        self._attr_unique_id = f"fem_{cam_name}_notif_title"

    async def async_set_value(self, value: str) -> None:
        """Met à jour le template de titre sur le coordinator en live."""
        self._attr_native_value = value
        self._apply_value(value)
        self.async_write_ha_state()

    def _apply_value(self, value: str) -> None:
        self.coordinator.set_notif_title(value or None)


class NotifMessageText(_FEMTextBase):
    """Template Jinja2 du message de notification."""

    _attr_translation_key = "notif_message"
    _attr_icon = "mdi:message-text-outline"

    def __init__(
        self,
        coordinator: FrigateEventManagerCoordinator,
        subentry_id: str,
        initial: str,
    ) -> None:
        """Initialise l'entité message de notification."""
        super().__init__(coordinator, subentry_id, initial)
        cam_name = coordinator.camera
        self._attr_unique_id = f"fem_{cam_name}_notif_message"

    async def async_set_value(self, value: str) -> None:
        """Met à jour le template de message sur le coordinator en live."""
        self._attr_native_value = value
        self._apply_value(value)
        self.async_write_ha_state()

    def _apply_value(self, value: str) -> None:
        self.coordinator.set_notif_message(value or None)


class CriticalTemplateText(_FEMTextBase):
    """Condition Jinja2 pour les notifications critiques."""

    _attr_translation_key = "critical_template"
    _attr_icon = "mdi:alert-circle-outline"

    def __init__(
        self,
        coordinator: FrigateEventManagerCoordinator,
        subentry_id: str,
        initial: str,
    ) -> None:
        """Initialise l'entité template critique."""
        super().__init__(coordinator, subentry_id, initial)
        cam_name = coordinator.camera
        self._attr_unique_id = f"fem_{cam_name}_critical_template"

    async def async_set_value(self, value: str) -> None:
        """Met à jour le template critique sur le coordinator en live."""
        self._attr_native_value = value
        self._apply_value(value)
        self.async_write_ha_state()

    def _apply_value(self, value: str) -> None:
        self.coordinator.set_critical_template(value or None)
