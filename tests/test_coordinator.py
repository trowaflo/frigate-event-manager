"""Tests for the Frigate Event Manager MQTT coordinator."""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.core import HomeAssistant

from custom_components.frigate_event_manager.const import (
    CONF_CAMERA,
    CONF_COOLDOWN,
    CONF_DEBOUNCE,
    CONF_DISABLED_HOURS,
    CONF_LABELS,
    CONF_NOTIFY_TARGET,
    CONF_SILENT_DURATION,
    CONF_ZONES,
    DEFAULT_MQTT_TOPIC,
)
from custom_components.frigate_event_manager.coordinator import (
    FrigateEventManagerCoordinator,
)
from custom_components.frigate_event_manager.domain.model import (
    CameraState,
    FrigateEvent,
    _parse_event,
)

# ---------------------------------------------------------------------------
# Realistic Frigate payloads
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
    """Create a minimal mock ConfigEntry (global)."""
    entry = MagicMock()
    entry.entry_id = "test-entry-id"
    entry.data = {}
    if notify_target:
        entry.data[CONF_NOTIFY_TARGET] = notify_target
    return entry


def _make_subentry(cam_name: str = "jardin", notify_target: str | None = None) -> MagicMock:
    """Create a mock ConfigSubentry for a camera."""
    subentry = MagicMock()
    subentry.subentry_id = f"sub_{cam_name}"
    subentry.data = {CONF_CAMERA: cam_name}
    if notify_target:
        subentry.data[CONF_NOTIFY_TARGET] = notify_target
    return subentry


def _make_fake_event_source() -> AsyncMock:
    """Create a fake EventSourcePort (AsyncMock returning an unsubscribe callable)."""
    source = AsyncMock()
    source.async_subscribe = AsyncMock(return_value=MagicMock())
    return source


def _make_coordinator(
    hass: HomeAssistant,
    cam_name: str = "jardin",
    notify_target: str | None = None,
) -> FrigateEventManagerCoordinator:
    """Instantiate a coordinator with mock ConfigEntry + ConfigSubentry."""
    entry = _make_entry()
    subentry = _make_subentry(cam_name, notify_target)
    return FrigateEventManagerCoordinator(
        hass, entry, subentry, event_source=_make_fake_event_source()
    )


def _make_msg(payload: dict | str) -> SimpleNamespace:
    """Create a fake MQTT message."""
    if isinstance(payload, dict):
        payload = json.dumps(payload)
    return SimpleNamespace(payload=payload)


# ---------------------------------------------------------------------------
# Tests for _parse_event
# ---------------------------------------------------------------------------


class TestParseEvent:
    """Unit tests for _parse_event."""

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

    def test_to_float_valeur_non_convertible_retourne_defaut(self) -> None:
        """_to_float with a non-convertible value returns the default."""
        from custom_components.frigate_event_manager.domain.model import _to_float

        assert _to_float("not_a_float", default=None) is None
        assert _to_float([], default=0.0) == 0.0

    def test_to_float_none_retourne_defaut(self) -> None:
        """_to_float(None) returns default."""
        from custom_components.frigate_event_manager.domain.model import _to_float

        assert _to_float(None, default=42.0) == 42.0


