"""Tests des entités HA — sensor, switch, binary_sensor.

Couvre :
- FrigateLastSeveritySensor.native_value
- FrigateLastObjectSensor.native_value + extra_state_attributes
- FrigateEventCountSensor.native_value
- FrigateNotificationSwitch.is_on + async_turn_on/off
- FrigateMotionSensor.is_on + device_class

Stratégie : mock du coordinator (MagicMock) avec coordinator.data
fourni comme liste de dicts au format CameraState.as_dict().
CoordinatorEntity.__init__ est patché en no-op pour éviter
les dépendances HA (hass, event bus, etc.).
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from homeassistant.components.binary_sensor import BinarySensorDeviceClass

from custom_components.frigate_event_manager.binary_sensor import FrigateMotionSensor
from custom_components.frigate_event_manager.coordinator import CameraState
from custom_components.frigate_event_manager.sensor import (
    FrigateEventCountSensor,
    FrigateLastObjectSensor,
    FrigateLastSeveritySensor,
)
from custom_components.frigate_event_manager.switch import FrigateNotificationSwitch

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_NOOP = "homeassistant.helpers.update_coordinator.CoordinatorEntity.__init__"


def _make_coordinator(cam_dicts: list[dict]) -> MagicMock:
    """Construit un coordinator mocké dont .data vaut la liste fournie."""
    coordinator = MagicMock()
    coordinator.data = cam_dicts
    return coordinator


def _cam_dict(
    name: str = "jardin",
    last_severity: str | None = "alert",
    last_objects: list[str] | None = None,
    event_count_24h: int = 5,
    motion: bool = False,
    enabled: bool = True,
) -> dict:
    """Retourne un dict conforme à CameraState.as_dict()."""
    return CameraState(
        name=name,
        last_severity=last_severity,
        last_objects=last_objects if last_objects is not None else ["personne"],
        event_count_24h=event_count_24h,
        motion=motion,
        enabled=enabled,
    ).as_dict()


# ---------------------------------------------------------------------------
# FrigateLastSeveritySensor
# ---------------------------------------------------------------------------


class TestFrigateLastSeveritySensor:
    """Tests de FrigateLastSeveritySensor."""

    def _build(self, cam_dicts: list[dict], cam_name: str = "jardin") -> FrigateLastSeveritySensor:
        coordinator = _make_coordinator(cam_dicts)
        with patch(_NOOP, return_value=None):
            sensor = FrigateLastSeveritySensor(coordinator, cam_name)
        sensor.coordinator = coordinator
        return sensor

    def test_native_value_retourne_last_severity(self) -> None:
        """Cas nominal : native_value vaut last_severity de la caméra."""
        sensor = self._build([_cam_dict(last_severity="alert")])
        assert sensor.native_value == "alert"

    def test_native_value_detection(self) -> None:
        """native_value vaut 'detection' quand la sévérité est detection."""
        sensor = self._build([_cam_dict(last_severity="detection")])
        assert sensor.native_value == "detection"

    def test_native_value_none_quand_non_defini(self) -> None:
        """native_value vaut None quand last_severity est None."""
        sensor = self._build([_cam_dict(last_severity=None)])
        assert sensor.native_value is None

    def test_native_value_none_camera_inconnue(self) -> None:
        """native_value vaut None quand la caméra n'est pas dans coordinator.data."""
        sensor = self._build([_cam_dict(name="autre")], cam_name="jardin")
        assert sensor.native_value is None

    def test_native_value_coordinator_data_vide(self) -> None:
        """native_value vaut None quand coordinator.data est vide."""
        sensor = self._build([])
        assert sensor.native_value is None

    def test_native_value_coordinator_data_none(self) -> None:
        """native_value vaut None quand coordinator.data est None."""
        sensor = self._build([])
        sensor.coordinator.data = None
        assert sensor.native_value is None

    def test_unique_id(self) -> None:
        """unique_id suit le format fem_{cam}_last_severity."""
        sensor = self._build([_cam_dict()], cam_name="garage")
        assert sensor._attr_unique_id == "fem_garage_last_severity"

    def test_plusieurs_cameras_isole_bonne(self) -> None:
        """Retourne la sévérité de la bonne caméra quand plusieurs sont présentes."""
        data = [
            _cam_dict(name="jardin", last_severity="alert"),
            _cam_dict(name="garage", last_severity="detection"),
        ]
        sensor = self._build(data, cam_name="garage")
        assert sensor.native_value == "detection"


