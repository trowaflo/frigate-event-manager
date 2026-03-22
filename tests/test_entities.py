"""Tests des entités HA — switch, binary_sensor, sensor."""

from __future__ import annotations

import time
from datetime import timezone
from unittest.mock import MagicMock, patch

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.sensor import SensorDeviceClass

from custom_components.frigate_event_manager.binary_sensor import (
    FrigateMotionSensor,
    SilentStateSensor,
)
from custom_components.frigate_event_manager.domain.model import CameraState
from custom_components.frigate_event_manager.sensor import SilentUntilSensor
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
        assert switch._attr_translation_key == "notifications"

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
        assert sensor._attr_translation_key == "motion"

    def test_device_info_identifiers_contient_subentry_id(self) -> None:
        sensor = self._build()
        ids = {i[1] for i in sensor._attr_device_info["identifiers"]}
        assert _SUBENTRY_ID in ids

    def test_motion_false_par_defaut(self) -> None:
        sensor = self._build(data=_cam_dict())
        assert sensor.is_on is False


# ---------------------------------------------------------------------------
# SilentStateSensor
# ---------------------------------------------------------------------------


class TestSilentStateSensor:
    """Tests de SilentStateSensor (binary_sensor silence actif)."""

    def _build(self, cam_name: str = "jardin", silent_until: float = 0.0) -> SilentStateSensor:
        coordinator = _make_coordinator(cam_name)
        coordinator._silent_until = silent_until
        with patch(_NOOP, return_value=None):
            sensor = SilentStateSensor(coordinator, _SUBENTRY_ID)
        sensor.coordinator = coordinator
        return sensor

    def test_is_on_true_quand_silence_actif(self) -> None:
        """is_on retourne True quand _silent_until est dans le futur."""
        sensor = self._build(silent_until=time.time() + 3600.0)
        assert sensor.is_on is True

    def test_is_on_false_quand_silence_inactif(self) -> None:
        """is_on retourne False quand _silent_until vaut 0.0."""
        sensor = self._build(silent_until=0.0)
        assert sensor.is_on is False

    def test_is_on_false_quand_silence_expire(self) -> None:
        """is_on retourne False quand _silent_until est dans le passé."""
        sensor = self._build(silent_until=time.time() - 1.0)
        assert sensor.is_on is False

    def test_device_class_est_running(self) -> None:
        sensor = self._build()
        assert sensor._attr_device_class == BinarySensorDeviceClass.RUNNING

    def test_unique_id_format(self) -> None:
        sensor = self._build(cam_name="entree")
        assert sensor._attr_unique_id == "fem_entree_silent_state"

    def test_translation_key(self) -> None:
        sensor = self._build()
        assert sensor._attr_translation_key == "silent_state"

    def test_icon(self) -> None:
        sensor = self._build()
        assert sensor._attr_icon == "mdi:bell-sleep"

    def test_has_entity_name(self) -> None:
        sensor = self._build()
        assert sensor._attr_has_entity_name is True

    def test_device_info_identifiers_contient_subentry_id(self) -> None:
        sensor = self._build()
        ids = {i[1] for i in sensor._attr_device_info["identifiers"]}
        assert _SUBENTRY_ID in ids

    def test_device_info_nom_camera(self) -> None:
        sensor = self._build("terrasse")
        assert sensor._attr_device_info["name"] == "Caméra terrasse"

    def test_is_on_reflecte_mise_a_jour_silent_until(self) -> None:
        """is_on reflète le changement de _silent_until après async_set_updated_data."""
        sensor = self._build(silent_until=0.0)
        assert sensor.is_on is False

        # Simuler la mise à jour par le coordinator (comme async_set_updated_data ferait)
        sensor.coordinator._silent_until = time.time() + 3600.0
        assert sensor.is_on is True


# ---------------------------------------------------------------------------
# SilentUntilSensor
# ---------------------------------------------------------------------------


class TestSilentUntilSensor:
    """Tests de SilentUntilSensor (sensor timestamp reprise)."""

    def _build(self, cam_name: str = "jardin", silent_until: float = 0.0) -> SilentUntilSensor:
        coordinator = _make_coordinator(cam_name)
        coordinator._silent_until = silent_until
        with patch(_NOOP, return_value=None):
            sensor = SilentUntilSensor(coordinator, _SUBENTRY_ID)
        sensor.coordinator = coordinator
        return sensor

    def test_native_value_none_quand_silence_inactif(self) -> None:
        """native_value vaut None quand _silent_until est 0.0."""
        sensor = self._build(silent_until=0.0)
        assert sensor.native_value is None

    def test_native_value_none_quand_silence_expire(self) -> None:
        """native_value vaut None quand _silent_until est dans le passé."""
        sensor = self._build(silent_until=time.time() - 1.0)
        assert sensor.native_value is None

    def test_native_value_datetime_quand_silence_actif(self) -> None:
        """native_value retourne un datetime UTC quand _silent_until est dans le futur."""
        future = time.time() + 3600.0
        sensor = self._build(silent_until=future)
        result = sensor.native_value
        assert result is not None
        assert result.tzinfo == timezone.utc

    def test_native_value_timestamp_correct(self) -> None:
        """Le timestamp du native_value correspond à _silent_until."""
        future = time.time() + 3600.0
        sensor = self._build(silent_until=future)
        result = sensor.native_value
        assert result is not None
        assert abs(result.timestamp() - future) < 0.01

    def test_device_class_est_timestamp(self) -> None:
        sensor = self._build()
        assert sensor._attr_device_class == SensorDeviceClass.TIMESTAMP

    def test_unique_id_format(self) -> None:
        sensor = self._build(cam_name="entree")
        assert sensor._attr_unique_id == "fem_entree_silent_until"

    def test_translation_key(self) -> None:
        sensor = self._build()
        assert sensor._attr_translation_key == "silent_until"

    def test_icon(self) -> None:
        sensor = self._build()
        assert sensor._attr_icon == "mdi:timer-outline"

    def test_has_entity_name(self) -> None:
        sensor = self._build()
        assert sensor._attr_has_entity_name is True

    def test_device_info_identifiers_contient_subentry_id(self) -> None:
        sensor = self._build()
        ids = {i[1] for i in sensor._attr_device_info["identifiers"]}
        assert _SUBENTRY_ID in ids

    def test_device_info_nom_camera(self) -> None:
        sensor = self._build("piscine")
        assert sensor._attr_device_info["name"] == "Caméra piscine"