# ---------------------------------------------------------------------------
# Tests for CameraState
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
# Tests for coordinator — MQTT processing
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
        """An end with the same review_id as the new terminates motion."""
        coordinator = _make_coordinator(hass, cam_name="jardin")
        coordinator._handle_mqtt_message(_make_msg(PAYLOAD_NEW))
        assert coordinator.camera_state.motion is True

        # End of the same review (review-001 = review-001)
        payload_end_meme_review = {
            "type": "end",
            "after": {
                "camera": "jardin",
                "severity": "alert",
                "objects": ["personne"],
                "current_zones": ["entree"],
                "score": 0.88,
                "id": "review-001",  # same id as PAYLOAD_NEW
                "start_time": 1710000020.0,
                "end_time": 1710000060.0,
            },
        }
        coordinator._handle_mqtt_message(_make_msg(payload_end_meme_review))
        assert coordinator.camera_state.motion is False

    async def test_type_end_motion_reste_true_si_autre_review_actif(
        self, hass: HomeAssistant
    ) -> None:
        """An end does not set motion=False if another review is still active."""
        coordinator = _make_coordinator(hass, cam_name="jardin")

        # First review
        payload_new_1 = {
            "type": "new",
            "after": {
                "camera": "jardin", "severity": "alert",
                "objects": ["personne"], "id": "review-A", "start_time": 1710000000.0,
            },
        }
        # Second review
        payload_new_2 = {
            "type": "new",
            "after": {
                "camera": "jardin", "severity": "detection",
                "objects": ["chien"], "id": "review-B", "start_time": 1710000005.0,
            },
        }
        # End of the first review only
        payload_end_1 = {
            "type": "end",
            "after": {
                "camera": "jardin", "severity": "alert",
                "objects": ["personne"], "id": "review-A",
                "start_time": 1710000000.0, "end_time": 1710000030.0,
            },
        }

        coordinator._handle_mqtt_message(_make_msg(payload_new_1))
        coordinator._handle_mqtt_message(_make_msg(payload_new_2))
        assert coordinator.camera_state.motion is True

        coordinator._handle_mqtt_message(_make_msg(payload_end_1))
        # review-B is still active → motion must remain True
        assert coordinator.camera_state.motion is True

    async def test_type_end_last_event_time_est_end_time(self, hass: HomeAssistant) -> None:
        coordinator = _make_coordinator(hass, cam_name="jardin")
        coordinator._handle_mqtt_message(_make_msg(PAYLOAD_NEW))
        coordinator._handle_mqtt_message(_make_msg(PAYLOAD_END))

        assert coordinator.camera_state.last_event_time == pytest.approx(1710000060.0)

    async def test_type_end_motion_false_quand_tous_reviews_termines(
        self, hass: HomeAssistant
    ) -> None:
        """motion switches to False when all active reviews are finished."""
        coordinator = _make_coordinator(hass, cam_name="jardin")

        payload_new_1 = {
            "type": "new",
            "after": {
                "camera": "jardin", "severity": "alert",
                "objects": ["personne"], "id": "review-A", "start_time": 1710000000.0,
            },
        }
        payload_new_2 = {
            "type": "new",
            "after": {
                "camera": "jardin", "severity": "detection",
                "objects": ["chien"], "id": "review-B", "start_time": 1710000005.0,
            },
        }
        payload_end_1 = {
            "type": "end",
            "after": {
                "camera": "jardin", "id": "review-A",
                "start_time": 1710000000.0, "end_time": 1710000030.0,
            },
        }
        payload_end_2 = {
            "type": "end",
            "after": {
                "camera": "jardin", "id": "review-B",
                "start_time": 1710000005.0, "end_time": 1710000040.0,
            },
        }

        coordinator._handle_mqtt_message(_make_msg(payload_new_1))
        coordinator._handle_mqtt_message(_make_msg(payload_new_2))
        coordinator._handle_mqtt_message(_make_msg(payload_end_1))
        assert coordinator.camera_state.motion is True  # review-B still active

        coordinator._handle_mqtt_message(_make_msg(payload_end_2))
        assert coordinator.camera_state.motion is False  # no more active reviews

    async def test_review_id_vide_pas_ajoute_a_active_reviews(
        self, hass: HomeAssistant
    ) -> None:
        """A new event with empty review_id must not pollute _active_reviews."""
        coordinator = _make_coordinator(hass, cam_name="jardin")

        payload_new_sans_id = {
            "type": "new",
            "after": {
                "camera": "jardin",
                "severity": "alert",
                "objects": ["personne"],
                "current_zones": [],
                "score": 0.8,
                "id": "",  # empty review_id
                "start_time": 1710000000.0,
                "end_time": None,
            },
        }
        coordinator._handle_mqtt_message(_make_msg(payload_new_sans_id))

        # _active_reviews must remain empty — empty string is falsy
        assert coordinator._active_reviews == set()
        # motion still switches to True (it is a new event)
        assert coordinator.camera_state.motion is True

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
# Tests for set_camera_enabled
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
# Tests for async_start / async_stop
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
        await coordinator.async_stop()  # must not raise an exception

    async def test_async_start_appelle_subscribe(self, hass: HomeAssistant) -> None:
        """async_start subscribes via the injected EventSourcePort."""
        mock_unsubscribe = MagicMock()
        mock_source = AsyncMock()
        mock_source.async_subscribe = AsyncMock(return_value=mock_unsubscribe)

        coordinator = FrigateEventManagerCoordinator(
            hass, _make_entry(), _make_subentry("jardin"), event_source=mock_source
        )
        await coordinator.async_start()

        mock_source.async_subscribe.assert_called_once_with(
            DEFAULT_MQTT_TOPIC, coordinator._handle_mqtt_message
        )
        assert coordinator._unsubscribe_mqtt is mock_unsubscribe


# ---------------------------------------------------------------------------
# Tests for _async_update_data
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


# ---------------------------------------------------------------------------
# Tests for FilterChain built from subentry.data
# ---------------------------------------------------------------------------


class TestFilterChainDepuisSubentry:
    async def test_filtre_labels_bloque_mauvais_objet(self, hass: HomeAssistant) -> None:
        """LabelFilter: an event with an unauthorized object is blocked."""
        subentry = _make_subentry("jardin")
        subentry.data[CONF_ZONES] = []
        subentry.data[CONF_LABELS] = ["person"]
        subentry.data[CONF_DISABLED_HOURS] = []
        coordinator = FrigateEventManagerCoordinator(
            hass, _make_entry(), subentry, event_source=_make_fake_event_source()
        )

        # PAYLOAD_NEW has objects=["personne"] — does not match "person"
        assert coordinator._filter_chain.apply(
            __import__(
                "custom_components.frigate_event_manager.domain.model",
                fromlist=["FrigateEvent"],
            ).FrigateEvent(
                type="new",
                camera="jardin",
                severity="alert",
                objects=["car"],
                zones=["jardin"],
                score=0.9,
                review_id="r1",
                start_time=0.0,
                end_time=None,
            )
        ) is False

    async def test_filtre_labels_accepte_bon_objet(self, hass: HomeAssistant) -> None:
        """LabelFilter: an event with an authorized object is accepted."""
        subentry = _make_subentry("jardin")
        subentry.data[CONF_ZONES] = []
        subentry.data[CONF_LABELS] = ["person"]
        subentry.data[CONF_DISABLED_HOURS] = []
        coordinator = FrigateEventManagerCoordinator(
            hass, _make_entry(), subentry, event_source=_make_fake_event_source()
        )

        from custom_components.frigate_event_manager.domain.model import FrigateEvent

        assert coordinator._filter_chain.apply(
            FrigateEvent(
                type="new",
                camera="jardin",
                severity="alert",
                objects=["person"],
                zones=["jardin"],
                score=0.9,
                review_id="r1",
                start_time=0.0,
                end_time=None,
            )
        ) is True

    async def test_filtres_vides_acceptent_tout(self, hass: HomeAssistant) -> None:
        """Without configured filters, all events are accepted."""
        subentry = _make_subentry("jardin")
        subentry.data[CONF_ZONES] = []
        subentry.data[CONF_LABELS] = []
        subentry.data[CONF_DISABLED_HOURS] = []
        coordinator = FrigateEventManagerCoordinator(
            hass, _make_entry(), subentry, event_source=_make_fake_event_source()
        )

        from custom_components.frigate_event_manager.domain.model import FrigateEvent

        assert coordinator._filter_chain.apply(
            FrigateEvent(
                type="new",
                camera="jardin",
                severity="alert",
                objects=["anything"],
                zones=[],
                score=0.5,
                review_id="r2",
                start_time=0.0,
                end_time=None,
            )
        ) is True


