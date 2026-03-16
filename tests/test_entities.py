"""Tests des entités HA — switch, binary_sensor."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from homeassistant.components.binary_sensor import BinarySensorDeviceClass

from custom_components.frigate_event_manager.binary_sensor import FrigateMotionSensor
from custom_components.frigate_event_manager.coordinator import CameraState
from custom_components.frigate_event_manager.switch import FrigateNotificationSwitch

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_NOOP = "homeassistant.helpers.update_coordinator.CoordinatorEntity.__init__"
_SUBENTRY_ID = "subentry_test_id"


def _make_coordinator(cam_name: str = "jardin", data: dict | None = None) -> MagicMock:
    coordinator = MagicMock()
    coordinator.camera = cam_name
    coordinator.camera_state = CameraState(name=cam_name)
    coordinator.data = data if data is not None else CameraState(name=cam_name).as_dict()
    return coordinator


def _cam_dict(
    name: str = "jardin",
    last_severity: str | None = "alert",
    last_objects: list[str] | None = None,
    motion: bool = False,
    enabled: bool = True,
) -> dict:
    """Retourne un dict conforme à CameraState.as_dict()."""
    return CameraState(
        name=name,
        last_severity=last_severity,
        last_objects=last_objects if last_objects is not None else ["personne"],
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
            switch = FrigateNotificationSwitch(coordinator, _SUBENTRY_ID)
        switch.coordinator = coordinator
        return switch

    def test_is_on_retourne_enabled_true(self) -> None:
        switch = self._build(data=_cam_dict(enabled=True))
        assert switch.is_on is True

    def test_is_on_retourne_enabled_false(self) -> None:
        switch = self._build(data=_cam_dict(enabled=False))
        assert switch.is_on is False

    def test_is_on_true_par_defaut_data_none(self) -> None:
        switch = self._build()
        switch.coordinator.data = None
        switch.coordinator.camera_state.enabled = True
        assert switch.is_on is True

    def test_is_on_false_via_camera_state_quand_data_none(self) -> None:
        switch = self._build()
        switch.coordinator.data = None
        switch.coordinator.camera_state.enabled = False
        assert switch.is_on is False

    async def test_async_turn_on(self) -> None:
        switch = self._build(data=_cam_dict(enabled=False))
        await switch.async_turn_on()
        switch.coordinator.set_camera_enabled.assert_called_once_with(True)

    async def test_async_turn_off(self) -> None:
        switch = self._build(data=_cam_dict(enabled=True))
        await switch.async_turn_off()
        switch.coordinator.set_camera_enabled.assert_called_once_with(False)

    def test_unique_id_format(self) -> None:
        switch = self._build(cam_name="entree")
        assert switch._attr_unique_id == "fem_entree_switch"

    def test_nom_entite_est_notifications(self) -> None:
        switch = self._build(cam_name="terrasse")
        assert switch._attr_name == "Notifications"

    def test_device_info_identifiers_contient_subentry_id(self) -> None:
        switch = self._build()
        ids = {i[1] for i in switch._attr_device_info["identifiers"]}
        assert _SUBENTRY_ID in ids

    async def test_async_turn_on_avec_kwargs(self) -> None:
        switch = self._build()
        await switch.async_turn_on(transition=1)
        switch.coordinator.set_camera_enabled.assert_called_once_with(True)

    async def test_async_turn_off_avec_kwargs(self) -> None:
        switch = self._build()
        await switch.async_turn_off(transition=1)
        switch.coordinator.set_camera_enabled.assert_called_once_with(False)


# ---------------------------------------------------------------------------
# FrigateMotionSensor
# ---------------------------------------------------------------------------


class TestFrigateMotionSensor:
    """Tests de FrigateMotionSensor."""

    def _build(self, cam_name: str = "jardin", data: dict | None = None) -> FrigateMotionSensor:
        coordinator = _make_coordinator(cam_name, data)
        with patch(_NOOP, return_value=None):
            sensor = FrigateMotionSensor(coordinator, _SUBENTRY_ID)
        sensor.coordinator = coordinator
        return sensor

    def test_is_on_true_quand_motion_true(self) -> None:
        sensor = self._build(data=_cam_dict(motion=True))
        assert sensor.is_on is True

    def test_is_on_false_quand_motion_false(self) -> None:
        sensor = self._build(data=_cam_dict(motion=False))
        assert sensor.is_on is False

    def test_is_on_via_camera_state_quand_data_none(self) -> None:
        sensor = self._build()
        sensor.coordinator.data = None
        sensor.coordinator.camera_state.motion = False
        assert sensor.is_on is False

    def test_is_on_true_via_camera_state(self) -> None:
        sensor = self._build()
        sensor.coordinator.data = None
        sensor.coordinator.camera_state.motion = True
        assert sensor.is_on is True

    def test_device_class_est_motion(self) -> None:
        sensor = self._build(data=_cam_dict())
        assert sensor._attr_device_class == BinarySensorDeviceClass.MOTION

    def test_unique_id_format(self) -> None:
        sensor = self._build(cam_name="entree")
        assert sensor._attr_unique_id == "fem_entree_motion"

    def test_nom_entite_est_mouvement(self) -> None:
        sensor = self._build(cam_name="piscine")
        assert sensor._attr_name == "Mouvement"

    def test_device_info_identifiers_contient_subentry_id(self) -> None:
        sensor = self._build()
        ids = {i[1] for i in sensor._attr_device_info["identifiers"]}
        assert _SUBENTRY_ID in ids

    def test_motion_false_par_defaut(self) -> None:
        sensor = self._build(data=_cam_dict())
        assert sensor.is_on is False
