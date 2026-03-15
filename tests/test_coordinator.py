"""Tests du coordinator MQTT Frigate Event Manager.

Couvre :
- _parse_event : payloads valides (type=new/update/end), invalides, malformés
- FrigateEventManagerCoordinator.async_start / async_stop
- _handle_mqtt_message : mise à jour des CameraState
- set_camera_enabled : activation/désactivation + notification listeners
- coordinator.data : format liste-de-dicts compatible sensor.py
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.core import HomeAssistant

from custom_components.frigate_event_manager.const import (
    CONF_MQTT_TOPIC,
    DEFAULT_MQTT_TOPIC,
)
from custom_components.frigate_event_manager.coordinator import (
    CameraState,
    FrigateEvent,
    FrigateEventManagerCoordinator,
    _parse_event,
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
        "camera": "garage",
        "severity": "alert",
        "objects": ["voiture"],
        "current_zones": ["parking"],
        "score": 0.88,
        "thumb_path": "/media/frigate/clips/garage-xyz.jpg",
        "id": "review-003",
        "start_time": 1710000020.0,
        "end_time": 1710000060.0,
    },
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_entry(topic: str = DEFAULT_MQTT_TOPIC) -> MagicMock:
    """Crée un ConfigEntry mock minimal."""
    entry = MagicMock()
    entry.entry_id = "test-entry-id"
    entry.data = {CONF_MQTT_TOPIC: topic}
    return entry


def _make_msg(payload: dict | str) -> SimpleNamespace:
    """Crée un message MQTT fake avec attribut payload."""
    if isinstance(payload, dict):
        payload = json.dumps(payload)
    return SimpleNamespace(payload=payload)


def _make_coordinator(
    hass: HomeAssistant,
    topic: str = DEFAULT_MQTT_TOPIC,
) -> FrigateEventManagerCoordinator:
    """Instancie un coordinator de test avec un ConfigEntry mock."""
    return FrigateEventManagerCoordinator(hass, _make_entry(topic))


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
        assert result.camera == "garage"
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
        """as_dict() expose toutes les clés attendues par sensor.py."""
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
    """Tests de _handle_mqtt_message : auto-découverte et mise à jour d'état."""

    async def test_type_new_cree_camera(self, hass: HomeAssistant) -> None:
        """Message type=new → auto-création CameraState avec motion=True."""
        coordinator = _make_coordinator(hass)

        coordinator._handle_mqtt_message(_make_msg(PAYLOAD_NEW))

        assert "jardin" in coordinator.cameras
        state = coordinator.cameras["jardin"]
        assert state.last_severity == "alert"
        assert state.last_objects == ["personne"]
        assert state.motion is True
        assert state.event_count_24h == 1

    async def test_type_new_incremente_event_count(self, hass: HomeAssistant) -> None:
        """Chaque message type=new incrémente event_count_24h."""
        coordinator = _make_coordinator(hass)

        for _ in range(3):
            coordinator._handle_mqtt_message(_make_msg(PAYLOAD_NEW))

        assert coordinator.cameras["jardin"].event_count_24h == 3

    async def test_type_update_ne_pas_incrementer_count(self, hass: HomeAssistant) -> None:
        """Message type=update n'incrémente PAS event_count_24h."""
        coordinator = _make_coordinator(hass)

        coordinator._handle_mqtt_message(_make_msg(PAYLOAD_NEW))
        coordinator._handle_mqtt_message(_make_msg(PAYLOAD_UPDATE))

        assert coordinator.cameras["jardin"].event_count_24h == 1

    async def test_type_update_met_a_jour_severity_et_objets(self, hass: HomeAssistant) -> None:
        """Message type=update met à jour last_severity et last_objects."""
        coordinator = _make_coordinator(hass)

        coordinator._handle_mqtt_message(_make_msg(PAYLOAD_NEW))
        coordinator._handle_mqtt_message(_make_msg(PAYLOAD_UPDATE))

        state = coordinator.cameras["jardin"]
        assert state.last_severity == "detection"
        assert state.last_objects == ["chien"]

    async def test_type_end_passe_motion_false(self, hass: HomeAssistant) -> None:
        """Message type=end passe motion à False."""
        coordinator = _make_coordinator(hass)

        new_garage = {"type": "new", "after": {"camera": "garage", "start_time": 1710000010.0}}
        coordinator._handle_mqtt_message(_make_msg(new_garage))
        assert coordinator.cameras["garage"].motion is True

        coordinator._handle_mqtt_message(_make_msg(PAYLOAD_END))

        assert coordinator.cameras["garage"].motion is False

    async def test_type_end_last_event_time_est_end_time(self, hass: HomeAssistant) -> None:
        """Pour type=end, last_event_time = end_time du payload."""
        coordinator = _make_coordinator(hass)

        new_garage = {"type": "new", "after": {"camera": "garage", "start_time": 1710000020.0}}
        coordinator._handle_mqtt_message(_make_msg(new_garage))
        coordinator._handle_mqtt_message(_make_msg(PAYLOAD_END))

        assert coordinator.cameras["garage"].last_event_time == pytest.approx(1710000060.0)

    async def test_payload_invalide_ne_crash_pas(self, hass: HomeAssistant) -> None:
        """Payload non-JSON → aucune modification des caméras, pas d'exception."""
        coordinator = _make_coordinator(hass)

        coordinator._handle_mqtt_message(_make_msg("pas du json {{{"))

        assert len(coordinator.cameras) == 0

    async def test_payload_type_inconnu_ignore(self, hass: HomeAssistant) -> None:
        """Type inconnu → ignoré silencieusement."""
        coordinator = _make_coordinator(hass)

        coordinator._handle_mqtt_message(_make_msg({"type": "heartbeat", "after": {"camera": "cam"}}))

        assert len(coordinator.cameras) == 0

    async def test_payload_sans_camera_ignore(self, hass: HomeAssistant) -> None:
        """Payload sans champ camera → ignoré silencieusement."""
        coordinator = _make_coordinator(hass)

        coordinator._handle_mqtt_message(_make_msg({"type": "new", "after": {"severity": "alert"}}))

        assert len(coordinator.cameras) == 0

    async def test_coordinator_data_est_liste_de_dicts(self, hass: HomeAssistant) -> None:
        """Après traitement, coordinator.data est une liste de dicts avec les clés sensor."""
        coordinator = _make_coordinator(hass)

        coordinator._handle_mqtt_message(_make_msg(PAYLOAD_NEW))

        assert isinstance(coordinator.data, list)
        assert len(coordinator.data) == 1
        cam_dict = coordinator.data[0]
        for key in ("name", "last_severity", "last_objects", "event_count_24h", "motion", "enabled"):
            assert key in cam_dict, f"Clé manquante dans coordinator.data : {key}"

    async def test_plusieurs_cameras_dans_data(self, hass: HomeAssistant) -> None:
        """coordinator.data contient une entrée par caméra découverte."""
        coordinator = _make_coordinator(hass)

        coordinator._handle_mqtt_message(_make_msg(PAYLOAD_NEW))    # jardin
        coordinator._handle_mqtt_message(_make_msg(PAYLOAD_END))    # garage

        noms = {d["name"] for d in coordinator.data}
        assert "jardin" in noms
        assert "garage" in noms

    async def test_cameras_property_retourne_camera_state(self, hass: HomeAssistant) -> None:
        """coordinator.cameras retourne un dict[str, CameraState]."""
        coordinator = _make_coordinator(hass)

        coordinator._handle_mqtt_message(_make_msg(PAYLOAD_NEW))

        assert isinstance(coordinator.cameras["jardin"], CameraState)