# ---------------------------------------------------------------------------
# Tests for configurable cooldown
# ---------------------------------------------------------------------------


class TestCooldownConfigurable:
    async def test_cooldown_depuis_subentry(self, hass: HomeAssistant) -> None:
        """The Throttler uses the cooldown configured in the subentry."""
        subentry = _make_subentry("jardin")
        subentry.data[CONF_COOLDOWN] = 120
        coordinator = FrigateEventManagerCoordinator(
            hass, _make_entry(), subentry, event_source=_make_fake_event_source()
        )
        assert coordinator._throttler._cooldown == 120

    async def test_cooldown_defaut_si_absent(self, hass: HomeAssistant) -> None:
        """Without CONF_COOLDOWN in subentry → default cooldown (60)."""
        coordinator = _make_coordinator(hass, cam_name="jardin")
        assert coordinator._throttler._cooldown == 60


# ---------------------------------------------------------------------------
# Tests for silent mode
# ---------------------------------------------------------------------------


class TestSilentMode:
    async def test_activate_silent_mode_bloque_notifications(
        self, hass: HomeAssistant
    ) -> None:
        """In silent mode, new events do not trigger a notification."""
        notifier = AsyncMock()
        subentry = _make_subentry("jardin")
        subentry.data[CONF_SILENT_DURATION] = 30
        coordinator = FrigateEventManagerCoordinator(
            hass,
            _make_entry(),
            subentry,
            notifier=notifier,
            event_source=_make_fake_event_source(),
        )
        coordinator.activate_silent_mode()

        coordinator._handle_mqtt_message(_make_msg(PAYLOAD_NEW))
        await hass.async_block_till_done()

        notifier.async_notify.assert_not_called()

    async def test_activate_silent_mode_met_a_jour_silent_until(
        self, hass: HomeAssistant
    ) -> None:
        """activate_silent_mode sets _silent_until to a future timestamp."""
        import time
        coordinator = _make_coordinator(hass)
        before = time.time()
        coordinator.activate_silent_mode()
        assert coordinator._silent_until > before

    async def test_silent_duration_depuis_subentry(self, hass: HomeAssistant) -> None:
        """_silent_duration matches the value from the subentry."""
        subentry = _make_subentry("jardin")
        subentry.data[CONF_SILENT_DURATION] = 45
        coordinator = FrigateEventManagerCoordinator(
            hass, _make_entry(), subentry, event_source=_make_fake_event_source()
        )
        assert coordinator._silent_duration == 45


# ---------------------------------------------------------------------------
# Tests for debounce
# ---------------------------------------------------------------------------


class TestDebounce:
    async def test_debounce_zero_envoie_immediatement(
        self, hass: HomeAssistant
    ) -> None:
        """With debounce=0, the notification is sent immediately."""
        notifier = AsyncMock()
        subentry = _make_subentry("jardin")
        subentry.data[CONF_DEBOUNCE] = 0
        coordinator = FrigateEventManagerCoordinator(
            hass,
            _make_entry(),
            subentry,
            notifier=notifier,
            event_source=_make_fake_event_source(),
        )
        coordinator._handle_mqtt_message(_make_msg(PAYLOAD_NEW))
        await hass.async_block_till_done()

        notifier.async_notify.assert_called_once()

    async def test_debounce_positif_differe_notification(
        self, hass: HomeAssistant
    ) -> None:
        """With debounce > 0, the notification is not sent immediately."""
        notifier = AsyncMock()
        subentry = _make_subentry("jardin")
        subentry.data[CONF_DEBOUNCE] = 5
        coordinator = FrigateEventManagerCoordinator(
            hass,
            _make_entry(),
            subentry,
            notifier=notifier,
            event_source=_make_fake_event_source(),
        )
        coordinator._handle_mqtt_message(_make_msg(PAYLOAD_NEW))
        # No await block_till_done — the task is scheduled but not executed
        notifier.async_notify.assert_not_called()
        # Cleanup
        if coordinator._debounce_task:
            coordinator._debounce_task.cancel()

    async def test_debounce_end_annule_task_et_libere_throttler(
        self, hass: HomeAssistant
    ) -> None:
        """An end event cancels the running debounce task."""
        notifier = AsyncMock()
        subentry = _make_subentry("jardin")
        subentry.data[CONF_DEBOUNCE] = 5
        coordinator = FrigateEventManagerCoordinator(
            hass,
            _make_entry(),
            subentry,
            notifier=notifier,
            event_source=_make_fake_event_source(),
        )
        coordinator._handle_mqtt_message(_make_msg(PAYLOAD_NEW))
        assert coordinator._debounce_task is not None

        coordinator._handle_mqtt_message(_make_msg(PAYLOAD_END))
        await hass.async_block_till_done()

        # Task was cancelled → no notification sent
        notifier.async_notify.assert_not_called()
        assert coordinator._debounce_task is None

    async def test_debounce_accumule_objects(self, hass: HomeAssistant) -> None:
        """With debounce, _pending_objects accumulates objects from events."""
        notifier = AsyncMock()
        subentry = _make_subentry("jardin")
        subentry.data[CONF_DEBOUNCE] = 5
        coordinator = FrigateEventManagerCoordinator(
            hass,
            _make_entry(),
            subentry,
            notifier=notifier,
            event_source=_make_fake_event_source(),
        )
        coordinator._handle_mqtt_message(_make_msg(PAYLOAD_NEW))  # objects=["personne"]
        coordinator._handle_mqtt_message(_make_msg(PAYLOAD_UPDATE))  # objects=["chien"]

        assert "personne" in coordinator._pending_objects
        assert "chien" in coordinator._pending_objects

        if coordinator._debounce_task:
            coordinator._debounce_task.cancel()

    async def test_chemin_immediat_transmet_critical_true_a_async_notify(
        self, hass: HomeAssistant
    ) -> None:
        """With debounce=0 and critical_template='true', critical=True is passed to async_notify."""
        from custom_components.frigate_event_manager.const import CONF_CRITICAL_TEMPLATE

        notifier = AsyncMock()
        subentry = _make_subentry("jardin")
        subentry.data[CONF_DEBOUNCE] = 0
        subentry.data[CONF_CRITICAL_TEMPLATE] = "true"
        coordinator = FrigateEventManagerCoordinator(
            hass,
            _make_entry(),
            subentry,
            notifier=notifier,
            event_source=_make_fake_event_source(),
        )

        coordinator._handle_mqtt_message(_make_msg(PAYLOAD_NEW))
        await hass.async_block_till_done()

        notifier.async_notify.assert_called_once()
        _, kwargs = notifier.async_notify.call_args
        assert kwargs.get("critical") is True


