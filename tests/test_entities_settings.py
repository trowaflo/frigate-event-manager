"""Tests des entités de réglage — number, select, text."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from custom_components.frigate_event_manager.const import (
    DEFAULT_DEBOUNCE,
    DEFAULT_SEVERITY,
    DEFAULT_TAP_ACTION,
    DEFAULT_THROTTLE_COOLDOWN,
    DOMAIN,
)
from custom_components.frigate_event_manager.number import CooldownNumber, DebounceNumber
from custom_components.frigate_event_manager.select import (
    SeverityFilterSelect,
    TapActionSelect,
    _SEVERITY_BOTH,
    _severity_list_to_ui,
)
from custom_components.frigate_event_manager.text import (
    CriticalTemplateText,
    NotifMessageText,
    NotifTitleText,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_NOOP = "homeassistant.helpers.update_coordinator.CoordinatorEntity.__init__"
_NOOP_COORD_ADDED = "homeassistant.helpers.update_coordinator.CoordinatorEntity.async_added_to_hass"
_NOOP_RESTORE = "homeassistant.helpers.restore_state.RestoreEntity.async_added_to_hass"
_SUBENTRY_ID = "sub_test"


def _make_coordinator(cam_name: str = "jardin") -> MagicMock:
    coordinator = MagicMock()
    coordinator.camera = cam_name
    return coordinator


async def _call_added(entity: object, last_state: object) -> None:
    """Appelle async_added_to_hass avec les bons patches CoordinatorEntity + RestoreEntity."""
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
# Helpers utilitaires select
# ---------------------------------------------------------------------------


class TestSeverityListToUi:
    """Tests de la fonction _severity_list_to_ui."""

    def test_alert_seul(self) -> None:
        assert _severity_list_to_ui(["alert"]) == "alert"

    def test_detection_seul(self) -> None:
        assert _severity_list_to_ui(["detection"]) == "detection"

    def test_les_deux_ordres_varies(self) -> None:
        assert _severity_list_to_ui(["alert", "detection"]) == _SEVERITY_BOTH
        assert _severity_list_to_ui(["detection", "alert"]) == _SEVERITY_BOTH

    def test_liste_vide_retourne_both(self) -> None:
        assert _severity_list_to_ui([]) == _SEVERITY_BOTH


# ---------------------------------------------------------------------------
# CooldownNumber
# ---------------------------------------------------------------------------


class TestCooldownNumber:
    """Tests de l'entité CooldownNumber."""

    def _build(self, initial: int = DEFAULT_THROTTLE_COOLDOWN) -> CooldownNumber:
        coordinator = _make_coordinator()
        with patch(_NOOP):
            entity = CooldownNumber(coordinator, _SUBENTRY_ID, initial)
        entity.coordinator = coordinator
        return entity

    def test_unique_id(self) -> None:
        entity = self._build()
        assert entity._attr_unique_id == "fem_jardin_cooldown"

    def test_valeur_initiale(self) -> None:
        entity = self._build(initial=120)
        assert entity._attr_native_value == 120.0

    def test_limites(self) -> None:
        entity = self._build()
        assert entity._attr_native_min_value == 0
        assert entity._attr_native_max_value == 3600

    def test_device_info_contient_domaine(self) -> None:
        entity = self._build()
        assert (DOMAIN, _SUBENTRY_ID) in entity._attr_device_info["identifiers"]

    async def test_set_native_value_appelle_set_cooldown(self) -> None:
        entity = self._build()
        entity.async_write_ha_state = MagicMock()
        await entity.async_set_native_value(90.0)
        entity.coordinator.set_cooldown.assert_called_once_with(90)
        assert entity._attr_native_value == 90.0

    async def test_async_added_to_hass_sans_etat_precedent(self) -> None:
        """Sans état précédent, la valeur initiale est conservée."""
        entity = self._build(initial=60)
        await _call_added(entity, None)
        assert entity._attr_native_value == 60.0

    async def test_async_added_to_hass_restaure_valeur(self) -> None:
        """Avec état précédent valide, la valeur est restaurée."""
        entity = self._build(initial=60)
        mock_state = MagicMock()
        mock_state.state = "180"
        await _call_added(entity, mock_state)
        assert entity._attr_native_value == 180.0
        entity.coordinator.set_cooldown.assert_called_once_with(180)


# ---------------------------------------------------------------------------
# DebounceNumber
# ---------------------------------------------------------------------------


class TestDebounceNumber:
    """Tests de l'entité DebounceNumber."""

    def _build(self, initial: int = DEFAULT_DEBOUNCE) -> DebounceNumber:
        coordinator = _make_coordinator()
        with patch(_NOOP):
            entity = DebounceNumber(coordinator, _SUBENTRY_ID, initial)
        entity.coordinator = coordinator
        return entity

    def test_unique_id(self) -> None:
        entity = self._build()
        assert entity._attr_unique_id == "fem_jardin_debounce"

    def test_limites(self) -> None:
        entity = self._build()
        assert entity._attr_native_max_value == 60

    async def test_set_native_value_appelle_set_debounce(self) -> None:
        entity = self._build()
        entity.async_write_ha_state = MagicMock()
        await entity.async_set_native_value(5.0)
        entity.coordinator.set_debounce.assert_called_once_with(5)

    async def test_async_added_to_hass_etat_invalide_ignore(self) -> None:
        """État précédent non numérique → valeur initiale conservée."""
        entity = self._build(initial=10)
        mock_state = MagicMock()
        mock_state.state = "invalid"
        await _call_added(entity, mock_state)
        assert entity._attr_native_value == 10.0