# ---------------------------------------------------------------------------
# Tests de set_camera_enabled
# ---------------------------------------------------------------------------


class TestSetCameraEnabled:
    """Tests de set_camera_enabled : modification d'état et notification listeners."""

    async def test_desactive_camera_existante(self, hass: HomeAssistant) -> None:
        """set_camera_enabled(cam, False) désactive une caméra existante."""
        coordinator = _make_coordinator(hass)
        coordinator._handle_mqtt_message(_make_msg(PAYLOAD_NEW))

        coordinator.set_camera_enabled("jardin", False)

        assert coordinator.cameras["jardin"].enabled is False

    async def test_reactive_camera(self, hass: HomeAssistant) -> None:
        """set_camera_enabled(cam, True) réactive une caméra désactivée."""
        coordinator = _make_coordinator(hass)
        coordinator._handle_mqtt_message(_make_msg(PAYLOAD_NEW))
        coordinator.set_camera_enabled("jardin", False)

        coordinator.set_camera_enabled("jardin", True)

        assert coordinator.cameras["jardin"].enabled is True

    async def test_cree_camera_inconnue(self, hass: HomeAssistant) -> None:
        """set_camera_enabled crée la CameraState si la caméra est inconnue."""
        coordinator = _make_coordinator(hass)

        coordinator.set_camera_enabled("nouvelle_cam", False)

        assert "nouvelle_cam" in coordinator.cameras
        assert coordinator.cameras["nouvelle_cam"].enabled is False

    async def test_notifie_les_listeners(self, hass: HomeAssistant) -> None:
        """set_camera_enabled notifie les listeners HA enregistrés."""
        coordinator = _make_coordinator(hass)
        coordinator._handle_mqtt_message(_make_msg(PAYLOAD_NEW))

        listener = MagicMock()
        coordinator.async_add_listener(listener)

        coordinator.set_camera_enabled("jardin", False)

        listener.assert_called()

    async def test_data_reflecte_enabled_false(self, hass: HomeAssistant) -> None:
        """coordinator.data reflète enabled=False après set_camera_enabled."""
        coordinator = _make_coordinator(hass)
        coordinator._handle_mqtt_message(_make_msg(PAYLOAD_NEW))

        coordinator.set_camera_enabled("jardin", False)

        cam_dict = next(d for d in coordinator.data if d["name"] == "jardin")
        assert cam_dict["enabled"] is False

    async def test_enabled_true_par_defaut(self, hass: HomeAssistant) -> None:
        """Caméra auto-découverte → enabled=True par défaut dans coordinator.data."""
        coordinator = _make_coordinator(hass)

        coordinator._handle_mqtt_message(_make_msg(PAYLOAD_NEW))

        cam_dict = next(d for d in coordinator.data if d["name"] == "jardin")
        assert cam_dict["enabled"] is True