# ---------------------------------------------------------------------------
# Tests for notification on type=update
# ---------------------------------------------------------------------------


class TestNotificationUpdate:
    async def test_type_update_notifie_si_conditions_reunies(
        self, hass: HomeAssistant
    ) -> None:
        """An update event triggers a notification if the throttle allows it."""
        notifier = AsyncMock()
        subentry = _make_subentry("jardin")
        coordinator = FrigateEventManagerCoordinator(
            hass,
            _make_entry(),
            subentry,
            notifier=notifier,
            event_source=_make_fake_event_source(),
        )
        coordinator._handle_mqtt_message(_make_msg(PAYLOAD_UPDATE))
        await hass.async_block_till_done()

        notifier.async_notify.assert_called_once()

    async def test_type_end_ne_notifie_pas(self, hass: HomeAssistant) -> None:
        """An end event never triggers a notification."""
        notifier = AsyncMock()
        coordinator = FrigateEventManagerCoordinator(
            hass,
            _make_entry(),
            _make_subentry("jardin"),
            notifier=notifier,
            event_source=_make_fake_event_source(),
        )
        coordinator._handle_mqtt_message(_make_msg(PAYLOAD_END))
        await hass.async_block_till_done()

        notifier.async_notify.assert_not_called()

    async def test_camera_disabled_ne_notifie_pas(self, hass: HomeAssistant) -> None:
        """Disabled camera → no notification even on new."""
        notifier = AsyncMock()
        coordinator = FrigateEventManagerCoordinator(
            hass,
            _make_entry(),
            _make_subentry("jardin"),
            notifier=notifier,
            event_source=_make_fake_event_source(),
        )
        coordinator.set_camera_enabled(False)
        coordinator._handle_mqtt_message(_make_msg(PAYLOAD_NEW))
        await hass.async_block_till_done()

        notifier.async_notify.assert_not_called()


# ---------------------------------------------------------------------------
# Tests for _debounce_send — full coroutine execution
# ---------------------------------------------------------------------------


