"""Tests du coordinator MQTT Frigate Event Manager.

Couvre :
- _parse_event : payloads valides (type=new/update/end), invalides, malformés
- FrigateEventManagerCoordinator.async_start / async_stop
- _handle_mqtt_message : mise à jour du CameraState unique
- set_camera_enabled : activation/désactivation + notification listeners
- coordinator.data : format dict compatible switch/binary_sensor
- _resolve_notify_target : fallback sur l'entrée globale
- async_setup_entry : comportement global vs caméra
"""

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
    DOMAIN,
)
from custom_components.frigate_event_manager.coordinator import (
    CameraState,
    FrigateEvent,
    FrigateEventManagerCoordinator,
    _parse_event,
    _resolve_notify_target,
)

# ---------------------------------------------------------------------------
# Fixtures réalistes Frigate
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
        "thumb_path": "",
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
        "thumb_path": "/media/frigate/clips/jardin-xyz.jpg",
        "id": "review-003",
        "start_time": 1710000020.0,
        "end_time": 1710000060.0,
    },
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_entry(
    cam_name: str = "jardin",
    notify_target: str | None = None,
) -> MagicMock:
    """Crée un ConfigEntry mock minimal pour une caméra."""
    entry = MagicMock()
    entry.entry_id = "test-entry-id"
    entry.data = {CONF_CAMERA: cam_name}
    if notify_target is not None:
        entry.data[CONF_NOTIFY_TARGET] = notify_target
    return entry


def _make_msg(payload: dict | str) -> SimpleNamespace:
    """Crée un message MQTT fake avec attribut payload."""
    if isinstance(payload, dict):
        payload = json.dumps(payload)
    return SimpleNamespace(payload=payload)


def _make_coordinator(
    hass: HomeAssistant,
    cam_name: str = "jardin",
    notify_target: str | None = None,
) -> FrigateEventManagerCoordinator:
    """Instancie un coordinator de test avec un ConfigEntry mock."""
    entry = _make_entry(cam_name, notify_target)
    # Patche hass.config_entries pour éviter les appels HA réels
    hass.config_entries.async_entry_for_domain_unique_id = MagicMock(return_value=None)
    return FrigateEventManagerCoordinator(hass, entry)


# ---------------------------------------------------------------------------
# Tests de _parse_event
# ---------------------------------------------------------------------------