# ---------------------------------------------------------------------------
# FrigateLastObjectSensor
# ---------------------------------------------------------------------------


class TestFrigateLastObjectSensor:
    """Tests de FrigateLastObjectSensor."""

    def _build(self, cam_dicts: list[dict], cam_name: str = "jardin") -> FrigateLastObjectSensor:
        coordinator = _make_coordinator(cam_dicts)
        with patch(_NOOP, return_value=None):
            sensor = FrigateLastObjectSensor(coordinator, cam_name)
        sensor.coordinator = coordinator
        return sensor

    def test_native_value_retourne_premier_objet(self) -> None:
        """native_value retourne le premier élément de last_objects."""
        sensor = self._build([_cam_dict(last_objects=["personne", "voiture"])])
        assert sensor.native_value == "personne"

    def test_native_value_un_seul_objet(self) -> None:
        """native_value retourne le seul objet quand la liste en contient un."""
        sensor = self._build([_cam_dict(last_objects=["chien"])])
        assert sensor.native_value == "chien"

    def test_native_value_none_liste_vide(self) -> None:
        """native_value est None quand last_objects est vide."""
        sensor = self._build([_cam_dict(last_objects=[])])
        assert sensor.native_value is None

    def test_native_value_none_camera_inconnue(self) -> None:
        """native_value est None quand la caméra est absente."""
        sensor = self._build([_cam_dict(name="autre")], cam_name="jardin")
        assert sensor.native_value is None

    def test_extra_state_attributes_contient_all_objects(self) -> None:
        """extra_state_attributes expose all_objects avec la liste complète."""
        sensor = self._build([_cam_dict(last_objects=["personne", "voiture"])])
        attrs = sensor.extra_state_attributes
        assert "all_objects" in attrs
        assert attrs["all_objects"] == ["personne", "voiture"]

    def test_extra_state_attributes_liste_vide(self) -> None:
        """extra_state_attributes contient all_objects=[] quand pas d'objet."""
        sensor = self._build([_cam_dict(last_objects=[])])
        assert sensor.extra_state_attributes["all_objects"] == []

    def test_extra_state_attributes_camera_inconnue(self) -> None:
        """extra_state_attributes contient all_objects=[] quand caméra absente."""
        sensor = self._build([], cam_name="jardin")
        assert sensor.extra_state_attributes["all_objects"] == []

    def test_unique_id(self) -> None:
        """unique_id suit le format fem_{cam}_last_object."""
        sensor = self._build([_cam_dict()], cam_name="entree")
        assert sensor._attr_unique_id == "fem_entree_last_object"

    def test_plusieurs_cameras_isole_bonne(self) -> None:
        """Retourne les objets de la bonne caméra quand plusieurs sont présentes."""
        data = [
            _cam_dict(name="jardin", last_objects=["personne"]),
            _cam_dict(name="garage", last_objects=["voiture"]),
        ]
        sensor = self._build(data, cam_name="garage")
        assert sensor.native_value == "voiture"
        assert sensor.extra_state_attributes["all_objects"] == ["voiture"]


# ---------------------------------------------------------------------------
# FrigateEventCountSensor
# ---------------------------------------------------------------------------


