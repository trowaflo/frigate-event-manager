"""Tests for select entities — notification action buttons (T-532)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.frigate_event_manager.const import (
    ACTION_BTN_OPTIONS,
    DEFAULT_ACTION_BTN,
    DOMAIN,
)
from custom_components.frigate_event_manager.select import (
    ActionButton1Select,
    ActionButton2Select,
    ActionButton3Select,
    _ActionButtonSelectBase,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_NOOP = "homeassistant.helpers.update_coordinator.CoordinatorEntity.__init__"
_NOOP_COORD_ADDED = "homeassistant.helpers.update_coordinator.CoordinatorEntity.async_added_to_hass"
_NOOP_RESTORE = "homeassistant.helpers.restore_state.RestoreEntity.async_added_to_hass"
_SUBENTRY_ID = "sub_jardin"


def _make_coordinator(cam_name: str = "jardin") -> MagicMock:
    coordinator = MagicMock()
    coordinator.camera = cam_name
    return coordinator


def _build_btn1(cam_name: str = "jardin", initial: str = DEFAULT_ACTION_BTN) -> ActionButton1Select:
    coordinator = _make_coordinator(cam_name)
    with patch(_NOOP, return_value=None):
        entity = ActionButton1Select(coordinator, _SUBENTRY_ID, initial)
    entity.coordinator = coordinator
    return entity


def _build_btn2(cam_name: str = "jardin", initial: str = DEFAULT_ACTION_BTN) -> ActionButton2Select:
    coordinator = _make_coordinator(cam_name)
    with patch(_NOOP, return_value=None):
        entity = ActionButton2Select(coordinator, _SUBENTRY_ID, initial)
    entity.coordinator = coordinator
    return entity


def _build_btn3(cam_name: str = "jardin", initial: str = DEFAULT_ACTION_BTN) -> ActionButton3Select:
    coordinator = _make_coordinator(cam_name)
    with patch(_NOOP, return_value=None):
        entity = ActionButton3Select(coordinator, _SUBENTRY_ID, initial)
    entity.coordinator = coordinator
    return entity


async def _call_added(entity: object, last_state: object) -> None:
    """Call async_added_to_hass with the correct patches."""
    with patch(_NOOP_COORD_ADDED, new_callable=AsyncMock):
        with patch(_NOOP_RESTORE, new_callable=AsyncMock):
            with patch.object(
                entity,  # type: ignore[arg-type]
                "async_get_last_state",
                new_callable=AsyncMock,
                return_value=last_state,
            ):
                await entity.async_added_to_hass()  # type: ignore[union-attr]


# ---------------------------------------------------------------------------
# Tests ActionButton1Select
# ---------------------------------------------------------------------------


class TestActionButton1Select:
    """Tests for the ActionButton1Select entity."""

    def test_unique_id(self) -> None:
        entity = _build_btn1()
        assert entity._attr_unique_id == "fem_jardin_action_btn1"

    def test_unique_id_autre_camera(self) -> None:
        entity = _build_btn1("garage")
        assert entity._attr_unique_id == "fem_garage_action_btn1"

    def test_valeur_initiale_defaut(self) -> None:
        entity = _build_btn1()
        assert entity._attr_current_option == DEFAULT_ACTION_BTN

    def test_valeur_initiale_clip(self) -> None:
        entity = _build_btn1(initial="clip")
        assert entity._attr_current_option == "clip"

    def test_valeur_initiale_invalide_retourne_none(self) -> None:
        """An invalid initial value is replaced by 'none'."""
        entity = _build_btn1(initial="invalide")
        assert entity._attr_current_option == DEFAULT_ACTION_BTN

    def test_options_contient_toutes_les_options(self) -> None:
        entity = _build_btn1()
        assert entity._attr_options == ACTION_BTN_OPTIONS

    def test_icon(self) -> None:
        entity = _build_btn1()
        assert entity._attr_icon == "mdi:gesture-tap-button"

    def test_translation_key(self) -> None:
        entity = _build_btn1()
        assert entity._attr_translation_key == "action_btn1"

    def test_device_info_contient_domaine(self) -> None:
        entity = _build_btn1()
        assert (DOMAIN, _SUBENTRY_ID) in entity._attr_device_info["identifiers"]

    async def test_select_option_appelle_set_action_btn1(self) -> None:
        entity = _build_btn1()
        entity.async_write_ha_state = MagicMock()
        await entity.async_select_option("clip")
        entity.coordinator.set_action_btn1.assert_called_once_with("clip")
        assert entity._attr_current_option == "clip"

    async def test_select_option_met_a_jour_current_option(self) -> None:
        entity = _build_btn1()
        entity.async_write_ha_state = MagicMock()
        await entity.async_select_option("dismiss")
        assert entity._attr_current_option == "dismiss"

    async def test_async_added_restaure_etat_valide(self) -> None:
        entity = _build_btn1()
        state = MagicMock()
        state.state = "snapshot"
        await _call_added(entity, state)
        assert entity._attr_current_option == "snapshot"
        entity.coordinator.set_action_btn1.assert_called_once_with("snapshot")

    async def test_async_added_ignore_etat_invalide(self) -> None:
        entity = _build_btn1()
        state = MagicMock()
        state.state = "invalide"
        await _call_added(entity, state)
        # The invalid state is not applied — the initial value (none) is preserved
        assert entity._attr_current_option == DEFAULT_ACTION_BTN
        entity.coordinator.set_action_btn1.assert_not_called()

    async def test_async_added_sans_etat_precedent(self) -> None:
        entity = _build_btn1(initial="preview")
        await _call_added(entity, None)
        assert entity._attr_current_option == "preview"
        entity.coordinator.set_action_btn1.assert_not_called()


# ---------------------------------------------------------------------------
# Tests ActionButton2Select
# ---------------------------------------------------------------------------


class TestActionButton2Select:
    """Tests for the ActionButton2Select entity."""

    def test_unique_id(self) -> None:
        entity = _build_btn2()
        assert entity._attr_unique_id == "fem_jardin_action_btn2"

    def test_translation_key(self) -> None:
        entity = _build_btn2()
        assert entity._attr_translation_key == "action_btn2"

    async def test_select_option_appelle_set_action_btn2(self) -> None:
        entity = _build_btn2()
        entity.async_write_ha_state = MagicMock()
        await entity.async_select_option("silent_30min")
        entity.coordinator.set_action_btn2.assert_called_once_with("silent_30min")


# ---------------------------------------------------------------------------
# Tests ActionButton3Select
# ---------------------------------------------------------------------------


class TestActionButton3Select:
    """Tests for the ActionButton3Select entity."""

    def test_unique_id(self) -> None:
        entity = _build_btn3()
        assert entity._attr_unique_id == "fem_jardin_action_btn3"

    def test_translation_key(self) -> None:
        entity = _build_btn3()
        assert entity._attr_translation_key == "action_btn3"

    async def test_select_option_appelle_set_action_btn3(self) -> None:
        entity = _build_btn3()
        entity.async_write_ha_state = MagicMock()
        await entity.async_select_option("silent_1h")
        entity.coordinator.set_action_btn3.assert_called_once_with("silent_1h")


# ---------------------------------------------------------------------------
# Tests options valides pour tous les boutons
# ---------------------------------------------------------------------------


class TestActionBtnOptions:
    """Verifies that all options are supported."""

    @pytest.mark.parametrize("option", ACTION_BTN_OPTIONS)
    def test_toutes_options_valides_acceptees_btn1(self, option: str) -> None:
        entity = _build_btn1(initial=option)
        assert entity._attr_current_option == option

    @pytest.mark.parametrize("option", ACTION_BTN_OPTIONS)
    async def test_toutes_options_selectionables_btn1(self, option: str) -> None:
        entity = _build_btn1()
        entity.async_write_ha_state = MagicMock()
        await entity.async_select_option(option)
        assert entity._attr_current_option == option


# ---------------------------------------------------------------------------
# Tests _ActionButtonSelectBase — NotImplementedError (T-532c)
# ---------------------------------------------------------------------------


class TestActionButtonSelectBaseNotImplemented:
    """Verifies that the base class raises NotImplementedError."""

    def test_apply_to_coordinator_leve_not_implemented(self) -> None:
        """_apply_to_coordinator must raise NotImplementedError in the base class."""
        coordinator = _make_coordinator()
        with patch(_NOOP, return_value=None):
            # Direct instantiation of the abstract base class
            entity = _ActionButtonSelectBase.__new__(_ActionButtonSelectBase)
            entity.coordinator = coordinator
            entity._btn_key = "test_key"
            entity._attr_current_option = DEFAULT_ACTION_BTN
            entity._attr_unique_id = "fem_test_test_key"

        with pytest.raises(NotImplementedError):
            entity._apply_to_coordinator("clip")


# ---------------------------------------------------------------------------
# Tests async_setup_entry select (T-532c)
# ---------------------------------------------------------------------------


async def test_async_setup_entry_nenregistre_aucune_entite() -> None:
    """async_setup_entry creates no entity — action buttons are in the config flow."""
    from custom_components.frigate_event_manager.select import async_setup_entry

    mock_add_entities = MagicMock()
    await async_setup_entry(MagicMock(), MagicMock(), mock_add_entities)
    mock_add_entities.assert_not_called()