class TestParseEvent:
    """Tests unitaires de la fonction _parse_event (pas de HA requis)."""

    def test_type_new_payload_complet(self) -> None:
        """Payload complet type=new → FrigateEvent avec tous les champs."""
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

    def test_type_update_payload_valide(self) -> None:
        """Payload type=update → FrigateEvent avec champs mis à jour."""
        result = _parse_event(json.dumps(PAYLOAD_UPDATE))

        assert result is not None
        assert result.type == "update"
        assert result.camera == "jardin"
        assert result.severity == "detection"
        assert result.objects == ["chien"]
        assert result.zones == []

    def test_type_end_expose_end_time(self) -> None:
        """Payload type=end → end_time correctement parsé."""
        result = _parse_event(json.dumps(PAYLOAD_END))

        assert result is not None
        assert result.type == "end"
        assert result.camera == "jardin"
        assert result.end_time == pytest.approx(1710000060.0)

    def test_champs_plats_sans_after(self) -> None:
        """Frigate peut envoyer les champs à la racine sans clé 'after'."""
        payload = {
            "type": "new",
            "camera": "salon",
            "severity": "detection",
            "objects": ["chat"],
            "zones": ["sejour"],
        }
        result = _parse_event(json.dumps(payload))

        assert result is not None
        assert result.camera == "salon"
        assert result.objects == ["chat"]

    def test_before_utilise_si_after_absent(self) -> None:
        """Si 'after' absent, le parser se replie sur 'before'."""
        payload = {
            "type": "end",
            "before": {
                "camera": "entree",
                "severity": "alert",
                "start_time": 1710000100.0,
                "end_time": 1710000200.0,
            },
        }
        result = _parse_event(json.dumps(payload))

        assert result is not None
        assert result.camera == "entree"
        assert result.end_time == pytest.approx(1710000200.0)

    def test_severity_par_defaut_est_detection(self) -> None:
        """Severity absente → valeur par défaut 'detection'."""
        payload = {"type": "new", "after": {"camera": "piscine"}}
        result = _parse_event(json.dumps(payload))

        assert result is not None
        assert result.severity == "detection"

    def test_objets_et_zones_par_defaut_vides(self) -> None:
        """objects et zones absents → listes vides par défaut."""
        payload = {"type": "new", "after": {"camera": "terrasse"}}
        result = _parse_event(json.dumps(payload))

        assert result is not None
        assert result.objects == []
        assert result.zones == []

    def test_score_par_defaut_zero(self) -> None:
        """Score absent → 0.0 par défaut."""
        payload = {"type": "new", "after": {"camera": "terrasse"}}
        result = _parse_event(json.dumps(payload))

        assert result is not None
        assert result.score == pytest.approx(0.0)

    def test_thumb_path_et_review_id_par_defaut_vides(self) -> None:
        """thumb_path et review_id absents → chaînes vides."""
        payload = {"type": "new", "after": {"camera": "cour"}}
        result = _parse_event(json.dumps(payload))

        assert result is not None
        assert result.thumb_path == ""
        assert result.review_id == ""

    def test_json_invalide_retourne_none(self) -> None:
        """Payload non-JSON → None (sans exception)."""
        result = _parse_event("pas du json {{ invalide")

        assert result is None

    def test_chaine_vide_retourne_none(self) -> None:
        """Payload chaîne vide → None."""
        result = _parse_event("")

        assert result is None

    def test_none_retourne_none(self) -> None:
        """None passé en argument → None (sans exception)."""
        result = _parse_event(None)  # type: ignore[arg-type]

        assert result is None

    def test_type_inconnu_retourne_none(self) -> None:
        """Type non reconnu ('heartbeat') → None."""
        payload = {"type": "heartbeat", "after": {"camera": "jardin"}}
        result = _parse_event(json.dumps(payload))

        assert result is None

    def test_type_manquant_retourne_none(self) -> None:
        """Payload sans champ 'type' → None."""
        payload = {"after": {"camera": "jardin"}}
        result = _parse_event(json.dumps(payload))

        assert result is None

    def test_camera_manquante_retourne_none(self) -> None:
        """Type valide mais sans camera → None."""
        payload = {"type": "new", "after": {"severity": "alert"}}
        result = _parse_event(json.dumps(payload))

        assert result is None

    def test_json_liste_retourne_none(self) -> None:
        """JSON valide mais non-dict (liste) → None."""
        result = _parse_event(json.dumps(["new", "jardin"]))

        assert result is None


# ---------------------------------------------------------------------------
# Tests de CameraState
# ---------------------------------------------------------------------------


class TestCameraState:
    """Tests de la dataclass CameraState."""

    def test_as_dict_contient_cles_sensor(self) -> None:
        """as_dict() expose toutes les clés attendues."""
        state = CameraState(
            name="jardin",
            last_severity="alert",
            last_objects=["personne"],
            event_count_24h=3,
            last_event_time=1710000000.0,
            motion=True,
            enabled=True,
        )
        d = state.as_dict()

        assert d["name"] == "jardin"
        assert d["last_severity"] == "alert"
        assert d["last_objects"] == ["personne"]
        assert d["event_count_24h"] == 3
        assert d["last_event_time"] == pytest.approx(1710000000.0)
        assert d["motion"] is True
        assert d["enabled"] is True

    def test_valeurs_par_defaut(self) -> None:
        """Valeurs par défaut de CameraState correctes."""
        state = CameraState(name="cam")

        assert state.last_severity is None
        assert state.last_objects == []
        assert state.event_count_24h == 0
        assert state.last_event_time is None
        assert state.motion is False
        assert state.enabled is True

    def test_as_dict_enabled_false(self) -> None:
        """as_dict() retourne enabled=False si la caméra est désactivée."""
        state = CameraState(name="cam_off", enabled=False)

        assert state.as_dict()["enabled"] is False


