"""Tests du bouton silencieux par caméra."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from custom_components.frigate_event_manager.button import CancelSilentButton, SilentButton
from custom_components.frigate_event_manager.const import DOMAIN

_NOOP = "homeassistant.helpers.update_coordinator.CoordinatorEntity.__init__"
_SUBENTRY_ID = "sub_jardin"


def _make_coordinator(cam_name: str = "jardin") -> MagicMock:
    """Crée un coordinator mock pour les tests du bouton."""
    coordinator = MagicMock()
    coordinator.camera = cam_name
    return coordinator


def _build(cam_name: str = "jardin", subentry_id: str = _SUBENTRY_ID) -> SilentButton:
    """Helper : instancie SilentButton avec mock coordinator + patch CoordinatorEntity."""
    coordinator = _make_coordinator(cam_name)
    with patch(_NOOP, return_value=None):
        btn = SilentButton(coordinator, subentry_id)
    btn.coordinator = coordinator
    return btn


# ---------------------------------------------------------------------------
# Tests SilentButton
# ---------------------------------------------------------------------------


class TestSilentButton:
    def test_unique_id_format(self) -> None:
        """unique_id suit le format fem_{cam}_silent."""
        btn = _build("jardin")
        assert btn._attr_unique_id == "fem_jardin_silent"

    def test_unique_id_autre_camera(self) -> None:
        """unique_id est unique par caméra."""
        btn = _build("garage")
        assert btn._attr_unique_id == "fem_garage_silent"

    def test_device_info_identifiers(self) -> None:
        """device_info pointe sur la bonne subentry."""
        btn = _build("jardin", "sub_jardin")
        assert (DOMAIN, "sub_jardin") in btn._attr_device_info["identifiers"]

    def test_translation_key(self) -> None:
        """translation_key est 'silent_button'."""
        btn = _build()
        assert btn._attr_translation_key == "silent_button"

    def test_icon(self) -> None:
        """Icône mdi:bell-sleep."""
        btn = _build()
        assert btn._attr_icon == "mdi:bell-sleep"

    def test_has_entity_name(self) -> None:
        """has_entity_name est True."""
        btn = _build()
        assert btn._attr_has_entity_name is True

    def test_device_info_nom_camera(self) -> None:
        """device_info contient le nom de la caméra."""
        btn = _build("terrasse")
        assert btn._attr_device_info["name"] == "Caméra terrasse"

    async def test_async_press_appelle_activate_silent_mode(self) -> None:
        """async_press appelle activate_silent_mode sur le coordinator."""
        btn = _build("jardin")
        await btn.async_press()
        btn.coordinator.activate_silent_mode.assert_called_once()

    async def test_async_press_different_cameras(self) -> None:
        """Chaque bouton appelle son propre coordinator."""
        btn1 = _build("jardin", "sub_jardin")
        btn2 = _build("garage", "sub_garage")

        await btn1.async_press()
        await btn2.async_press()

        btn1.coordinator.activate_silent_mode.assert_called_once()
        btn2.coordinator.activate_silent_mode.assert_called_once()

    async def test_async_press_ne_crashe_pas_deux_fois(self) -> None:
        """Plusieurs appuis successifs fonctionnent sans erreur."""
        btn = _build()
        await btn.async_press()
        await btn.async_press()
        assert btn.coordinator.activate_silent_mode.call_count == 2


# ---------------------------------------------------------------------------
# Tests CancelSilentButton
# ---------------------------------------------------------------------------


def _build_cancel(
    cam_name: str = "jardin", subentry_id: str = _SUBENTRY_ID
) -> CancelSilentButton:
    """Helper : instancie CancelSilentButton avec mock coordinator + patch CoordinatorEntity."""
    coordinator = _make_coordinator(cam_name)
    with patch(_NOOP, return_value=None):
        btn = CancelSilentButton(coordinator, subentry_id)
    btn.coordinator = coordinator
    btn.coordinator.async_cancel_silent = AsyncMock()
    return btn


class TestCancelSilentButton:
    def test_unique_id_format(self) -> None:
        """unique_id suit le format fem_{cam}_cancel_silent."""
        btn = _build_cancel("jardin")
        assert btn._attr_unique_id == "fem_jardin_cancel_silent"

    def test_unique_id_autre_camera(self) -> None:
        """unique_id est unique par caméra."""
        btn = _build_cancel("garage")
        assert btn._attr_unique_id == "fem_garage_cancel_silent"

    def test_device_info_identifiers(self) -> None:
        """device_info pointe sur la bonne subentry."""
        btn = _build_cancel("jardin", "sub_jardin")
        assert (DOMAIN, "sub_jardin") in btn._attr_device_info["identifiers"]

    def test_device_info_nom_camera(self) -> None:
        """device_info contient le nom de la caméra."""
        btn = _build_cancel("terrasse")
        assert btn._attr_device_info["name"] == "Caméra terrasse"

    def test_translation_key(self) -> None:
        """translation_key est 'cancel_silent_button'."""
        btn = _build_cancel()
        assert btn._attr_translation_key == "cancel_silent_button"

    def test_icon(self) -> None:
        """Icône mdi:bell-cancel."""
        btn = _build_cancel()
        assert btn._attr_icon == "mdi:bell-cancel"

    async def test_async_press_appelle_async_cancel_silent(self) -> None:
        """async_press appelle async_cancel_silent sur le coordinator."""
        btn = _build_cancel("jardin")
        await btn.async_press()
        btn.coordinator.async_cancel_silent.assert_called_once()
