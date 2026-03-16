"""Tests du coordinator MQTT Frigate Event Manager."""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.core import HomeAssistant

from custom_components.frigate_event_manager.const import (
    CONF_CAMERA,
    CONF_NOTIFY_TARGET,
    DEFAULT_MQTT_TOPIC,
)
from custom_components.frigate_event_manager.coordinator import (
    CameraState,
    FrigateEvent,
    FrigateEventManagerCoordinator,
    _parse_event,
)

# ---------------------------------------------------------------------------
# Payloads Frigate réalistes
# ---------------------------------------------------------------------------

PAYLOAD_NEW = {
    "type": "new",
    "after": {
        "camera": "jardin",
        "severity": "alert",
        "objects": ["personne"],
        "current_zones": ["entree"],
        "score": 0.92,
        "thumb_path": "/media/frigate/clips/jardin-abc123.jpg",
        "id": "review-001",
        "start_time": 1710000000.0,
        "end_time": None,
    },
}

PAYLOAD_UPDATE = {
    "type": "update",
    "after": {
        "camera": "jardin",
        "severity": "detection",
        "objects": ["chien"],
        "current_zones": [],
        "score": 0.75,
        "id": "review-002",
        "start_time": 1710000010.0,
        "end_time": None,
    },
}

PAYLOAD_END = {
    "type": "end",
    "after": {
        "camera": "jardin",
        "severity": "alert",
        "objects": ["personne"],
        "current_zones": ["entree"],
        "score": 0.88,
        "id": "review-003",
        "start_time": 1710000020.0,
        "end_time": 1710000060.0,
    },
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_entry(notify_target: str | None = None) -> MagicMock:
    """Crée un ConfigEntry mock minimal (globale)."""
    entry = MagicMock()
    entry.entry_id = "test-entry-id"
    entry.data = {}
    if notify_target:
        entry.data[CONF_NOTIFY_TARGET] = notify_target
    return entry


def _make_subentry(cam_name: str = "jardin", notify_target: str | None = None) -> MagicMock:
    """Crée un ConfigSubentry mock pour une caméra."""
    subentry = MagicMock()
    subentry.subentry_id = f"sub_{cam_name}"
    subentry.data = {CONF_CAMERA: cam_name}
    if notify_target:
        subentry.data[CONF_NOTIFY_TARGET] = notify_target
    return subentry


def _make_coordinator(
    hass: HomeAssistant,
    cam_name: str = "jardin",
    notify_target: str | None = None,
) -> FrigateEventManagerCoordinator:
    """Instancie un coordinator avec des mocks ConfigEntry + ConfigSubentry."""
    entry = _make_entry()
    subentry = _make_subentry(cam_name, notify_target)
    return FrigateEventManagerCoordinator(hass, entry, subentry)


def _make_msg(payload: dict | str) -> SimpleNamespace:
    """Crée un message MQTT fake."""
    if isinstance(payload, dict):
        payload = json.dumps(payload)
    return SimpleNamespace(payload=payload)


# ---------------------------------------------------------------------------
# Tests de _parse_event
# ---------------------------------------------------------------------------


class TestParseEvent:
    """Tests unitaires de _parse_event."""

    def test_type_new_payload_complet(self) -> None:
        result = _parse_event(json.dumps(PAYLOAD_NEW))

        assert result is not None
        assert isinstance(result, FrigateEvent)
        assert result.type == "new"
        assert result.camera == "jardin"
        assert result.severity == "alert"
        assert result.objects == ["personne"]
        assert result.zones == ["entree"]
        assert result.score == pytest.approx(0.92)
        assert result.review_id == "review-001"
        assert result.start_time == pytest.approx(1710000000.0)
        assert result.end_time is None

    def test_type_update_valide(self) -> None:
        result = _parse_event(json.dumps(PAYLOAD_UPDATE))

        assert result is not None
        assert result.type == "update"
        assert result.severity == "detection"
        assert result.objects == ["chien"]
        assert result.zones == []

    def test_type_end_expose_end_time(self) -> None:
        result = _parse_event(json.dumps(PAYLOAD_END))

        assert result is not None
        assert result.type == "end"
        assert result.end_time == pytest.approx(1710000060.0)

    def test_champs_plats_sans_after(self) -> None:
        payload = {"type": "new", "camera": "salon", "severity": "detection", "objects": ["chat"]}
        result = _parse_event(json.dumps(payload))

        assert result is not None
        assert result.camera == "salon"
        assert result.objects == ["chat"]

    def test_before_utilise_si_after_absent(self) -> None:
        payload = {
            "type": "end",
            "before": {"camera": "entree", "start_time": 1710000100.0, "end_time": 1710000200.0},
        }
        result = _parse_event(json.dumps(payload))

        assert result is not None
        assert result.camera == "entree"
        assert result.end_time == pytest.approx(1710000200.0)

    def test_severity_par_defaut_detection(self) -> None:
        result = _parse_event(json.dumps({"type": "new", "after": {"camera": "piscine"}}))
        assert result is not None
        assert result.severity == "detection"

    def test_objets_et_zones_vides_par_defaut(self) -> None:
        result = _parse_event(json.dumps({"type": "new", "after": {"camera": "terrasse"}}))
        assert result is not None
        assert result.objects == []
        assert result.zones == []

    def test_score_zero_par_defaut(self) -> None:
        result = _parse_event(json.dumps({"type": "new", "after": {"camera": "terrasse"}}))
        assert result is not None
        assert result.score == pytest.approx(0.0)

    def test_json_invalide_retourne_none(self) -> None:
        assert _parse_event("pas du json {{ invalide") is None

    def test_chaine_vide_retourne_none(self) -> None:
        assert _parse_event("") is None

    def test_none_retourne_none(self) -> None:
        assert _parse_event(None) is None  # type: ignore[arg-type]

    def test_type_inconnu_retourne_none(self) -> None:
        assert _parse_event(json.dumps({"type": "heartbeat", "after": {"camera": "jardin"}})) is None

    def test_type_manquant_retourne_none(self) -> None:
        assert _parse_event(json.dumps({"after": {"camera": "jardin"}})) is None

    def test_camera_manquante_retourne_none(self) -> None:
        assert _parse_event(json.dumps({"type": "new", "after": {"severity": "alert"}})) is None

    def test_json_liste_retourne_none(self) -> None:
        assert _parse_event(json.dumps(["new", "jardin"])) is None


# ---------------------------------------------------------------------------
# Tests de CameraState
# ---------------------------------------------------------------------------


class TestCameraState:
    def test_as_dict_contient_toutes_les_cles(self) -> None:
        state = CameraState(
            name="jardin",
            last_severity="alert",
            last_objects=["personne"],
            last_event_time=1710000000.0,
            motion=True,
            enabled=True,
        )
        d = state.as_dict()

        assert d["name"] == "jardin"
        assert d["last_severity"] == "alert"
        assert d["last_objects"] == ["personne"]
        assert d["last_event_time"] == pytest.approx(1710000000.0)
        assert d["motion"] is True
        assert d["enabled"] is True

    def test_valeurs_par_defaut(self) -> None:
        state = CameraState(name="cam")

        assert state.last_severity is None
        assert state.last_objects == []
        assert state.last_event_time is None
        assert state.motion is False
        assert state.enabled is True

    def test_as_dict_enabled_false(self) -> None:
        assert CameraState(name="cam", enabled=False).as_dict()["enabled"] is False


# ---------------------------------------------------------------------------
# Tests du coordinator — traitement MQTT
# ---------------------------------------------------------------------------


class TestHandleMqttMessage:
    async def test_type_new_met_a_jour_etat(self, hass: HomeAssistant) -> None:
        coordinator = _make_coordinator(hass, cam_name="jardin")
        coordinator._handle_mqtt_message(_make_msg(PAYLOAD_NEW))

        state = coordinator.camera_state
        assert state.last_severity == "alert"
        assert state.last_objects == ["personne"]
        assert state.motion is True

    async def test_type_update_met_a_jour_severity(self, hass: HomeAssistant) -> None:
        coordinator = _make_coordinator(hass, cam_name="jardin")
        coordinator._handle_mqtt_message(_make_msg(PAYLOAD_NEW))
        coordinator._handle_mqtt_message(_make_msg(PAYLOAD_UPDATE))

        state = coordinator.camera_state
        assert state.last_severity == "detection"
        assert state.last_objects == ["chien"]

    async def test_type_end_passe_motion_false(self, hass: HomeAssistant) -> None:
        coordinator = _make_coordinator(hass, cam_name="jardin")
        coordinator._handle_mqtt_message(_make_msg(PAYLOAD_NEW))
        assert coordinator.camera_state.motion is True

        coordinator._handle_mqtt_message(_make_msg(PAYLOAD_END))
        assert coordinator.camera_state.motion is False

    async def test_type_end_last_event_time_est_end_time(self, hass: HomeAssistant) -> None:
        coordinator = _make_coordinator(hass, cam_name="jardin")
        coordinator._handle_mqtt_message(_make_msg(PAYLOAD_NEW))
        coordinator._handle_mqtt_message(_make_msg(PAYLOAD_END))

        assert coordinator.camera_state.last_event_time == pytest.approx(1710000060.0)

    async def test_payload_invalide_ne_crash_pas(self, hass: HomeAssistant) -> None:
        coordinator = _make_coordinator(hass, cam_name="jardin")
        coordinator._handle_mqtt_message(_make_msg("pas du json {{{"))

        assert coordinator.camera_state.motion is False

    async def test_autre_camera_ignoree(self, hass: HomeAssistant) -> None:
        coordinator = _make_coordinator(hass, cam_name="garage")
        coordinator._handle_mqtt_message(_make_msg(PAYLOAD_NEW))  # camera=jardin

        assert coordinator.camera_state.motion is False

    async def test_coordinator_data_est_dict(self, hass: HomeAssistant) -> None:
        coordinator = _make_coordinator(hass, cam_name="jardin")
        coordinator._handle_mqtt_message(_make_msg(PAYLOAD_NEW))

        assert isinstance(coordinator.data, dict)
        for key in ("name", "last_severity", "last_objects", "motion", "enabled"):
            assert key in coordinator.data

    async def test_camera_property(self, hass: HomeAssistant) -> None:
        coordinator = _make_coordinator(hass, cam_name="salon")
        assert coordinator.camera == "salon"

    async def test_camera_state_property(self, hass: HomeAssistant) -> None:
        coordinator = _make_coordinator(hass, cam_name="jardin")
        assert isinstance(coordinator.camera_state, CameraState)
        assert coordinator.camera_state.name == "jardin"


# ---------------------------------------------------------------------------
# Tests de set_camera_enabled
# ---------------------------------------------------------------------------


class TestSetCameraEnabled:
    async def test_desactive_camera(self, hass: HomeAssistant) -> None:
        coordinator = _make_coordinator(hass)
        coordinator.set_camera_enabled(False)
        assert coordinator.camera_state.enabled is False

    async def test_reactive_camera(self, hass: HomeAssistant) -> None:
        coordinator = _make_coordinator(hass)
        coordinator.set_camera_enabled(False)
        coordinator.set_camera_enabled(True)
        assert coordinator.camera_state.enabled is True

    async def test_notifie_les_listeners(self, hass: HomeAssistant) -> None:
        coordinator = _make_coordinator(hass)
        listener = MagicMock()
        coordinator.async_add_listener(listener)
        coordinator.set_camera_enabled(False)
        listener.assert_called()

    async def test_data_reflecte_enabled_false(self, hass: HomeAssistant) -> None:
        coordinator = _make_coordinator(hass)
        coordinator.set_camera_enabled(False)
        assert coordinator.data["enabled"] is False

    async def test_enabled_true_par_defaut(self, hass: HomeAssistant) -> None:
        coordinator = _make_coordinator(hass)
        assert coordinator.camera_state.enabled is True


# ---------------------------------------------------------------------------
# Tests de async_start / async_stop
# ---------------------------------------------------------------------------


class TestAsyncStartStop:
    async def test_async_stop_appelle_unsubscribe(self, hass: HomeAssistant) -> None:
        coordinator = _make_coordinator(hass)
        mock_unsubscribe = MagicMock()
        coordinator._unsubscribe_mqtt = mock_unsubscribe

        await coordinator.async_stop()

        mock_unsubscribe.assert_called_once()
        assert coordinator._unsubscribe_mqtt is None

    async def test_async_stop_sans_souscription(self, hass: HomeAssistant) -> None:
        coordinator = _make_coordinator(hass)
        assert coordinator._unsubscribe_mqtt is None
        await coordinator.async_stop()  # ne doit pas lever d'exception

    async def test_async_start_appelle_subscribe(self) -> None:
        mock_unsubscribe = MagicMock()
        mock_subscribe = AsyncMock(return_value=mock_unsubscribe)
        mock_hass = MagicMock()

        coordinator = object.__new__(FrigateEventManagerCoordinator)
        coordinator._camera = "jardin"
        coordinator._camera_state = CameraState(name="jardin")
        coordinator._unsubscribe_mqtt = None
        coordinator.hass = mock_hass

        with patch(
            "custom_components.frigate_event_manager.coordinator.mqtt.async_subscribe",
            mock_subscribe,
        ):
            await coordinator.async_start()

        mock_subscribe.assert_called_once_with(
            mock_hass, DEFAULT_MQTT_TOPIC, coordinator._handle_mqtt_message
        )
        assert coordinator._unsubscribe_mqtt is mock_unsubscribe


# ---------------------------------------------------------------------------
# Tests de _async_update_data
# ---------------------------------------------------------------------------


class TestAsyncUpdateData:
    async def test_retourne_dict_vide_si_pas_de_messages(self, hass: HomeAssistant) -> None:
        coordinator = _make_coordinator(hass)
        result = await coordinator._async_update_data()
        assert result == {}

    async def test_retourne_data_existante(self, hass: HomeAssistant) -> None:
        coordinator = _make_coordinator(hass, cam_name="jardin")
        coordinator._handle_mqtt_message(_make_msg(PAYLOAD_NEW))

        result = await coordinator._async_update_data()
        assert isinstance(result, dict)
        assert result["name"] == "jardin"
