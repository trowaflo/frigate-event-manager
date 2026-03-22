"""Select entities — notification action buttons per camera."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import FEMConfigEntry
from .const import (
    ACTION_BTN_OPTIONS,
    DEFAULT_ACTION_BTN,
    DEFAULT_SEVERITY,
    DEFAULT_TAP_ACTION,
    DOMAIN,
    SEVERITY_OPTIONS,
    TAP_ACTION_OPTIONS,
)
from .coordinator import FrigateEventManagerCoordinator

# Option for "alert and detection" in the single-value select
_SEVERITY_BOTH = "alert,detection"

# Mapping UI option → severity list
_SEVERITY_UI_TO_LIST: dict[str, list[str]] = {
    "alert": ["alert"],
    "detection": ["detection"],
    _SEVERITY_BOTH: ["alert", "detection"],
}

# Mapping severity list → UI option (reverse lookup)
def _severity_list_to_ui(severities: list[str]) -> str:
    """Convert a severity list to a single-value UI option."""
    s = sorted(severities)
    if s == ["alert"]:
        return "alert"
    if s == ["detection"]:
        return "detection"
    # default case: both
    return _SEVERITY_BOTH


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FEMConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """No select entity created — action buttons managed in config flow."""


class SeverityFilterSelect(
    CoordinatorEntity[FrigateEventManagerCoordinator],
    SelectEntity,
    RestoreEntity,
):
    """Severity filter — Alert / Detection / Both."""

    _attr_has_entity_name = True
    _attr_translation_key = "severity_filter"
    _attr_icon = "mdi:filter-variant"

    # UI options: alert only, detection only, both
    _attr_options = [
        *SEVERITY_OPTIONS,
        _SEVERITY_BOTH,
    ]

    def __init__(
        self,
        coordinator: FrigateEventManagerCoordinator,
        subentry_id: str,
        initial: list[str],
    ) -> None:
        """Initialize the severity select."""
        super().__init__(coordinator)
        cam_name = coordinator.camera
        self._attr_unique_id = f"fem_{cam_name}_severity"
        self._attr_current_option = _severity_list_to_ui(initial)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, subentry_id)},
            name=f"Caméra {cam_name}",
            manufacturer="Frigate",
        )

    async def async_added_to_hass(self) -> None:
        """Restore value from previous state if available."""
        await super().async_added_to_hass()
        state = await self.async_get_last_state()
        if state is not None and state.state in self._attr_options:
            self._attr_current_option = state.state
            self.coordinator.set_severity(
                _SEVERITY_UI_TO_LIST.get(state.state, DEFAULT_SEVERITY)
            )

    async def async_select_option(self, option: str) -> None:
        """Update the severity filter on the coordinator live."""
        self._attr_current_option = option
        self.coordinator.set_severity(_SEVERITY_UI_TO_LIST.get(option, DEFAULT_SEVERITY))
        self.async_write_ha_state()


class TapActionSelect(
    CoordinatorEntity[FrigateEventManagerCoordinator],
    SelectEntity,
    RestoreEntity,
):
    """Notification tap action (clip / snapshot / preview)."""

    _attr_has_entity_name = True
    _attr_translation_key = "tap_action"
    _attr_icon = "mdi:gesture-tap"
    _attr_options = TAP_ACTION_OPTIONS

    def __init__(
        self,
        coordinator: FrigateEventManagerCoordinator,
        subentry_id: str,
        initial: str,
    ) -> None:
        """Initialize the tap action select."""
        super().__init__(coordinator)
        cam_name = coordinator.camera
        self._attr_unique_id = f"fem_{cam_name}_tap_action"
        self._attr_current_option = initial if initial in TAP_ACTION_OPTIONS else DEFAULT_TAP_ACTION
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, subentry_id)},
            name=f"Caméra {cam_name}",
            manufacturer="Frigate",
        )

    async def async_added_to_hass(self) -> None:
        """Restore value from previous state if available."""
        await super().async_added_to_hass()
        state = await self.async_get_last_state()
        if state is not None and state.state in TAP_ACTION_OPTIONS:
            self._attr_current_option = state.state
            self.coordinator.set_tap_action(state.state)

    async def async_select_option(self, option: str) -> None:
        """Update the tap action on the coordinator live."""
        self._attr_current_option = option
        self.coordinator.set_tap_action(option)
        self.async_write_ha_state()


class _ActionButtonSelectBase(
    CoordinatorEntity[FrigateEventManagerCoordinator],
    SelectEntity,
    RestoreEntity,
):
    """Base class for notification action button selects."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:gesture-tap-button"
    _attr_options = ACTION_BTN_OPTIONS

    # To be overridden in subclasses
    _btn_key: str = ""

    def __init__(
        self,
        coordinator: FrigateEventManagerCoordinator,
        subentry_id: str,
        initial: str,
    ) -> None:
        """Initialize the action button select."""
        super().__init__(coordinator)
        cam_name = coordinator.camera
        self._attr_unique_id = f"fem_{cam_name}_{self._btn_key}"
        self._attr_current_option = (
            initial if initial in ACTION_BTN_OPTIONS else DEFAULT_ACTION_BTN
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, subentry_id)},
            name=f"Caméra {cam_name}",
            manufacturer="Frigate",
        )

    async def async_added_to_hass(self) -> None:
        """Restore value from previous state if available."""
        await super().async_added_to_hass()
        state = await self.async_get_last_state()
        if state is not None and state.state in ACTION_BTN_OPTIONS:
            self._attr_current_option = state.state
            self._apply_to_coordinator(state.state)

    def _apply_to_coordinator(self, option: str) -> None:
        """Delegate the value to the coordinator — overridden by each subclass."""
        raise NotImplementedError

    async def async_select_option(self, option: str) -> None:
        """Update the action button on the coordinator live."""
        self._attr_current_option = option
        self._apply_to_coordinator(option)
        self.async_write_ha_state()


class ActionButton1Select(_ActionButtonSelectBase):
    """Action button #1 in notifications."""

    _attr_translation_key = "action_btn1"
    _btn_key = "action_btn1"

    def _apply_to_coordinator(self, option: str) -> None:
        self.coordinator.set_action_btn1(option)


class ActionButton2Select(_ActionButtonSelectBase):
    """Action button #2 in notifications."""

    _attr_translation_key = "action_btn2"
    _btn_key = "action_btn2"

    def _apply_to_coordinator(self, option: str) -> None:
        self.coordinator.set_action_btn2(option)


class ActionButton3Select(_ActionButtonSelectBase):
    """Action button #3 in notifications."""

    _attr_translation_key = "action_btn3"
    _btn_key = "action_btn3"

    def _apply_to_coordinator(self, option: str) -> None:
        self.coordinator.set_action_btn3(option)