# ---------------------------------------------------------------------------
# Tests du coordinator — traitement des messages MQTT
# ---------------------------------------------------------------------------


class TestHandleMqttMessage:
    """Tests de _handle_mqtt_message : filtrage par caméra et mise à jour d'état."""

    async def test_type_new_met_a_jour_etat(self, hass: HomeAssistant) -> None:
        """Message type=new → CameraState mis à jour avec motion=True."""
        coordinator = _make_coordinator(hass, cam_name="jardin")

        coordinator._handle_mqtt_message(_make_msg(PAYLOAD_NEW))

        state = coordinator.camera_state
        assert state.last_severity == "alert"
        assert state.last_objects == ["personne"]
        assert state.motion is True
        assert state.event_count_24h == 1

    async def test_type_new_incremente_event_count(self, hass: HomeAssistant) -> None:
        """Chaque message type=new incrémente event_count_24h."""
        coordinator = _make_coordinator(hass, cam_name="jardin")

        for _ in range(3):
            coordinator._handle_mqtt_message(_make_msg(PAYLOAD_NEW))

        assert coordinator.camera_state.event_count_24h == 3

    async def test_type_update_ne_pas_incrementer_count(self, hass: HomeAssistant) -> None:
        """Message type=update n'incrémente PAS event_count_24h."""
        coordinator = _make_coordinator(hass, cam_name="jardin")

        coordinator._handle_mqtt_message(_make_msg(PAYLOAD_NEW))
        coordinator._handle_mqtt_message(_make_msg(PAYLOAD_UPDATE))

        assert coordinator.camera_state.event_count_24h == 1

    async def test_type_update_met_a_jour_severity_et_objets(self, hass: HomeAssistant) -> None:
        """Message type=update met à jour last_severity et last_objects."""
        coordinator = _make_coordinator(hass, cam_name="jardin")

        coordinator._handle_mqtt_message(_make_msg(PAYLOAD_NEW))
        coordinator._handle_mqtt_message(_make_msg(PAYLOAD_UPDATE))

        state = coordinator.camera_state
        assert state.last_severity == "detection"
        assert state.last_objects == ["chien"]

    async def test_type_end_passe_motion_false(self, hass: HomeAssistant) -> None:
        """Message type=end passe motion à False."""
        coordinator = _make_coordinator(hass, cam_name="jardin")

        coordinator._handle_mqtt_message(_make_msg(PAYLOAD_NEW))
        assert coordinator.camera_state.motion is True

        coordinator._handle_mqtt_message(_make_msg(PAYLOAD_END))

        assert coordinator.camera_state.motion is False

    async def test_type_end_last_event_time_est_end_time(self, hass: HomeAssistant) -> None:
        """Pour type=end, last_event_time = end_time du payload."""
        coordinator = _make_coordinator(hass, cam_name="jardin")

        coordinator._handle_mqtt_message(_make_msg(PAYLOAD_NEW))
        coordinator._handle_mqtt_message(_make_msg(PAYLOAD_END))

        assert coordinator.camera_state.last_event_time == pytest.approx(1710000060.0)

    async def test_payload_invalide_ne_crash_pas(self, hass: HomeAssistant) -> None:
        """Payload non-JSON → aucune modification de l'état, pas d'exception."""
        coordinator = _make_coordinator(hass, cam_name="jardin")

        coordinator._handle_mqtt_message(_make_msg("pas du json {{{"))

        # état inchangé (motion=False par défaut)
        assert coordinator.camera_state.motion is False
        assert coordinator.camera_state.event_count_24h == 0

    async def test_payload_type_inconnu_ignore(self, hass: HomeAssistant) -> None:
        """Type inconnu → ignoré silencieusement."""
        coordinator = _make_coordinator(hass, cam_name="jardin")

        coordinator._handle_mqtt_message(_make_msg({"type": "heartbeat", "after": {"camera": "jardin"}}))

        assert coordinator.camera_state.event_count_24h == 0

    async def test_payload_sans_camera_ignore(self, hass: HomeAssistant) -> None:
        """Payload sans champ camera → ignoré silencieusement."""
        coordinator = _make_coordinator(hass, cam_name="jardin")

        coordinator._handle_mqtt_message(_make_msg({"type": "new", "after": {"severity": "alert"}}))

        assert coordinator.camera_state.event_count_24h == 0

    async def test_autre_camera_ignoree(self, hass: HomeAssistant) -> None:
        """Payload d'une autre caméra → ignoré (filtrage par nom de caméra)."""
        coordinator = _make_coordinator(hass, cam_name="garage")

        coordinator._handle_mqtt_message(_make_msg(PAYLOAD_NEW))  # camera=jardin

        assert coordinator.camera_state.event_count_24h == 0
        assert coordinator.camera_state.motion is False

    async def test_coordinator_data_est_dict(self, hass: HomeAssistant) -> None:
        """Après traitement, coordinator.data est un dict avec les clés CameraState."""
        coordinator = _make_coordinator(hass, cam_name="jardin")

        coordinator._handle_mqtt_message(_make_msg(PAYLOAD_NEW))

        assert isinstance(coordinator.data, dict)
        for key in ("name", "last_severity", "last_objects", "event_count_24h", "motion", "enabled"):
            assert key in coordinator.data, f"Clé manquante dans coordinator.data : {key}"

    async def test_camera_property_retourne_nom(self, hass: HomeAssistant) -> None:
        """coordinator.camera retourne le nom de la caméra configurée."""
        coordinator = _make_coordinator(hass, cam_name="salon")

        assert coordinator.camera == "salon"

    async def test_camera_state_property_retourne_camera_state(self, hass: HomeAssistant) -> None:
        """coordinator.camera_state retourne le CameraState de la caméra."""
        coordinator = _make_coordinator(hass, cam_name="jardin")

        assert isinstance(coordinator.camera_state, CameraState)
        assert coordinator.camera_state.name == "jardin"