class TestDebounceSend:
    async def test_debounce_send_envoie_notification_groupee(
        self, hass: HomeAssistant
    ) -> None:
        """_debounce_send() sends a notification with accumulated objects."""
        notifier = AsyncMock()
        subentry = _make_subentry("jardin")
        subentry.data[CONF_DEBOUNCE] = 1  # 1 seconde
        coordinator = FrigateEventManagerCoordinator(
            hass,
            _make_entry(),
            subentry,
            notifier=notifier,
            event_source=_make_fake_event_source(),
        )

        # Simulate object accumulation
        coordinator._pending_objects = {"personne", "chien"}
        coordinator._pending_event = _make_msg(PAYLOAD_NEW)

        from custom_components.frigate_event_manager.domain.model import FrigateEvent
        coordinator._pending_event = FrigateEvent(
            type="new",
            camera="jardin",
            severity="alert",
            objects=["personne"],
            zones=["entree"],
            score=0.9,
            review_id="r1",
            start_time=1710000000.0,
            end_time=None,
        )
        coordinator._debounce_seconds = 0  # no wait for the test

        await coordinator._debounce_send()

        notifier.async_notify.assert_called_once()
        call_args = notifier.async_notify.call_args[0][0]
        assert set(call_args.objects) == {"personne", "chien"}

    async def test_debounce_send_reinitialise_pending(
        self, hass: HomeAssistant
    ) -> None:
        """_debounce_send() clears _pending_objects and _pending_event after sending."""
        notifier = AsyncMock()
        subentry = _make_subentry("jardin")
        coordinator = FrigateEventManagerCoordinator(
            hass,
            _make_entry(),
            subentry,
            notifier=notifier,
            event_source=_make_fake_event_source(),
        )
        from custom_components.frigate_event_manager.domain.model import FrigateEvent
        coordinator._pending_objects = {"chat"}
        coordinator._pending_event = FrigateEvent(
            type="new", camera="jardin", severity="detection",
            objects=["chat"], zones=[], score=0.8, review_id="r2",
            start_time=1710000000.0, end_time=None,
        )
        coordinator._debounce_seconds = 0

        await coordinator._debounce_send()

        assert coordinator._pending_objects == set()
        assert coordinator._pending_event is None
        assert coordinator._debounce_task is None

    async def test_debounce_send_sans_pending_event_ne_notifie_pas(
        self, hass: HomeAssistant
    ) -> None:
        """_debounce_send() without _pending_event does not notify."""
        notifier = AsyncMock()
        coordinator = FrigateEventManagerCoordinator(
            hass,
            _make_entry(),
            _make_subentry("jardin"),
            notifier=notifier,
            event_source=_make_fake_event_source(),
        )
        coordinator._debounce_seconds = 0
        # _pending_event is None by default

        await coordinator._debounce_send()

        notifier.async_notify.assert_not_called()

    async def test_debounce_send_cancellation_ne_notifie_pas(
        self, hass: HomeAssistant
    ) -> None:
        """If _debounce_send() is cancelled, no notification is sent."""
        import asyncio
        notifier = AsyncMock()
        subentry = _make_subentry("jardin")
        subentry.data[CONF_DEBOUNCE] = 10  # 10 seconds → will be cancelled
        coordinator = FrigateEventManagerCoordinator(
            hass,
            _make_entry(),
            subentry,
            notifier=notifier,
            event_source=_make_fake_event_source(),
        )
        from custom_components.frigate_event_manager.domain.model import FrigateEvent
        coordinator._pending_event = FrigateEvent(
            type="new", camera="jardin", severity="alert",
            objects=["personne"], zones=[], score=0.9, review_id="r3",
            start_time=0.0, end_time=None,
        )

        task = hass.async_create_task(coordinator._debounce_send())
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        notifier.async_notify.assert_not_called()

    async def test_async_stop_annule_debounce_task_en_cours(
        self, hass: HomeAssistant
    ) -> None:
        """async_stop() cancels the debounce_task if active."""
        subentry = _make_subentry("jardin")
        subentry.data[CONF_DEBOUNCE] = 10
        notifier = AsyncMock()
        coordinator = FrigateEventManagerCoordinator(
            hass,
            _make_entry(),
            subentry,
            notifier=notifier,
            event_source=_make_fake_event_source(),
        )
        # Trigger debounce via a new event
        coordinator._handle_mqtt_message(_make_msg(PAYLOAD_NEW))
        assert coordinator._debounce_task is not None

        await coordinator.async_stop()

        assert coordinator._debounce_task is None

    async def test_debounce_send_transmet_critical_true_a_async_notify(
        self, hass: HomeAssistant
    ) -> None:
        """_debounce_send() passes critical=True to async_notify when the template dictates it."""
        from custom_components.frigate_event_manager.const import CONF_CRITICAL_TEMPLATE
        from custom_components.frigate_event_manager.domain.model import FrigateEvent

        notifier = AsyncMock()
        subentry = _make_subentry("jardin")
        # Template that always returns True — critical=True path guaranteed
        subentry.data[CONF_CRITICAL_TEMPLATE] = "true"
        coordinator = FrigateEventManagerCoordinator(
            hass,
            _make_entry(),
            subentry,
            notifier=notifier,
            event_source=_make_fake_event_source(),
        )
        coordinator._pending_objects = {"personne"}
        coordinator._pending_event = FrigateEvent(
            type="update",
            camera="jardin",
            severity="alert",
            objects=["personne"],
            zones=["entree"],
            score=0.9,
            review_id="r-critical",
            start_time=1710000000.0,
            end_time=None,
        )
        coordinator._debounce_seconds = 0

        await coordinator._debounce_send()

        notifier.async_notify.assert_called_once()
        _, kwargs = notifier.async_notify.call_args
        assert kwargs.get("critical") is True


# ---------------------------------------------------------------------------
# Tests for advanced silent mode — cancel and async_stop
# ---------------------------------------------------------------------------


class TestSilentModeAvance:
    async def test_activate_silent_mode_stocke_cancel(
        self, hass: HomeAssistant
    ) -> None:
        """activate_silent_mode stores a cancellation callable in _cancel_silent."""
        coordinator = _make_coordinator(hass)
        assert coordinator._cancel_silent is None

        coordinator.activate_silent_mode()

        assert coordinator._cancel_silent is not None

    async def test_activate_silent_mode_double_appel_annule_premier(
        self, hass: HomeAssistant
    ) -> None:
        """A second call to activate_silent_mode cancels the first timer."""
        coordinator = _make_coordinator(hass)

        coordinator.activate_silent_mode()
        premier_cancel = coordinator._cancel_silent
        assert premier_cancel is not None

        # Spy on the first cancel call
        annule = MagicMock(wraps=premier_cancel)
        coordinator._cancel_silent = annule

        coordinator.activate_silent_mode()

        # The first timer must have been cancelled
        annule.assert_called_once()
        # A new cancel must be stored
        assert coordinator._cancel_silent is not None
        assert coordinator._cancel_silent is not annule

    async def test_async_stop_annule_cancel_silent(
        self, hass: HomeAssistant
    ) -> None:
        """async_stop() calls _cancel_silent and sets it to None."""
        coordinator = _make_coordinator(hass)
        coordinator.activate_silent_mode()
        assert coordinator._cancel_silent is not None

        # Spy on the cancellation callable
        mock_cancel = MagicMock()
        coordinator._cancel_silent = mock_cancel

        await coordinator.async_stop()

        mock_cancel.assert_called_once()
        assert coordinator._cancel_silent is None

    async def test_async_stop_sans_cancel_silent_ne_crash_pas(
        self, hass: HomeAssistant
    ) -> None:
        """async_stop() without active silent mode raises no exception."""
        coordinator = _make_coordinator(hass)
        assert coordinator._cancel_silent is None

        await coordinator.async_stop()  # must not raise an exception

    async def test_async_cancel_silent_annule_timer_et_remet_zero(
        self, hass: HomeAssistant
    ) -> None:
        """async_cancel_silent cancels the timer, resets _silent_until to 0.0 and saves."""
        coordinator = _make_coordinator(hass)
        coordinator.activate_silent_mode()
        assert coordinator._cancel_silent is not None

        mock_cancel = MagicMock()
        coordinator._cancel_silent = mock_cancel
        coordinator._store = MagicMock()
        coordinator._store.async_save = AsyncMock()

        await coordinator.async_cancel_silent()

        mock_cancel.assert_called_once()
        assert coordinator._cancel_silent is None
        assert coordinator._silent_until == 0.0

    async def test_async_cancel_silent_sans_timer_actif_ne_crash_pas(
        self, hass: HomeAssistant
    ) -> None:
        """async_cancel_silent without active silent mode raises no exception."""
        coordinator = _make_coordinator(hass)
        assert coordinator._cancel_silent is None

        coordinator._store = MagicMock()
        coordinator._store.async_save = AsyncMock()

        await coordinator.async_cancel_silent()  # must not raise an exception
        assert coordinator._silent_until == 0.0

    async def test_async_remove_store_appelle_store_async_remove(
        self, hass: HomeAssistant
    ) -> None:
        """async_remove_store delegates to self._store.async_remove()."""
        coordinator = _make_coordinator(hass)
        coordinator._store = MagicMock()
        coordinator._store.async_remove = AsyncMock()

        await coordinator.async_remove_store()

        coordinator._store.async_remove.assert_called_once()