# ---------------------------------------------------------------------------
# SeverityFilterSelect
# ---------------------------------------------------------------------------


class TestSeverityFilterSelect:
    """Tests de l'entité SeverityFilterSelect."""

    def _build(self, initial: list[str] | None = None) -> SeverityFilterSelect:
        coordinator = _make_coordinator()
        with patch(_NOOP):
            entity = SeverityFilterSelect(coordinator, _SUBENTRY_ID, initial or DEFAULT_SEVERITY)
        entity.coordinator = coordinator
        return entity

    def test_unique_id(self) -> None:
        entity = self._build()
        assert entity._attr_unique_id == "fem_jardin_severity"

    def test_options_contiennent_les_trois_valeurs(self) -> None:
        entity = self._build()
        assert "alert" in entity._attr_options
        assert "detection" in entity._attr_options
        assert _SEVERITY_BOTH in entity._attr_options

    def test_valeur_initiale_alert_seul(self) -> None:
        entity = self._build(initial=["alert"])
        assert entity._attr_current_option == "alert"

    def test_valeur_initiale_les_deux(self) -> None:
        entity = self._build(initial=["alert", "detection"])
        assert entity._attr_current_option == _SEVERITY_BOTH

    async def test_select_option_alert_appelle_set_severity(self) -> None:
        entity = self._build()
        entity.async_write_ha_state = MagicMock()
        await entity.async_select_option("alert")
        entity.coordinator.set_severity.assert_called_once_with(["alert"])
        assert entity._attr_current_option == "alert"

    async def test_select_option_both_passe_les_deux(self) -> None:
        entity = self._build()
        entity.async_write_ha_state = MagicMock()
        await entity.async_select_option(_SEVERITY_BOTH)
        entity.coordinator.set_severity.assert_called_once_with(["alert", "detection"])

    async def test_async_added_to_hass_restaure_option_valide(self) -> None:
        entity = self._build(initial=["alert", "detection"])
        mock_state = MagicMock()
        mock_state.state = "detection"
        await _call_added(entity, mock_state)
        assert entity._attr_current_option == "detection"
        entity.coordinator.set_severity.assert_called_once_with(["detection"])

    async def test_async_added_to_hass_option_invalide_ignore(self) -> None:
        """Option inconnue → valeur initiale conservée, pas d'appel set_severity."""
        entity = self._build(initial=["alert"])
        mock_state = MagicMock()
        mock_state.state = "invalide_inconnu"
        await _call_added(entity, mock_state)
        assert entity._attr_current_option == "alert"
        entity.coordinator.set_severity.assert_not_called()


# ---------------------------------------------------------------------------
# TapActionSelect
# ---------------------------------------------------------------------------


class TestTapActionSelect:
    """Tests de l'entité TapActionSelect."""

    def _build(self, initial: str = DEFAULT_TAP_ACTION) -> TapActionSelect:
        coordinator = _make_coordinator()
        with patch(_NOOP):
            entity = TapActionSelect(coordinator, _SUBENTRY_ID, initial)
        entity.coordinator = coordinator
        return entity

    def test_unique_id(self) -> None:
        entity = self._build()
        assert entity._attr_unique_id == "fem_jardin_tap_action"

    def test_valeur_initiale_clip(self) -> None:
        entity = self._build(initial="clip")
        assert entity._attr_current_option == "clip"

    def test_valeur_initiale_invalide_bascule_sur_defaut(self) -> None:
        entity = self._build(initial="invalide")
        assert entity._attr_current_option == DEFAULT_TAP_ACTION

    async def test_select_option_snapshot(self) -> None:
        entity = self._build()
        entity.async_write_ha_state = MagicMock()
        await entity.async_select_option("snapshot")
        entity.coordinator.set_tap_action.assert_called_once_with("snapshot")
        assert entity._attr_current_option == "snapshot"

    async def test_async_added_to_hass_restaure_preview(self) -> None:
        entity = self._build(initial="clip")
        mock_state = MagicMock()
        mock_state.state = "preview"
        await _call_added(entity, mock_state)
        assert entity._attr_current_option == "preview"
        entity.coordinator.set_tap_action.assert_called_once_with("preview")


# ---------------------------------------------------------------------------
# NotifTitleText
# ---------------------------------------------------------------------------