# ---------------------------------------------------------------------------
# Tests de set_camera_enabled
# ---------------------------------------------------------------------------


class TestSetCameraEnabled:
    """Tests de set_camera_enabled : modification d'état et notification listeners."""

    async def test_desactive_camera(self, hass: HomeAssistant) -> None:
        """set_camera_enabled(False) désactive la caméra."""
        coordinator = _make_coordinator(hass, cam_name="jardin")

        coordinator.set_camera_enabled(False)

        assert coordinator.camera_state.enabled is False

    async def test_reactive_camera(self, hass: HomeAssistant) -> None:
        """set_camera_enabled(True) réactive une caméra désactivée."""
        coordinator = _make_coordinator(hass, cam_name="jardin")
        coordinator.set_camera_enabled(False)

        coordinator.set_camera_enabled(True)

        assert coordinator.camera_state.enabled is True

    async def test_notifie_les_listeners(self, hass: HomeAssistant) -> None:
        """set_camera_enabled notifie les listeners HA enregistrés."""
        coordinator = _make_coordinator(hass, cam_name="jardin")

        listener = MagicMock()
        coordinator.async_add_listener(listener)

        coordinator.set_camera_enabled(False)

        listener.assert_called()

    async def test_data_reflecte_enabled_false(self, hass: HomeAssistant) -> None:
        """coordinator.data reflète enabled=False après set_camera_enabled."""
        coordinator = _make_coordinator(hass, cam_name="jardin")

        coordinator.set_camera_enabled(False)

        assert coordinator.data["enabled"] is False

    async def test_enabled_true_par_defaut(self, hass: HomeAssistant) -> None:
        """Caméra configurée → enabled=True par défaut."""
        coordinator = _make_coordinator(hass, cam_name="jardin")

        assert coordinator.camera_state.enabled is True


# ---------------------------------------------------------------------------
# Tests de async_start / async_stop — mock de mqtt.async_subscribe
# ---------------------------------------------------------------------------


