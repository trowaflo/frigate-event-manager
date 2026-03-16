"""Tests des entités HA — switch, binary_sensor.

Couvre :
- FrigateNotificationSwitch.is_on + async_turn_on/off
- FrigateMotionSensor.is_on + device_class

Stratégie : mock du coordinator (MagicMock) dont :
  - coordinator.camera retourne le nom de la caméra
  - coordinator.data retourne un dict conforme à CameraState.as_dict()
  - coordinator.camera_state retourne un CameraState réel

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


def _make_coordinator(cam_name: str = "jardin", data: dict | None = None) -> MagicMock:
    """Construit un coordinator mocké pour une caméra unique.

    coordinator.data est un dict conforme à CameraState.as_dict().
    coordinator.camera retourne le nom de la caméra.
    coordinator.camera_state retourne un CameraState réel.
    """
    coordinator = MagicMock()
    coordinator.camera = cam_name
    coordinator.camera_state = CameraState(name=cam_name)
    coordinator.data = data if data is not None else CameraState(name=cam_name).as_dict()
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

    def _build(self, cam_name: str = "jardin", data: dict | None = None) -> FrigateNotificationSwitch:
        coordinator = _make_coordinator(cam_name, data)
        with patch(_NOOP, return_value=None):
            switch = FrigateNotificationSwitch(coordinator)
        switch.coordinator = coordinator
        return switch

    def test_is_on_retourne_enabled_true(self) -> None:
        """is_on retourne True quand enabled=True."""
        switch = self._build(data=_cam_dict(enabled=True))
        assert switch.is_on is True

    def test_is_on_retourne_enabled_false(self) -> None:
        """is_on retourne False quand enabled=False."""
        switch = self._build(data=_cam_dict(enabled=False))
        assert switch.is_on is False

    def test_is_on_true_par_defaut_data_none(self) -> None:
        """is_on se replie sur camera_state.enabled quand coordinator.data est None."""
        switch = self._build()
        switch.coordinator.data = None
        switch.coordinator.camera_state.enabled = True
        assert switch.is_on is True

    def test_is_on_false_via_camera_state_quand_data_none(self) -> None:
        """is_on retourne False via camera_state quand coordinator.data est None."""
        switch = self._build()
        switch.coordinator.data = None
        switch.coordinator.camera_state.enabled = False
        assert switch.is_on is False

    async def test_async_turn_on_appelle_set_camera_enabled_true(self) -> None:
        """async_turn_on appelle coordinator.set_camera_enabled avec True."""
        switch = self._build(data=_cam_dict(enabled=False))
        await switch.async_turn_on()
        switch.coordinator.set_camera_enabled.assert_called_once_with(True)

    async def test_async_turn_off_appelle_set_camera_enabled_false(self) -> None:
        """async_turn_off appelle coordinator.set_camera_enabled avec False."""
        switch = self._build(data=_cam_dict(enabled=True))
        await switch.async_turn_off()
        switch.coordinator.set_camera_enabled.assert_called_once_with(False)

    def test_unique_id_format_switch(self) -> None:
        """unique_id suit le format fem_{cam}_switch."""
        switch = self._build(cam_name="entree")
        assert switch._attr_unique_id == "fem_entree_switch"

    def test_unique_id_camera_jardin(self) -> None:
        """unique_id correct pour caméra jardin."""
        switch = self._build(cam_name="jardin")
        assert switch._attr_unique_id == "fem_jardin_switch"

    async def test_async_turn_on_avec_kwargs_ne_plante_pas(self) -> None:
        """async_turn_on accepte des kwargs arbitraires sans erreur."""
        switch = self._build(data=_cam_dict())
        await switch.async_turn_on(transition=1)
        switch.coordinator.set_camera_enabled.assert_called_once_with(True)

    async def test_async_turn_off_avec_kwargs_ne_plante_pas(self) -> None:
        """async_turn_off accepte des kwargs arbitraires sans erreur."""
        switch = self._build(data=_cam_dict())
        await switch.async_turn_off(transition=1)
        switch.coordinator.set_camera_enabled.assert_called_once_with(False)

    def test_is_on_depuis_data_dict(self) -> None:
        """is_on lit enabled depuis coordinator.data (dict)."""
        switch = self._build(data=_cam_dict(name="garage", enabled=True))
        assert switch.is_on is True

    def test_nom_entite_contient_nom_camera(self) -> None:
        """_attr_name contient le nom de la caméra."""
        switch = self._build(cam_name="terrasse")
        assert "terrasse" in switch._attr_name


# ---------------------------------------------------------------------------
# FrigateMotionSensor
# ---------------------------------------------------------------------------


class TestFrigateMotionSensor:
    """Tests de FrigateMotionSensor."""

    def _build(self, cam_name: str = "jardin", data: dict | None = None) -> FrigateMotionSensor:
        coordinator = _make_coordinator(cam_name, data)
        with patch(_NOOP, return_value=None):
            sensor = FrigateMotionSensor(coordinator)
        sensor.coordinator = coordinator
        return sensor

    def test_is_on_true_quand_motion_true(self) -> None:
        """is_on retourne True quand motion=True (événement type=new actif)."""
        sensor = self._build(data=_cam_dict(motion=True))
        assert sensor.is_on is True

    def test_is_on_false_quand_motion_false(self) -> None:
        """is_on retourne False quand motion=False (aucun mouvement actif)."""
        sensor = self._build(data=_cam_dict(motion=False))
        assert sensor.is_on is False

    def test_is_on_via_camera_state_quand_data_none(self) -> None:
        """is_on se replie sur camera_state.motion quand coordinator.data est None."""
        sensor = self._build()
        sensor.coordinator.data = None
        sensor.coordinator.camera_state.motion = False
        assert sensor.is_on is False

    def test_is_on_true_via_camera_state(self) -> None:
        """is_on retourne True via camera_state quand data est None."""
        sensor = self._build()
        sensor.coordinator.data = None
        sensor.coordinator.camera_state.motion = True
        assert sensor.is_on is True

    def test_device_class_est_motion(self) -> None:
        """device_class est BinarySensorDeviceClass.MOTION."""
        sensor = self._build(data=_cam_dict())
        assert sensor._attr_device_class == BinarySensorDeviceClass.MOTION

    def test_unique_id_format_motion(self) -> None:
        """unique_id suit le format fem_{cam}_motion."""
        sensor = self._build(cam_name="entree")
        assert sensor._attr_unique_id == "fem_entree_motion"

    def test_unique_id_camera_jardin(self) -> None:
        """unique_id correct pour caméra jardin."""
        sensor = self._build(cam_name="jardin")
        assert sensor._attr_unique_id == "fem_jardin_motion"

    def test_motion_false_par_defaut_via_cam_dict(self) -> None:
        """Le champ motion vaut False par défaut dans CameraState.as_dict()."""
        sensor = self._build(data=_cam_dict())
        assert sensor.is_on is False

    def test_nom_entite_contient_nom_camera(self) -> None:
        """_attr_name contient le nom de la caméra."""
        sensor = self._build(cam_name="piscine")
        assert "piscine" in sensor._attr_name
