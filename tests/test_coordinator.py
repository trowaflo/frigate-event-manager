"""Tests du coordinator MQTT Frigate Event Manager."""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

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


def _make_fake_event_source() -> AsyncMock:
    """Crée un EventSourcePort fake (AsyncMock retournant un callable de désabonnement)."""
    source = AsyncMock()
    source.async_subscribe = AsyncMock(return_value=MagicMock())
    return source


def _make_coordinator(
    hass: HomeAssistant,
    cam_name: str = "jardin",
    notify_target: str | None = None,
) -> FrigateEventManagerCoordinator:
    """Instancie un coordinator avec des mocks ConfigEntry + ConfigSubentry."""
    entry = _make_entry()
    subentry = _make_subentry(cam_name, notify_target)
    return FrigateEventManagerCoordinator(
        hass, entry, subentry, event_source=_make_fake_event_source()
    )


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

    async def test_async_start_appelle_subscribe(self, hass: HomeAssistant) -> None:
        """async_start souscrit via l'EventSourcePort injecté."""
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


# ---------------------------------------------------------------------------
# Tests de FilterChain construite depuis subentry.data
# ---------------------------------------------------------------------------


class TestFilterChainDepuisSubentry:
    async def test_filtre_labels_bloque_mauvais_objet(self, hass: HomeAssistant) -> None:
        """LabelFilter: un événement avec objet non autorisé est bloqué."""
        subentry = _make_subentry("jardin")
        subentry.data[CONF_ZONES] = []
        subentry.data[CONF_LABELS] = ["person"]
        subentry.data[CONF_DISABLED_HOURS] = []
        coordinator = FrigateEventManagerCoordinator(
            hass, _make_entry(), subentry, event_source=_make_fake_event_source()
        )

        # PAYLOAD_NEW a objects=["personne"] — ne correspond pas à "person"
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
        """LabelFilter: un événement avec objet autorisé est accepté."""
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
        """Sans filtres configurés, tous les événements sont acceptés."""
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
# Tests du cooldown configurable
# ---------------------------------------------------------------------------


class TestCooldownConfigurable:
    async def test_cooldown_depuis_subentry(self, hass: HomeAssistant) -> None:
        """Le Throttler utilise le cooldown configuré dans la subentry."""
        subentry = _make_subentry("jardin")
        subentry.data[CONF_COOLDOWN] = 120
        coordinator = FrigateEventManagerCoordinator(
            hass, _make_entry(), subentry, event_source=_make_fake_event_source()
        )
        assert coordinator._throttler._cooldown == 120

    async def test_cooldown_defaut_si_absent(self, hass: HomeAssistant) -> None:
        """Sans CONF_COOLDOWN dans subentry → cooldown par défaut (60)."""
        coordinator = _make_coordinator(hass, cam_name="jardin")
        assert coordinator._throttler._cooldown == 60


# ---------------------------------------------------------------------------
# Tests du silent mode
# ---------------------------------------------------------------------------


class TestSilentMode:
    async def test_activate_silent_mode_bloque_notifications(
        self, hass: HomeAssistant
    ) -> None:
        """En mode silencieux, les événements new ne déclenchent pas de notification."""
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
        """activate_silent_mode met _silent_until dans le futur."""
        import time
        coordinator = _make_coordinator(hass)
        before = time.time()
        coordinator.activate_silent_mode()
        assert coordinator._silent_until > before

    async def test_silent_duration_depuis_subentry(self, hass: HomeAssistant) -> None:
        """_silent_duration correspond à la valeur de la subentry."""
        subentry = _make_subentry("jardin")
        subentry.data[CONF_SILENT_DURATION] = 45
        coordinator = FrigateEventManagerCoordinator(
            hass, _make_entry(), subentry, event_source=_make_fake_event_source()
        )
        assert coordinator._silent_duration == 45


# ---------------------------------------------------------------------------
# Tests du debounce
# ---------------------------------------------------------------------------


class TestDebounce:
    async def test_debounce_zero_envoie_immediatement(
        self, hass: HomeAssistant
    ) -> None:
        """Avec debounce=0, la notification est envoyée immédiatement."""
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
        """Avec debounce > 0, la notification n'est pas envoyée immédiatement."""
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
        # Pas de await block_till_done — la task est planifiée mais pas exécutée
        notifier.async_notify.assert_not_called()
        # Nettoyage
        if coordinator._debounce_task:
            coordinator._debounce_task.cancel()

    async def test_debounce_end_annule_task_et_libere_throttler(
        self, hass: HomeAssistant
    ) -> None:
        """Un événement end annule le debounce task en cours."""
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

        # La task a été annulée → aucune notification envoyée
        notifier.async_notify.assert_not_called()
        assert coordinator._debounce_task is None

    async def test_debounce_accumule_objects(self, hass: HomeAssistant) -> None:
        """Avec debounce, _pending_objects accumule les objets des événements."""
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


# ---------------------------------------------------------------------------
# Tests de la notification sur type=update
# ---------------------------------------------------------------------------


class TestNotificationUpdate:
    async def test_type_update_notifie_si_conditions_reunies(
        self, hass: HomeAssistant
    ) -> None:
        """Un événement update entraîne une notification si le throttle le permet."""
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
        """Un événement end ne déclenche jamais de notification."""
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
        """Caméra désactivée → aucune notification même sur new."""
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
# Tests de _debounce_send — exécution complète de la coroutine
# ---------------------------------------------------------------------------


class TestDebounceSend:
    async def test_debounce_send_envoie_notification_groupee(
        self, hass: HomeAssistant
    ) -> None:
        """_debounce_send() envoie une notification avec les objets accumulés."""
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

        # Simuler l'accumulation d'objets
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
        coordinator._debounce_seconds = 0  # pas d'attente pour le test

        await coordinator._debounce_send()

        notifier.async_notify.assert_called_once()
        call_args = notifier.async_notify.call_args[0][0]
        assert set(call_args.objects) == {"personne", "chien"}

    async def test_debounce_send_reinitialise_pending(
        self, hass: HomeAssistant
    ) -> None:
        """_debounce_send() vide _pending_objects et _pending_event après envoi."""
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
        """_debounce_send() sans _pending_event ne notifie pas."""
        notifier = AsyncMock()
        coordinator = FrigateEventManagerCoordinator(
            hass,
            _make_entry(),
            _make_subentry("jardin"),
            notifier=notifier,
            event_source=_make_fake_event_source(),
        )
        coordinator._debounce_seconds = 0
        # _pending_event vaut None par défaut

        await coordinator._debounce_send()

        notifier.async_notify.assert_not_called()

    async def test_debounce_send_cancellation_ne_notifie_pas(
        self, hass: HomeAssistant
    ) -> None:
        """Si _debounce_send() est annulée, aucune notification n'est envoyée."""
        import asyncio
        notifier = AsyncMock()
        subentry = _make_subentry("jardin")
        subentry.data[CONF_DEBOUNCE] = 10  # 10 secondes → sera annulée
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
        """async_stop() annule le debounce_task si actif."""
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
        # Déclencher le debounce via un événement new
        coordinator._handle_mqtt_message(_make_msg(PAYLOAD_NEW))
        assert coordinator._debounce_task is not None

        await coordinator.async_stop()

        assert coordinator._debounce_task is None