class TestAsyncStartStop:
    """Tests de async_start et async_stop avec mock de MQTT."""

    async def test_async_stop_appelle_unsubscribe(self, hass: HomeAssistant) -> None:
        """async_stop() appelle le callback d'unsubscribe et le réinitialise à None."""
        coordinator = _make_coordinator(hass)
        mock_unsubscribe = MagicMock()
        coordinator._unsubscribe_mqtt = mock_unsubscribe

        await coordinator.async_stop()

        mock_unsubscribe.assert_called_once()
        assert coordinator._unsubscribe_mqtt is None

    async def test_async_stop_sans_souscription_ne_crash_pas(self, hass: HomeAssistant) -> None:
        """async_stop() sans souscription active ne lève pas d'exception."""
        coordinator = _make_coordinator(hass)
        assert coordinator._unsubscribe_mqtt is None

        await coordinator.async_stop()

    async def test_async_start_appelle_subscribe_mock_direct(self) -> None:
        """async_start() souscrit au topic MQTT configuré.

        Utilise __new__ pour éviter DataUpdateCoordinator.__init__.
        """
        mock_unsubscribe = MagicMock()
        mock_subscribe = AsyncMock(return_value=mock_unsubscribe)

        mock_hass = MagicMock()

        coordinator = object.__new__(FrigateEventManagerCoordinator)
        coordinator._entry = _make_entry()
        coordinator._camera = "jardin"
        coordinator._mqtt_topic = DEFAULT_MQTT_TOPIC
        coordinator._camera_state = CameraState(name="jardin")
        coordinator._unsubscribe_mqtt = None
        coordinator.hass = mock_hass

        with patch(
            "custom_components.frigate_event_manager.coordinator.mqtt.async_subscribe",
            mock_subscribe,
        ):
            await coordinator.async_start()

        mock_subscribe.assert_called_once_with(
            mock_hass,
            DEFAULT_MQTT_TOPIC,
            coordinator._handle_mqtt_message,
        )
        assert coordinator._unsubscribe_mqtt is mock_unsubscribe

    async def test_async_start_topic_personnalise_mock_direct(self) -> None:
        """async_start() utilise le topic défini dans _mqtt_topic."""
        custom_topic = "frigate/events/perso"
        mock_unsubscribe = MagicMock()
        mock_subscribe = AsyncMock(return_value=mock_unsubscribe)

        mock_hass = MagicMock()

        coordinator = object.__new__(FrigateEventManagerCoordinator)
        coordinator._entry = _make_entry()
        coordinator._camera = "jardin"
        coordinator._mqtt_topic = custom_topic
        coordinator._camera_state = CameraState(name="jardin")
        coordinator._unsubscribe_mqtt = None
        coordinator.hass = mock_hass

        with patch(
            "custom_components.frigate_event_manager.coordinator.mqtt.async_subscribe",
            mock_subscribe,
        ):
            await coordinator.async_start()

        mock_subscribe.assert_called_once_with(
            mock_hass,
            custom_topic,
            coordinator._handle_mqtt_message,
        )

    async def test_async_stop_mock_direct(self) -> None:
        """async_stop() avec hass mocké appelle unsubscribe et remet à None."""
        mock_unsubscribe = MagicMock()
        mock_hass = MagicMock()

        coordinator = object.__new__(FrigateEventManagerCoordinator)
        coordinator._entry = _make_entry()
        coordinator._camera = "jardin"
        coordinator._mqtt_topic = DEFAULT_MQTT_TOPIC
        coordinator._camera_state = CameraState(name="jardin")
        coordinator._unsubscribe_mqtt = mock_unsubscribe
        coordinator.hass = mock_hass

        await coordinator.async_stop()

        mock_unsubscribe.assert_called_once()
        assert coordinator._unsubscribe_mqtt is None


# ---------------------------------------------------------------------------
# Tests de _async_update_data
# ---------------------------------------------------------------------------


class TestAsyncUpdateData:
    """Tests de _async_update_data (méthode de fallback push-only)."""

    async def test_retourne_dict_vide_si_pas_de_messages(self, hass: HomeAssistant) -> None:
        """Sans message MQTT reçu, _async_update_data retourne {}."""
        coordinator = _make_coordinator(hass)

        result = await coordinator._async_update_data()

        assert result == {}

    async def test_retourne_data_existante(self, hass: HomeAssistant) -> None:
        """Après des messages, _async_update_data retourne coordinator.data."""
        coordinator = _make_coordinator(hass, cam_name="jardin")
        coordinator._handle_mqtt_message(_make_msg(PAYLOAD_NEW))

        result = await coordinator._async_update_data()

        assert isinstance(result, dict)
        assert result["name"] == "jardin"