class TestNotifTitleText:
    """Tests de l'entité NotifTitleText."""

    def _build(self, initial: str = "") -> NotifTitleText:
        coordinator = _make_coordinator()
        with patch(_NOOP):
            entity = NotifTitleText(coordinator, _SUBENTRY_ID, initial)
        entity.coordinator = coordinator
        return entity

    def test_unique_id(self) -> None:
        entity = self._build()
        assert entity._attr_unique_id == "fem_jardin_notif_title"

    def test_valeur_initiale(self) -> None:
        entity = self._build(initial="Alerte {{ camera }}")
        assert entity._attr_native_value == "Alerte {{ camera }}"

    async def test_set_value_appelle_set_notif_title(self) -> None:
        entity = self._build()
        entity.async_write_ha_state = MagicMock()
        await entity.async_set_value("Mon titre")
        entity.coordinator.set_notif_title.assert_called_once_with("Mon titre")

    async def test_set_value_vide_passe_none(self) -> None:
        entity = self._build(initial="titre")
        entity.async_write_ha_state = MagicMock()
        await entity.async_set_value("")
        entity.coordinator.set_notif_title.assert_called_once_with(None)

    async def test_async_added_to_hass_restaure_valeur(self) -> None:
        entity = self._build()
        mock_state = MagicMock()
        mock_state.state = "Caméra {{ camera }}"
        await _call_added(entity, mock_state)
        assert entity._attr_native_value == "Caméra {{ camera }}"
        entity.coordinator.set_notif_title.assert_called_once_with("Caméra {{ camera }}")

    async def test_async_added_to_hass_etat_unknown_ignore(self) -> None:
        entity = self._build(initial="titre initial")
        mock_state = MagicMock()
        mock_state.state = "unknown"
        await _call_added(entity, mock_state)
        assert entity._attr_native_value == "titre initial"

    async def test_async_added_to_hass_sans_etat_precedent(self) -> None:
        entity = self._build(initial="défaut")
        await _call_added(entity, None)
        assert entity._attr_native_value == "défaut"


# ---------------------------------------------------------------------------
# NotifMessageText
# ---------------------------------------------------------------------------


class TestNotifMessageText:
    """Tests de l'entité NotifMessageText."""

    def _build(self, initial: str = "") -> NotifMessageText:
        coordinator = _make_coordinator()
        with patch(_NOOP):
            entity = NotifMessageText(coordinator, _SUBENTRY_ID, initial)
        entity.coordinator = coordinator
        return entity

    def test_unique_id(self) -> None:
        entity = self._build()
        assert entity._attr_unique_id == "fem_jardin_notif_message"

    async def test_set_value_appelle_set_notif_message(self) -> None:
        entity = self._build()
        entity.async_write_ha_state = MagicMock()
        await entity.async_set_value("Mon message")
        entity.coordinator.set_notif_message.assert_called_once_with("Mon message")

    async def test_set_value_vide_passe_none(self) -> None:
        entity = self._build(initial="msg")
        entity.async_write_ha_state = MagicMock()
        await entity.async_set_value("")
        entity.coordinator.set_notif_message.assert_called_once_with(None)

    async def test_async_added_to_hass_restaure_valeur(self) -> None:
        entity = self._build()
        mock_state = MagicMock()
        mock_state.state = "{{ objects | join(', ') }}"
        await _call_added(entity, mock_state)
        assert entity._attr_native_value == "{{ objects | join(', ') }}"
        entity.coordinator.set_notif_message.assert_called_once_with("{{ objects | join(', ') }}")


# ---------------------------------------------------------------------------
# CriticalTemplateText
# ---------------------------------------------------------------------------


class TestCriticalTemplateText:
    """Tests de l'entité CriticalTemplateText."""

    def _build(self, initial: str = "") -> CriticalTemplateText:
        coordinator = _make_coordinator()
        with patch(_NOOP):
            entity = CriticalTemplateText(coordinator, _SUBENTRY_ID, initial)
        entity.coordinator = coordinator
        return entity

    def test_unique_id(self) -> None:
        entity = self._build()
        assert entity._attr_unique_id == "fem_jardin_critical_template"

    async def test_set_value_appelle_set_critical_template(self) -> None:
        entity = self._build()
        entity.async_write_ha_state = MagicMock()
        await entity.async_set_value("{{ severity == 'alert' }}")
        entity.coordinator.set_critical_template.assert_called_once_with("{{ severity == 'alert' }}")

    async def test_set_value_vide_passe_none(self) -> None:
        entity = self._build(initial="tpl")
        entity.async_write_ha_state = MagicMock()
        await entity.async_set_value("")
        entity.coordinator.set_critical_template.assert_called_once_with(None)

    async def test_async_added_to_hass_etat_unavailable_ignore(self) -> None:
        entity = self._build(initial="{{ severity == 'alert' }}")
        mock_state = MagicMock()
        mock_state.state = "unavailable"
        await _call_added(entity, mock_state)
        assert entity._attr_native_value == "{{ severity == 'alert' }}"

    async def test_async_added_to_hass_restaure_template(self) -> None:
        entity = self._build()
        mock_state = MagicMock()
        mock_state.state = "{{ severity == 'alert' }}"
        await _call_added(entity, mock_state)
        assert entity._attr_native_value == "{{ severity == 'alert' }}"
        entity.coordinator.set_critical_template.assert_called_once_with("{{ severity == 'alert' }}")