# ---------------------------------------------------------------------------
# Tests for silent mode persistence via Store
# ---------------------------------------------------------------------------


class TestSilentModePersistance:
    async def test_activate_silent_mode_sauvegarde_via_store(
        self, hass: HomeAssistant
    ) -> None:
        """activate_silent_mode schedules a Store save task."""
        coordinator = _make_coordinator(hass)
        coordinator._store = MagicMock()
        coordinator._store.async_save = AsyncMock()

        coordinator.activate_silent_mode()
        await hass.async_block_till_done()

        coordinator._store.async_save.assert_called()
        call_args = coordinator._store.async_save.call_args[0][0]
        assert "silent_until" in call_args
        assert call_args["silent_until"] > 0.0

    async def test_async_start_restaure_silent_mode_actif(
        self, hass: HomeAssistant
    ) -> None:
        """async_start restores _silent_until if the Store contains a future value."""
        import time
        future = time.time() + 3600.0  # 1h in the future
        mock_source = AsyncMock()
        mock_source.async_subscribe = AsyncMock(return_value=MagicMock())

        coordinator = FrigateEventManagerCoordinator(
            hass, _make_entry(), _make_subentry("jardin"), event_source=mock_source
        )
        coordinator._store = MagicMock()
        coordinator._store.async_load = AsyncMock(return_value={"silent_until": future})

        await coordinator.async_start()

        assert coordinator._silent_until == future
        assert coordinator._cancel_silent is not None

    async def test_async_start_ignore_silent_mode_expire(
        self, hass: HomeAssistant
    ) -> None:
        """async_start ignores an expired silent_until (in the past)."""
        import time
        past = time.time() - 3600.0  # 1h in the past
        mock_source = AsyncMock()
        mock_source.async_subscribe = AsyncMock(return_value=MagicMock())

        coordinator = FrigateEventManagerCoordinator(
            hass, _make_entry(), _make_subentry("jardin"), event_source=mock_source
        )
        coordinator._store = MagicMock()
        coordinator._store.async_load = AsyncMock(return_value={"silent_until": past})

        await coordinator.async_start()

        # No restore — the period has expired
        assert coordinator._silent_until == 0.0
        assert coordinator._cancel_silent is None

    async def test_async_start_store_vide_ne_crash_pas(
        self, hass: HomeAssistant
    ) -> None:
        """async_start with empty Store raises no exception."""
        mock_source = AsyncMock()
        mock_source.async_subscribe = AsyncMock(return_value=MagicMock())

        coordinator = FrigateEventManagerCoordinator(
            hass, _make_entry(), _make_subentry("jardin"), event_source=mock_source
        )
        coordinator._store = MagicMock()
        coordinator._store.async_load = AsyncMock(return_value=None)

        await coordinator.async_start()  # must not raise an exception

        assert coordinator._silent_until == 0.0


# ---------------------------------------------------------------------------
# Tests _is_critical
# ---------------------------------------------------------------------------


class TestIsCritical:
    """Tests for the _is_critical method of the coordinator."""

    def _make_event(self, severity: str = "alert") -> FrigateEvent:
        return FrigateEvent(
            type="new",
            camera="jardin",
            severity=severity,
            objects=["personne"],
            zones=["entree"],
            score=0.9,
            review_id="r1",
        )

    def test_sans_template_retourne_false(self, hass: HomeAssistant) -> None:
        """No critical_template → _is_critical always returns False."""
        coordinator = _make_coordinator(hass)
        coordinator._critical_template = None
        assert coordinator._is_critical(self._make_event()) is False

    def test_template_vrai_retourne_true(self, hass: HomeAssistant) -> None:
        """Template evaluating to 'True' → _is_critical returns True."""
        coordinator = _make_coordinator(hass)
        coordinator._critical_template = "{{ severity == 'alert' }}"
        assert coordinator._is_critical(self._make_event(severity="alert")) is True

    def test_template_faux_retourne_false(self, hass: HomeAssistant) -> None:
        """Template evaluating to 'False' → _is_critical returns False."""
        coordinator = _make_coordinator(hass)
        coordinator._critical_template = "{{ severity == 'alert' }}"
        assert coordinator._is_critical(self._make_event(severity="detection")) is False

    def test_template_invalide_retourne_false(self, hass: HomeAssistant) -> None:
        """Invalid Jinja2 template → _is_critical returns False without raising an exception."""
        coordinator = _make_coordinator(hass)
        coordinator._critical_template = "{{ this_is_not_valid_jinja2(((( }}"
        # Must not raise an exception
        assert coordinator._is_critical(self._make_event()) is False