# ---------------------------------------------------------------------------
# Tests de async_start / async_stop — mock de hass.components.mqtt
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
        """async_start() avec un hass entièrement mocké (sans boucle HA).

        Utilise __new__ pour éviter DataUpdateCoordinator.__init__.
        Le coordinator est en mode dégradé — seuls async_start et async_stop sont testés.
        """
        mock_unsubscribe = MagicMock()
        mock_subscribe = AsyncMock(return_value=mock_unsubscribe)

        mock_hass = MagicMock()

        # Bypasse __init__ pour créer un coordinator minimal sans boucle HA
        coordinator = object.__new__(FrigateEventManagerCoordinator)
        coordinator._entry = _make_entry()
        coordinator._mqtt_topic = DEFAULT_MQTT_TOPIC
        coordinator._cameras = {}
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
        """async_start() utilise le topic défini dans entry.data."""
        custom_topic = "frigate/events/perso"
        mock_unsubscribe = MagicMock()
        mock_subscribe = AsyncMock(return_value=mock_unsubscribe)

        mock_hass = MagicMock()

        coordinator = object.__new__(FrigateEventManagerCoordinator)
        coordinator._entry = _make_entry(topic=custom_topic)
        coordinator._mqtt_topic = custom_topic
        coordinator._cameras = {}
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
        mock_hass = MagicMock(spec=HomeAssistant)

        coordinator = object.__new__(FrigateEventManagerCoordinator)
        coordinator._entry = _make_entry()
        coordinator._mqtt_topic = DEFAULT_MQTT_TOPIC
        coordinator._cameras = {}
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

    async def test_retourne_liste_vide_si_pas_de_messages(self, hass: HomeAssistant) -> None:
        """Sans message MQTT reçu, _async_update_data retourne []."""
        coordinator = _make_coordinator(hass)

        result = await coordinator._async_update_data()

        assert result == []

    async def test_retourne_data_existante(self, hass: HomeAssistant) -> None:
        """Après des messages, _async_update_data retourne coordinator.data."""
        coordinator = _make_coordinator(hass)
        coordinator._handle_mqtt_message(_make_msg(PAYLOAD_NEW))

        result = await coordinator._async_update_data()

        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["name"] == "jardin"
