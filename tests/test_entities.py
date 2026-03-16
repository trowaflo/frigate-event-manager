"""Tests des entités HA — switch, binary_sensor.

Couvre :
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