# ---------------------------------------------------------------------------
# Tests for live setters (setting entities T-524)
# ---------------------------------------------------------------------------


class TestSettersLive:
    """Tests for live setters of the coordinator — number / select / text."""

    def test_silent_until_property_retourne_valeur(self, hass: HomeAssistant) -> None:
        """The silent_until property exposes _silent_until."""
        coordinator = _make_coordinator(hass)
        coordinator._silent_until = 12345.0
        assert coordinator.silent_until == 12345.0

    def test_set_cooldown_remplace_throttler(self, hass: HomeAssistant) -> None:
        """set_cooldown creates a new Throttler with the given value."""
        from custom_components.frigate_event_manager.domain.throttle import Throttler

        coordinator = _make_coordinator(hass)
        old_throttler = coordinator._throttler
        coordinator.set_cooldown(120)
        assert coordinator._throttler is not old_throttler
        assert isinstance(coordinator._throttler, Throttler)

    def test_set_debounce_met_a_jour_debounce_seconds(self, hass: HomeAssistant) -> None:
        """set_debounce updates _debounce_seconds."""
        coordinator = _make_coordinator(hass)
        coordinator.set_debounce(15)
        assert coordinator._debounce_seconds == 15

    def test_set_severity_met_a_jour_filter_chain(self, hass: HomeAssistant) -> None:
        """set_severity updates _severities and rebuilds _filter_chain."""
        from custom_components.frigate_event_manager.domain.filter import FilterChain

        coordinator = _make_coordinator(hass)
        old_chain = coordinator._filter_chain
        coordinator.set_severity(["alert"])
        assert coordinator._severities == ["alert"]
        assert coordinator._filter_chain is not old_chain
        assert isinstance(coordinator._filter_chain, FilterChain)

    def test_set_tap_action_delegue_au_notifier(self, hass: HomeAssistant) -> None:
        """set_tap_action calls set_tap_action on the notifier if present."""
        coordinator = _make_coordinator(hass)
        mock_notifier = MagicMock()
        mock_notifier.set_tap_action = MagicMock()
        coordinator._notifier = mock_notifier
        coordinator.set_tap_action("snapshot")
        mock_notifier.set_tap_action.assert_called_once_with("snapshot")

    def test_set_tap_action_sans_notifier_ne_crash_pas(self, hass: HomeAssistant) -> None:
        """set_tap_action without a notifier raises no exception."""
        coordinator = _make_coordinator(hass)
        coordinator._notifier = None
        coordinator.set_tap_action("preview")  # must not raise an exception

    def test_set_notif_title_delegue_au_notifier(self, hass: HomeAssistant) -> None:
        """set_notif_title calls set_title_template on the notifier if present."""
        coordinator = _make_coordinator(hass)
        mock_notifier = MagicMock()
        mock_notifier.set_title_template = MagicMock()
        coordinator._notifier = mock_notifier
        coordinator.set_notif_title("Alerte {{ camera }}")
        mock_notifier.set_title_template.assert_called_once_with("Alerte {{ camera }}")

    def test_set_notif_title_sans_notifier_ne_crash_pas(self, hass: HomeAssistant) -> None:
        """set_notif_title without a notifier raises no exception."""
        coordinator = _make_coordinator(hass)
        coordinator._notifier = None
        coordinator.set_notif_title("titre")  # must not raise an exception

    def test_set_notif_message_delegue_au_notifier(self, hass: HomeAssistant) -> None:
        """set_notif_message calls set_message_template on the notifier if present."""
        coordinator = _make_coordinator(hass)
        mock_notifier = MagicMock()
        mock_notifier.set_message_template = MagicMock()
        coordinator._notifier = mock_notifier
        coordinator.set_notif_message("{{ objects | join(', ') }}")
        mock_notifier.set_message_template.assert_called_once_with("{{ objects | join(', ') }}")

    def test_set_notif_message_sans_notifier_ne_crash_pas(self, hass: HomeAssistant) -> None:
        """set_notif_message without a notifier raises no exception."""
        coordinator = _make_coordinator(hass)
        coordinator._notifier = None
        coordinator.set_notif_message("msg")  # must not raise an exception

    def test_set_critical_template_met_a_jour_template(self, hass: HomeAssistant) -> None:
        """set_critical_template updates _critical_template."""
        coordinator = _make_coordinator(hass)
        coordinator.set_critical_template("{{ severity == 'alert' }}")
        assert coordinator._critical_template == "{{ severity == 'alert' }}"

    def test_set_critical_template_vide_passe_none(self, hass: HomeAssistant) -> None:
        """set_critical_template with empty string normalises to None."""
        coordinator = _make_coordinator(hass)
        coordinator._critical_template = "old"
        coordinator.set_critical_template("")
        assert coordinator._critical_template is None

    def test_on_silent_expired_remet_silent_until_a_zero(self, hass: HomeAssistant) -> None:
        """_on_silent_expired resets _silent_until to 0.0 and _cancel_silent to None."""
        coordinator = _make_coordinator(hass)
        coordinator._silent_until = 99999.0
        coordinator._cancel_silent = MagicMock()
        coordinator._store = MagicMock()
        coordinator._store.async_save = AsyncMock()
        coordinator.async_set_updated_data = MagicMock()

        coordinator._on_silent_expired(None)

        assert coordinator._silent_until == 0.0
        assert coordinator._cancel_silent is None


