"""Entités number — cooldown et debounce par caméra (modifiables depuis le dashboard)."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import FEMConfigEntry
from .const import (
    CONF_COOLDOWN,
    CONF_DEBOUNCE,
    DEFAULT_DEBOUNCE,
    DEFAULT_THROTTLE_COOLDOWN,
    DOMAIN,
)
from .coordinator import FrigateEventManagerCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FEMConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Crée les entités number (cooldown + debounce) par caméra configurée."""
    entities: list[NumberEntity] = []
    for subentry_id, coordinator in entry.runtime_data.items():
        subentry = entry.subentries[subentry_id]
        entities.append(
            CooldownNumber(
                coordinator,
                subentry_id,
                initial=int(subentry.data.get(CONF_COOLDOWN, DEFAULT_THROTTLE_COOLDOWN)),
            )
        )
        entities.append(
            DebounceNumber(
                coordinator,
                subentry_id,
                initial=int(subentry.data.get(CONF_DEBOUNCE, DEFAULT_DEBOUNCE)),
            )
        )
    async_add_entities(entities)


class _FEMNumberBase(
    CoordinatorEntity[FrigateEventManagerCoordinator],
    NumberEntity,
    RestoreEntity,
):
    """Base commune aux entités number FEM."""

    _attr_has_entity_name = True
    _attr_mode = NumberMode.BOX

    def __init__(
        self,
        coordinator: FrigateEventManagerCoordinator,
        subentry_id: str,
        initial: float,
    ) -> None:
        """Initialise l'entité number."""
        super().__init__(coordinator)
        cam_name = coordinator.camera
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, subentry_id)},
            name=f"Caméra {cam_name}",
            manufacturer="Frigate",
        )
        self._attr_native_value = float(initial)

    async def async_added_to_hass(self) -> None:
        """Restaure la valeur depuis l'état précédent si disponible."""
        await super().async_added_to_hass()
        state = await self.async_get_last_state()
        if state is not None:
            try:
                restored = float(state.state)
                restored = max(
                    float(self._attr_native_min_value),
                    min(float(self._attr_native_max_value), restored),
                )
                self._attr_native_value = restored
                self._apply_value(int(restored))
            except (ValueError, TypeError):
                pass

    def _apply_value(self, value: int) -> None:
        """Applique la valeur sur le coordinator — à implémenter dans chaque sous-classe."""
        raise NotImplementedError


class CooldownNumber(_FEMNumberBase):
    """Cooldown anti-spam en secondes (0–3600)."""

    _attr_translation_key = "cooldown"
    _attr_native_min_value = 0
    _attr_native_max_value = 3600
    _attr_native_step = 1
    _attr_native_unit_of_measurement = "s"
    _attr_icon = "mdi:timer-sand"

    def __init__(
        self,
        coordinator: FrigateEventManagerCoordinator,
        subentry_id: str,
        initial: int,
    ) -> None:
        """Initialise l'entité cooldown."""
        super().__init__(coordinator, subentry_id, float(initial))
        cam_name = coordinator.camera
        self._attr_unique_id = f"fem_{cam_name}_cooldown"

    async def async_set_native_value(self, value: float) -> None:
        """Met à jour le cooldown sur le coordinator en live."""
        self._attr_native_value = value
        self._apply_value(int(value))
        self.async_write_ha_state()

    def _apply_value(self, value: int) -> None:
        self.coordinator.set_cooldown(value)


class DebounceNumber(_FEMNumberBase):
    """Fenêtre de debounce en secondes (0–60)."""

    _attr_translation_key = "debounce"
    _attr_native_min_value = 0
    _attr_native_max_value = 60
    _attr_native_step = 1
    _attr_native_unit_of_measurement = "s"
    _attr_icon = "mdi:timer-pause-outline"

    def __init__(
        self,
        coordinator: FrigateEventManagerCoordinator,
        subentry_id: str,
        initial: int,
    ) -> None:
        """Initialise l'entité debounce."""
        super().__init__(coordinator, subentry_id, float(initial))
        cam_name = coordinator.camera
        self._attr_unique_id = f"fem_{cam_name}_debounce"

    async def async_set_native_value(self, value: float) -> None:
        """Met à jour le debounce sur le coordinator en live."""
        self._attr_native_value = value
        self._apply_value(int(value))
        self.async_write_ha_state()

    def _apply_value(self, value: int) -> None:
        self.coordinator.set_debounce(value)