# ---------------------------------------------------------------------------
# Tests de _resolve_notify_target
# ---------------------------------------------------------------------------


class TestResolveNotifyTarget:
    """Tests de _resolve_notify_target : priorité locale vs globale."""

    def test_retourne_notify_target_local(self) -> None:
        """entry.data["notify_target"] non-None → retourné directement."""
        hass = MagicMock()
        entry = MagicMock()
        entry.data = {CONF_NOTIFY_TARGET: "notify.mobile_app_phone"}

        result = _resolve_notify_target(hass, entry)

        assert result == "notify.mobile_app_phone"
        hass.config_entries.async_entry_for_domain_unique_id.assert_not_called()

    def test_fallback_sur_entree_globale(self) -> None:
        """notify_target absent → fallback sur l'entrée globale."""
        global_entry = MagicMock()
        global_entry.data = {CONF_NOTIFY_TARGET: "notify.global_target"}

        hass = MagicMock()
        hass.config_entries.async_entry_for_domain_unique_id.return_value = global_entry

        entry = MagicMock()
        entry.data = {}

        result = _resolve_notify_target(hass, entry)

        assert result == "notify.global_target"
        hass.config_entries.async_entry_for_domain_unique_id.assert_called_once_with(DOMAIN, DOMAIN)

    def test_retourne_none_si_pas_de_target(self) -> None:
        """Ni local ni global → None."""
        hass = MagicMock()
        hass.config_entries.async_entry_for_domain_unique_id.return_value = None

        entry = MagicMock()
        entry.data = {}

        result = _resolve_notify_target(hass, entry)

        assert result is None

    def test_retourne_none_si_entree_globale_sans_target(self) -> None:
        """Entrée globale présente mais sans notify_target → None."""
        global_entry = MagicMock()
        global_entry.data = {}

        hass = MagicMock()
        hass.config_entries.async_entry_for_domain_unique_id.return_value = global_entry

        entry = MagicMock()
        entry.data = {}

        result = _resolve_notify_target(hass, entry)

        assert result is None


# ---------------------------------------------------------------------------
# Tests de async_setup_entry (__init__.py)
# ---------------------------------------------------------------------------


class TestAsyncSetupEntry:
    """Tests de async_setup_entry : global vs caméra."""

    async def test_entree_globale_retourne_true_sans_coordinator(self, hass: HomeAssistant) -> None:
        """Entrée globale (sans CONF_CAMERA) → True sans coordinator."""
        from custom_components.frigate_event_manager import async_setup_entry

        entry = MagicMock()
        entry.data = {"url": "http://localhost:5000", CONF_NOTIFY_TARGET: "notify.test"}
        # Pas de CONF_CAMERA dans entry.data

        result = await async_setup_entry(hass, entry)

        assert result is True
        assert DOMAIN not in hass.data or entry.entry_id not in hass.data.get(DOMAIN, {})

    async def test_entree_camera_cree_coordinator(self, hass: HomeAssistant) -> None:
        """Entrée caméra → coordinator créé dans hass.data[DOMAIN][entry.entry_id]."""
        from custom_components.frigate_event_manager import async_setup_entry

        entry = MagicMock()
        entry.entry_id = "cam-entry-id"
        entry.data = {CONF_CAMERA: "jardin"}

        hass.config_entries.async_entry_for_domain_unique_id = MagicMock(return_value=None)

        with patch(
            "custom_components.frigate_event_manager.coordinator.mqtt.async_subscribe",
            AsyncMock(return_value=MagicMock()),
        ):
            hass.config_entries.async_forward_entry_setups = AsyncMock(return_value=True)
            result = await async_setup_entry(hass, entry)

        assert result is True
        assert hass.data[DOMAIN]["cam-entry-id"] is not None
        coordinator = hass.data[DOMAIN]["cam-entry-id"]
        assert isinstance(coordinator, FrigateEventManagerCoordinator)
        assert coordinator.camera == "jardin"
