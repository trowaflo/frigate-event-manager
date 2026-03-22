"""Number entities — not registered (configuration moved to config flow)."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
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
    """No number entity created — parameters managed in config flow."""


class _FEMNumberBase(
    CoordinatorEntity[FrigateEventManagerCoordinator],
    NumberEntity,
    RestoreEntity,
):
    """Common base for FEM number entities."""

    _attr_has_entity_name = True
    _attr_mode = NumberMode.BOX

    def __init__(
        self,
        coordinator: FrigateEventManagerCoordinator,
        subentry_id: str,
        initial: float,
    ) -> None:
        """Initialize the number entity."""
        super().__init__(coordinator)
        cam_name = coordinator.camera
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, subentry_id)},
            name=f"Caméra {cam_name}",
            manufacturer="Frigate",
        )
        self._attr_native_value = float(initial)

    async def async_added_to_hass(self) -> None:
        """Restore value from previous state if available."""
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
        """Apply the value to the coordinator — to be implemented in each subclass."""
        raise NotImplementedError


class CooldownNumber(_FEMNumberBase):
    """Anti-spam cooldown in seconds (0–3600)."""

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
        """Initialize the cooldown entity."""
        super().__init__(coordinator, subentry_id, float(initial))
        cam_name = coordinator.camera
        self._attr_unique_id = f"fem_{cam_name}_cooldown"

    async def async_set_native_value(self, value: float) -> None:
        """Update the cooldown on the coordinator live."""
        self._attr_native_value = value
        self._apply_value(int(value))
        self.async_write_ha_state()

    def _apply_value(self, value: int) -> None:
        self.coordinator.set_cooldown(value)


class DebounceNumber(_FEMNumberBase):
    """Debounce window in seconds (0–60)."""

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
        """Initialize the debounce entity."""
        super().__init__(coordinator, subentry_id, float(initial))
        cam_name = coordinator.camera
        self._attr_unique_id = f"fem_{cam_name}_debounce"

    async def async_set_native_value(self, value: float) -> None:
        """Update the debounce on the coordinator live."""
        self._attr_native_value = value
        self._apply_value(int(value))
        self.async_write_ha_state()

    def _apply_value(self, value: int) -> None:
        self.coordinator.set_debounce(value)