# ---------------------------------------------------------------------------
# Tests for notification action buttons (T-532)
# ---------------------------------------------------------------------------


class TestActionBtns:
    """Tests for action button setters and the notification_action listener."""

    def test_set_action_btn1_updates_value(self, hass: HomeAssistant) -> None:
        coordinator = _make_coordinator(hass)
        coordinator.set_action_btn1("clip")
        assert coordinator._action_btn1 == "clip"

    def test_set_action_btn2_updates_value(self, hass: HomeAssistant) -> None:
        coordinator = _make_coordinator(hass)
        coordinator.set_action_btn2("snapshot")
        assert coordinator._action_btn2 == "snapshot"

    def test_set_action_btn3_updates_value(self, hass: HomeAssistant) -> None:
        coordinator = _make_coordinator(hass)
        coordinator.set_action_btn3("dismiss")
        assert coordinator._action_btn3 == "dismiss"

    def test_set_action_btn1_invalid_value_falls_back_to_none(self, hass: HomeAssistant) -> None:
        coordinator = _make_coordinator(hass)
        coordinator.set_action_btn1("invalide")
        assert coordinator._action_btn1 == "none"

    def test_set_action_btn1_delegates_to_notifier(self, hass: HomeAssistant) -> None:
        coordinator = _make_coordinator(hass)
        mock_notifier = MagicMock()
        mock_notifier.set_action_buttons = MagicMock()
        coordinator._notifier = mock_notifier
        coordinator.set_action_btn1("clip")
        mock_notifier.set_action_buttons.assert_called_once_with("clip", "none", "none")

    def test_set_action_btn1_without_notifier_does_not_crash(self, hass: HomeAssistant) -> None:
        coordinator = _make_coordinator(hass)
        coordinator._notifier = None
        coordinator.set_action_btn1("clip")  # must not raise an exception

    def test_initial_values_none(self, hass: HomeAssistant) -> None:
        """Action buttons default to 'none'."""
        coordinator = _make_coordinator(hass)
        assert coordinator._action_btn1 == "none"
        assert coordinator._action_btn2 == "none"
        assert coordinator._action_btn3 == "none"

    def test_handle_notification_action_silent_30min(self, hass: HomeAssistant) -> None:
        """The fem_silent_30min_{cam} action activates silent mode for 30 min."""
        from types import SimpleNamespace

        coordinator = _make_coordinator(hass, cam_name="jardin")
        coordinator.activate_silent_mode = MagicMock()

        event = SimpleNamespace(data={"action": "fem_silent_30min_jardin"})
        coordinator._handle_notification_action(event)

        coordinator.activate_silent_mode.assert_called_once_with(duration_min=30)

    def test_handle_notification_action_silent_1h(self, hass: HomeAssistant) -> None:
        """The fem_silent_1h_{cam} action activates silent mode for 1h."""
        from types import SimpleNamespace

        coordinator = _make_coordinator(hass, cam_name="jardin")
        coordinator.activate_silent_mode = MagicMock()

        event = SimpleNamespace(data={"action": "fem_silent_1h_jardin"})
        coordinator._handle_notification_action(event)

        coordinator.activate_silent_mode.assert_called_once_with(duration_min=60)

    def test_handle_notification_action_autre_camera_ignoree(self, hass: HomeAssistant) -> None:
        """An action for a different camera is ignored."""
        from types import SimpleNamespace

        coordinator = _make_coordinator(hass, cam_name="jardin")
        coordinator.activate_silent_mode = MagicMock()

        event = SimpleNamespace(data={"action": "fem_silent_30min_garage"})
        coordinator._handle_notification_action(event)

        coordinator.activate_silent_mode.assert_not_called()

    def test_handle_notification_action_inconnue_ignoree(self, hass: HomeAssistant) -> None:
        """An unknown action is silently ignored."""
        from types import SimpleNamespace

        coordinator = _make_coordinator(hass, cam_name="jardin")
        coordinator.activate_silent_mode = MagicMock()

        event = SimpleNamespace(data={"action": "autre_action"})
        coordinator._handle_notification_action(event)

        coordinator.activate_silent_mode.assert_not_called()

    def test_activate_silent_mode_avec_duration_min(self, hass: HomeAssistant) -> None:
        """activate_silent_mode(duration_min=30) uses 30 min instead of _silent_duration."""
        import time

        coordinator = _make_coordinator(hass)
        coordinator._silent_duration = 60  # entity default value
        coordinator._store = MagicMock()
        coordinator._store.async_save = AsyncMock()
        coordinator.async_set_updated_data = MagicMock()

        before = time.time()
        coordinator.activate_silent_mode(duration_min=30)
        after = time.time()

        # _silent_until must correspond to ~30 min, not 60
        expected_min = before + 30 * 60
        expected_max = after + 30 * 60
        assert expected_min <= coordinator._silent_until <= expected_max

    async def test_async_stop_desabonne_notif_action(self, hass: HomeAssistant) -> None:
        """async_stop calls the unsubscribe callable for the notification_action listener."""
        coordinator = _make_coordinator(hass)
        mock_unsub = MagicMock()
        coordinator._unsubscribe_notif_action = mock_unsub

        await coordinator.async_stop()

        mock_unsub.assert_called_once()
        assert coordinator._unsubscribe_notif_action is None