class TestFrigateEventCountSensor:
    """Tests de FrigateEventCountSensor."""

    def _build(self, cam_dicts: list[dict], cam_name: str = "jardin") -> FrigateEventCountSensor:
        coordinator = _make_coordinator(cam_dicts)
        with patch(_NOOP, return_value=None):
            sensor = FrigateEventCountSensor(coordinator, cam_name)
        sensor.coordinator = coordinator
        return sensor

    def test_native_value_retourne_event_count_24h(self) -> None:
        """native_value retourne le compteur d'événements 24h."""
        sensor = self._build([_cam_dict(event_count_24h=7)])
        assert sensor.native_value == 7

    def test_native_value_zero(self) -> None:
        """native_value retourne 0 quand aucun événement."""
        sensor = self._build([_cam_dict(event_count_24h=0)])
        assert sensor.native_value == 0

    def test_native_value_none_camera_inconnue(self) -> None:
        """native_value est None quand la caméra est absente."""
        sensor = self._build([_cam_dict(name="autre")], cam_name="jardin")
        assert sensor.native_value is None

    def test_native_value_coordinator_data_vide(self) -> None:
        """native_value est None quand coordinator.data est vide."""
        sensor = self._build([])
        assert sensor.native_value is None

    def test_unit_of_measurement(self) -> None:
        """La propriété native_unit_of_measurement est définie."""
        sensor = self._build([_cam_dict()])
        assert sensor._attr_native_unit_of_measurement == "événements"

    def test_unique_id(self) -> None:
        """unique_id suit le format fem_{cam}_event_count_24h."""
        sensor = self._build([_cam_dict()], cam_name="piscine")
        assert sensor._attr_unique_id == "fem_piscine_event_count_24h"

    def test_plusieurs_cameras_isole_bonne(self) -> None:
        """Retourne le compteur de la bonne caméra quand plusieurs sont présentes."""
        data = [
            _cam_dict(name="jardin", event_count_24h=3),
            _cam_dict(name="garage", event_count_24h=12),
        ]
        sensor = self._build(data, cam_name="garage")
        assert sensor.native_value == 12


# ---------------------------------------------------------------------------
# FrigateNotificationSwitch
# ---------------------------------------------------------------------------


class TestFrigateNotificationSwitch:
    """Tests de FrigateNotificationSwitch."""

    def _build(self, cam_dicts: list[dict], cam_name: str = "jardin") -> FrigateNotificationSwitch:
        coordinator = _make_coordinator(cam_dicts)
        with patch(_NOOP, return_value=None):
            switch = FrigateNotificationSwitch(coordinator, cam_name)
        switch.coordinator = coordinator
        return switch

    def test_is_on_retourne_enabled_true(self) -> None:
        """is_on retourne True quand enabled=True."""
        switch = self._build([_cam_dict(enabled=True)])
        assert switch.is_on is True

    def test_is_on_retourne_enabled_false(self) -> None:
        """is_on retourne False quand enabled=False."""
        switch = self._build([_cam_dict(enabled=False)])
        assert switch.is_on is False

    def test_is_on_true_par_defaut_camera_inconnue(self) -> None:
        """is_on retourne True quand la caméra n'est pas dans coordinator.data."""
        switch = self._build([_cam_dict(name="autre")], cam_name="jardin")
        assert switch.is_on is True

    def test_is_on_true_par_defaut_data_vide(self) -> None:
        """is_on retourne True quand coordinator.data est vide."""
        switch = self._build([])
        assert switch.is_on is True

    def test_is_on_true_par_defaut_data_none(self) -> None:
        """is_on retourne True quand coordinator.data est None."""
        switch = self._build([])
        switch.coordinator.data = None
        assert switch.is_on is True

    async def test_async_turn_on_appelle_set_camera_enabled_true(self) -> None:
        """async_turn_on appelle coordinator.set_camera_enabled avec enabled=True."""
        switch = self._build([_cam_dict(enabled=False)])
        await switch.async_turn_on()
        switch.coordinator.set_camera_enabled.assert_called_once_with("jardin", True)

    async def test_async_turn_off_appelle_set_camera_enabled_false(self) -> None:
        """async_turn_off appelle coordinator.set_camera_enabled avec enabled=False."""
        switch = self._build([_cam_dict(enabled=True)])
        await switch.async_turn_off()
        switch.coordinator.set_camera_enabled.assert_called_once_with("jardin", False)

    async def test_async_turn_on_nom_camera_correct(self) -> None:
        """async_turn_on passe le bon nom de caméra au coordinator."""
        switch = self._build([_cam_dict(name="garage", enabled=False)], cam_name="garage")
        await switch.async_turn_on()
        switch.coordinator.set_camera_enabled.assert_called_once_with("garage", True)

    async def test_async_turn_off_nom_camera_correct(self) -> None:
        """async_turn_off passe le bon nom de caméra au coordinator."""
        switch = self._build([_cam_dict(name="garage", enabled=True)], cam_name="garage")
        await switch.async_turn_off()
        switch.coordinator.set_camera_enabled.assert_called_once_with("garage", False)

    def test_unique_id(self) -> None:
        """unique_id suit le format fem_{cam}_notifications."""
        switch = self._build([_cam_dict()], cam_name="entree")
        assert switch._attr_unique_id == "fem_entree_notifications"

    def test_plusieurs_cameras_isole_bonne(self) -> None:
        """is_on retourne l'état de la bonne caméra quand plusieurs sont présentes."""
        data = [
            _cam_dict(name="jardin", enabled=True),
            _cam_dict(name="garage", enabled=False),
        ]
        switch = self._build(data, cam_name="garage")
        assert switch.is_on is False

    async def test_async_turn_on_avec_kwargs_ne_plante_pas(self) -> None:
        """async_turn_on accepte des kwargs arbitraires sans erreur."""
        switch = self._build([_cam_dict()])
        await switch.async_turn_on(transition=1)
        switch.coordinator.set_camera_enabled.assert_called_once_with("jardin", True)

    async def test_async_turn_off_avec_kwargs_ne_plante_pas(self) -> None:
        """async_turn_off accepte des kwargs arbitraires sans erreur."""
        switch = self._build([_cam_dict()])
        await switch.async_turn_off(transition=1)
        switch.coordinator.set_camera_enabled.assert_called_once_with("jardin", False)


