"""Entités select — boutons d'action notification par caméra."""

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
    CONF_ACTION_BTN1,
    CONF_ACTION_BTN2,
    CONF_ACTION_BTN3,
    DEFAULT_ACTION_BTN,
    DEFAULT_SEVERITY,
    DEFAULT_TAP_ACTION,
    DOMAIN,
    SEVERITY_OPTIONS,
    SUBENTRY_TYPE_CAMERA,
    TAP_ACTION_OPTIONS,
)
from .coordinator import FrigateEventManagerCoordinator

# Option pour "alert et detection" dans le select mono-valeur
_SEVERITY_BOTH = "alert,detection"

# Mapping option UI → liste de sévérités
_SEVERITY_UI_TO_LIST: dict[str, list[str]] = {
    "alert": ["alert"],
    "detection": ["detection"],
    _SEVERITY_BOTH: ["alert", "detection"],
}

# Mapping liste de sévérités → option UI (lookup inverse)
def _severity_list_to_ui(severities: list[str]) -> str:
    """Convertit une liste de sévérités en option UI mono-valeur."""
    s = sorted(severities)
    if s == ["alert"]:
        return "alert"
    if s == ["detection"]:
        return "detection"
    # cas par défaut : les deux
    return _SEVERITY_BOTH


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FEMConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Crée les entités select boutons d'action par caméra."""
    entities = []
    for subentry_id, subentry in entry.subentries.items():
        if subentry.subentry_type != SUBENTRY_TYPE_CAMERA:
            continue
        coordinator = entry.runtime_data.get(subentry_id)
        if coordinator is None:
            continue
        entities.extend([
            ActionButton1Select(
                coordinator,
                subentry_id,
                subentry.data.get(CONF_ACTION_BTN1, DEFAULT_ACTION_BTN),
            ),
            ActionButton2Select(
                coordinator,
                subentry_id,
                subentry.data.get(CONF_ACTION_BTN2, DEFAULT_ACTION_BTN),
            ),
            ActionButton3Select(
                coordinator,
                subentry_id,
                subentry.data.get(CONF_ACTION_BTN3, DEFAULT_ACTION_BTN),
            ),
        ])
    async_add_entities(entities)


class SeverityFilterSelect(
    CoordinatorEntity[FrigateEventManagerCoordinator],
    SelectEntity,
    RestoreEntity,
):
    """Filtre de sévérité — Alert / Detection / Les deux."""

    _attr_has_entity_name = True
    _attr_translation_key = "severity_filter"
    _attr_icon = "mdi:filter-variant"

    # Options UI : alert seul, detection seul, les deux
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
        """Initialise le select de sévérité."""
        super().__init__(coordinator)
        cam_name = coordinator.camera
        self._attr_unique_id = f"fem_{cam_name}_severity"
        self._attr_current_option = _severity_list_to_ui(initial)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, subentry_id)},
            name=f"Caméra {cam_name}",
            manufacturer="Frigate",
            config_subentry_id=subentry_id,
        )

    async def async_added_to_hass(self) -> None:
        """Restaure la valeur depuis l'état précédent si disponible."""
        await super().async_added_to_hass()
        state = await self.async_get_last_state()
        if state is not None and state.state in self._attr_options:
            self._attr_current_option = state.state
            self.coordinator.set_severity(
                _SEVERITY_UI_TO_LIST.get(state.state, DEFAULT_SEVERITY)
            )

    async def async_select_option(self, option: str) -> None:
        """Met à jour le filtre de sévérité sur le coordinator en live."""
        self._attr_current_option = option
        self.coordinator.set_severity(_SEVERITY_UI_TO_LIST.get(option, DEFAULT_SEVERITY))
        self.async_write_ha_state()


class TapActionSelect(
    CoordinatorEntity[FrigateEventManagerCoordinator],
    SelectEntity,
    RestoreEntity,
):
    """Action au tap de la notification (clip / snapshot / preview)."""

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
        """Initialise le select d'action au tap."""
        super().__init__(coordinator)
        cam_name = coordinator.camera
        self._attr_unique_id = f"fem_{cam_name}_tap_action"
        self._attr_current_option = initial if initial in TAP_ACTION_OPTIONS else DEFAULT_TAP_ACTION
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, subentry_id)},
            name=f"Caméra {cam_name}",
            manufacturer="Frigate",
            config_subentry_id=subentry_id,
        )

    async def async_added_to_hass(self) -> None:
        """Restaure la valeur depuis l'état précédent si disponible."""
        await super().async_added_to_hass()
        state = await self.async_get_last_state()
        if state is not None and state.state in TAP_ACTION_OPTIONS:
            self._attr_current_option = state.state
            self.coordinator.set_tap_action(state.state)

    async def async_select_option(self, option: str) -> None:
        """Met à jour l'action au tap sur le coordinator en live."""
        self._attr_current_option = option
        self.coordinator.set_tap_action(option)
        self.async_write_ha_state()


class _ActionButtonSelectBase(
    CoordinatorEntity[FrigateEventManagerCoordinator],
    SelectEntity,
    RestoreEntity,
):
    """Classe de base pour les selects boutons d'action notification."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:gesture-tap-button"
    _attr_options = ACTION_BTN_OPTIONS

    # À surcharger dans les sous-classes
    _btn_key: str = ""

    def __init__(
        self,
        coordinator: FrigateEventManagerCoordinator,
        subentry_id: str,
        initial: str,
    ) -> None:
        """Initialise le select bouton d'action."""
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
            config_subentry_id=subentry_id,
        )

    async def async_added_to_hass(self) -> None:
        """Restaure la valeur depuis l'état précédent si disponible."""
        await super().async_added_to_hass()
        state = await self.async_get_last_state()
        if state is not None and state.state in ACTION_BTN_OPTIONS:
            self._attr_current_option = state.state
            self._apply_to_coordinator(state.state)

    def _apply_to_coordinator(self, option: str) -> None:
        """Délègue la valeur au coordinator — surchargé par chaque sous-classe."""
        raise NotImplementedError

    async def async_select_option(self, option: str) -> None:
        """Met à jour le bouton d'action sur le coordinator en live."""
        self._attr_current_option = option
        self._apply_to_coordinator(option)
        self.async_write_ha_state()


class ActionButton1Select(_ActionButtonSelectBase):
    """Bouton d'action n°1 dans les notifications."""

    _attr_translation_key = "action_btn1"
    _btn_key = "action_btn1"

    def _apply_to_coordinator(self, option: str) -> None:
        self.coordinator.set_action_btn1(option)


class ActionButton2Select(_ActionButtonSelectBase):
    """Bouton d'action n°2 dans les notifications."""

    _attr_translation_key = "action_btn2"
    _btn_key = "action_btn2"

    def _apply_to_coordinator(self, option: str) -> None:
        self.coordinator.set_action_btn2(option)


class ActionButton3Select(_ActionButtonSelectBase):
    """Bouton d'action n°3 dans les notifications."""

    _attr_translation_key = "action_btn3"
    _btn_key = "action_btn3"

    def _apply_to_coordinator(self, option: str) -> None:
        self.coordinator.set_action_btn3(option)