# ---------------------------------------------------------------------------
# FrigateMotionSensor
# ---------------------------------------------------------------------------


class TestFrigateMotionSensor:
    """Tests de FrigateMotionSensor."""

    def _build(self, cam_dicts: list[dict], cam_name: str = "jardin") -> FrigateMotionSensor:
        coordinator = _make_coordinator(cam_dicts)
        with patch(_NOOP, return_value=None):
            sensor = FrigateMotionSensor(coordinator, cam_name)
        sensor.coordinator = coordinator
        return sensor

    def test_is_on_true_quand_motion_true(self) -> None:
        """is_on retourne True quand motion=True (événement type=new actif)."""
        sensor = self._build([_cam_dict(motion=True)])
        assert sensor.is_on is True

    def test_is_on_false_quand_motion_false(self) -> None:
        """is_on retourne False quand motion=False (aucun mouvement actif)."""
        sensor = self._build([_cam_dict(motion=False)])
        assert sensor.is_on is False

    def test_is_on_none_camera_inconnue(self) -> None:
        """is_on retourne None quand la caméra n'est pas dans coordinator.data."""
        sensor = self._build([_cam_dict(name="autre")], cam_name="jardin")
        assert sensor.is_on is None

    def test_is_on_none_data_vide(self) -> None:
        """is_on retourne None quand coordinator.data est vide."""
        sensor = self._build([])
        assert sensor.is_on is None

    def test_is_on_none_data_none(self) -> None:
        """is_on retourne None quand coordinator.data est None."""
        sensor = self._build([])
        sensor.coordinator.data = None
        assert sensor.is_on is None

    def test_device_class_est_motion(self) -> None:
        """device_class est BinarySensorDeviceClass.MOTION."""
        sensor = self._build([_cam_dict()])
        assert sensor._attr_device_class == BinarySensorDeviceClass.MOTION

    def test_unique_id(self) -> None:
        """unique_id suit le format fem_{cam}_motion."""
        sensor = self._build([_cam_dict()], cam_name="entree")
        assert sensor._attr_unique_id == "fem_entree_motion"

    def test_plusieurs_cameras_isole_bonne(self) -> None:
        """is_on retourne l'état de la bonne caméra quand plusieurs sont présentes."""
        data = [
            _cam_dict(name="jardin", motion=False),
            _cam_dict(name="garage", motion=True),
        ]
        sensor = self._build(data, cam_name="garage")
        assert sensor.is_on is True

    def test_motion_false_par_defaut_via_cam_dict(self) -> None:
        """Le champ motion vaut False par défaut dans CameraState.as_dict()."""
        sensor = self._build([_cam_dict()])
        assert sensor.is_on is False
