"""Tests for the per-camera anti-spam Throttler.

Covers:
- should_notify(): first notification (no history) → True
- should_notify(): after record(), before cooldown elapsed → False
- should_notify(): after record(), cooldown exactly elapsed → True
- should_notify(): cooldown not elapsed → False
- Camera independence: one camera's cooldown does not affect others
- now=0.0: treated as a valid timestamp (not as None/falsy)
- Injectable clock: behavior via self._clock when now is None
- record() without prior should_notify(): state updated correctly
- Custom cooldown: value other than 60s is respected
- Unknown camera: always allowed regardless of current time
"""

from __future__ import annotations

from unittest.mock import MagicMock


from custom_components.frigate_event_manager.domain.throttle import Throttler


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _throttler(cooldown: int = 60, clock_value: float = 1_700_000_000.0) -> Throttler:
    """Build a Throttler with a clock frozen at clock_value."""
    clock = MagicMock(return_value=clock_value)
    return Throttler(cooldown=cooldown, clock=clock)


# ---------------------------------------------------------------------------
# should_notify() — first notification (no history)
# ---------------------------------------------------------------------------

class TestShouldNotifyPremiere:
    def test_premiere_notification_autorisee(self) -> None:
        """When no notification has been recorded, should_notify() → True."""
        t = _throttler()
        assert t.should_notify("jardin", now=1_700_000_000.0) is True

    def test_premiere_notification_camera_inconnue(self) -> None:
        """An unknown camera is always allowed."""
        t = Throttler(cooldown=60)
        assert t.should_notify("entree") is True

    def test_plusieurs_cameras_inconnues_autorisees(self) -> None:
        """Multiple unknown cameras are all allowed independently."""
        t = _throttler()
        now = 1_700_000_000.0
        assert t.should_notify("cam_a", now=now) is True
        assert t.should_notify("cam_b", now=now) is True
        assert t.should_notify("cam_c", now=now) is True


# ---------------------------------------------------------------------------
# should_notify() — cooldown not elapsed
# ---------------------------------------------------------------------------

class TestShouldNotifyCooldownNonEcoule:
    def test_juste_apres_record_cooldown_non_ecoule(self) -> None:
        """Immediately after record(), should_notify() → False."""
        t = _throttler(cooldown=60)
        t.record("jardin", now=1_700_000_000.0)
        # Same instant → gap = 0 < 60
        assert t.should_notify("jardin", now=1_700_000_000.0) is False

    def test_un_instant_avant_cooldown(self) -> None:
        """1 second before end of cooldown → False."""
        t = _throttler(cooldown=60)
        t.record("jardin", now=1_700_000_000.0)
        # Gap = 59 < 60
        assert t.should_notify("jardin", now=1_700_000_059.0) is False

    def test_cooldown_personalise_non_ecoule(self) -> None:
        """Cooldown of 120s: at 119s gap → False."""
        t = _throttler(cooldown=120)
        t.record("garage", now=0.0)
        assert t.should_notify("garage", now=119.0) is False


# ---------------------------------------------------------------------------
# should_notify() — cooldown exactly elapsed or exceeded
# ---------------------------------------------------------------------------

class TestShouldNotifyCooldownEcoule:
    def test_cooldown_exactement_ecoule(self) -> None:
        """At exactly cooldown seconds gap, should_notify() → True."""
        t = _throttler(cooldown=60)
        t.record("jardin", now=1_700_000_000.0)
        # Gap = 60 == 60 → allowed (>= cooldown)
        assert t.should_notify("jardin", now=1_700_000_060.0) is True

    def test_cooldown_depasse(self) -> None:
        """Beyond the cooldown, should_notify() → True."""
        t = _throttler(cooldown=60)
        t.record("cour", now=1_700_000_000.0)
        # Gap = 120 > 60 → allowed
        assert t.should_notify("cour", now=1_700_000_120.0) is True

    def test_cooldown_personnalise_exactement_ecoule(self) -> None:
        """Cooldown of 300s: at exactly 300s gap → True."""
        t = _throttler(cooldown=300)
        t.record("parking", now=500.0)
        assert t.should_notify("parking", now=800.0) is True


# ---------------------------------------------------------------------------
# now=0.0 — falsy value but valid timestamp
# ---------------------------------------------------------------------------

class TestNowZero:
    def test_should_notify_now_zero_premiere_fois(self) -> None:
        """now=0.0 on an unknown camera → True (no falsy false-negative)."""
        t = _throttler(cooldown=60)
        assert t.should_notify("cam", now=0.0) is True

    def test_record_now_zero_puis_should_notify_avant_cooldown(self) -> None:
        """record(now=0.0) followed by should_notify(now=30.0) → False."""
        t = _throttler(cooldown=60)
        t.record("cam", now=0.0)
        # Gap = 30 < 60
        assert t.should_notify("cam", now=30.0) is False

    def test_record_now_zero_puis_should_notify_cooldown_ecoule(self) -> None:
        """record(now=0.0) followed by should_notify(now=60.0) → True."""
        t = _throttler(cooldown=60)
        t.record("cam", now=0.0)
        # Gap = 60 >= 60
        assert t.should_notify("cam", now=60.0) is True

    def test_should_notify_now_zero_apres_record_negatif(self) -> None:
        """now=0.0 in should_notify after record(now=0.0) same instant → False."""
        t = _throttler(cooldown=60)
        t.record("cam", now=0.0)
        # Gap = 0 < 60
        assert t.should_notify("cam", now=0.0) is False


# ---------------------------------------------------------------------------
# Injectable clock — should_notify and record without now parameter
# ---------------------------------------------------------------------------

class TestClockInjectable:
    def test_should_notify_utilise_clock_quand_now_est_none(self) -> None:
        """Without now parameter, should_notify() reads self._clock()."""
        clock = MagicMock(return_value=1_700_000_000.0)
        t = Throttler(cooldown=60, clock=clock)

        # First notification → clock called, returns True
        result = t.should_notify("jardin")

        assert result is True
        clock.assert_called_once()

    def test_record_utilise_clock_quand_now_est_none(self) -> None:
        """Without now parameter, record() reads self._clock() to store the timestamp."""
        clock = MagicMock(return_value=1_700_000_000.0)
        t = Throttler(cooldown=60, clock=clock)

        t.record("jardin")

        # Clock was called to get the timestamp
        clock.assert_called_once()
        # Stored timestamp must match the clock value
        assert t._last_notified["jardin"] == 1_700_000_000.0

    def test_clock_avance_entre_record_et_should_notify(self) -> None:
        """Clock is read on each call: advancing the clock allows unblocking."""
        timestamps = iter([
            1_700_000_000.0,  # record()
            1_700_000_060.0,  # should_notify() → gap = 60 >= 60
        ])
        clock = MagicMock(side_effect=timestamps)
        t = Throttler(cooldown=60, clock=clock)

        t.record("cam")
        result = t.should_notify("cam")

        assert result is True

    def test_clock_figee_bloque_la_notification(self) -> None:
        """With a frozen clock, the second notification is always blocked."""
        clock = MagicMock(return_value=1_700_000_000.0)
        t = Throttler(cooldown=60, clock=clock)

        t.record("cam")
        result = t.should_notify("cam")

        assert result is False


# ---------------------------------------------------------------------------
# Camera independence
# ---------------------------------------------------------------------------

class TestIndependanceCameras:
    def test_cooldown_camera_a_naffecte_pas_camera_b(self) -> None:
        """cam_a's cooldown does not block cam_b."""
        t = _throttler(cooldown=60)
        now = 1_700_000_000.0
        t.record("cam_a", now=now)

        # cam_b was never recorded → allowed
        assert t.should_notify("cam_b", now=now) is True

    def test_cooldown_ecoule_pour_a_pas_pour_b(self) -> None:
        """cam_a can be notified at T+60, cam_b was recorded at T+30 → blocked."""
        t = _throttler(cooldown=60)
        t.record("cam_a", now=1_700_000_000.0)
        t.record("cam_b", now=1_700_000_030.0)

        now_check = 1_700_000_060.0
        # cam_a: gap = 60 >= 60 → True
        assert t.should_notify("cam_a", now=now_check) is True
        # cam_b: gap = 30 < 60 → False
        assert t.should_notify("cam_b", now=now_check) is False

    def test_trois_cameras_independantes(self) -> None:
        """Three cameras with different histories managed independently."""
        t = _throttler(cooldown=60)
        t.record("cam_x", now=1_700_000_000.0)
        t.record("cam_y", now=1_700_000_010.0)
        # cam_z never recorded

        now = 1_700_000_065.0
        # cam_x: gap = 65 >= 60 → True
        assert t.should_notify("cam_x", now=now) is True
        # cam_y: gap = 55 < 60 → False
        assert t.should_notify("cam_y", now=now) is False
        # cam_z: never recorded → True
        assert t.should_notify("cam_z", now=now) is True


# ---------------------------------------------------------------------------
# record() without prior should_notify()
# ---------------------------------------------------------------------------

class TestRecordSansShouldNotify:
    def test_record_met_a_jour_le_dictionnaire(self) -> None:
        """record() alone stores the timestamp without prior call to should_notify()."""
        t = _throttler(cooldown=60)
        t.record("cam", now=1_700_000_000.0)

        assert t._last_notified["cam"] == 1_700_000_000.0

    def test_record_ecrase_le_timestamp_precedent(self) -> None:
        """A second record() overwrites the first timestamp."""
        t = _throttler(cooldown=60)
        t.record("cam", now=1_700_000_000.0)
        t.record("cam", now=1_700_000_500.0)

        assert t._last_notified["cam"] == 1_700_000_500.0

    def test_record_puis_should_notify_blocked(self) -> None:
        """After record() without should_notify(), the camera is still blocked."""
        t = _throttler(cooldown=60)
        t.record("cam", now=1_700_000_000.0)

        # No call to should_notify() before: state must still block
        assert t.should_notify("cam", now=1_700_000_010.0) is False

    def test_record_multiple_cameras_sans_should_notify(self) -> None:
        """record() on multiple cameras without should_notify() updates each one."""
        t = _throttler(cooldown=60)
        t.record("cam_a", now=100.0)
        t.record("cam_b", now=200.0)
        t.record("cam_c", now=300.0)

        assert t._last_notified["cam_a"] == 100.0
        assert t._last_notified["cam_b"] == 200.0
        assert t._last_notified["cam_c"] == 300.0


# ---------------------------------------------------------------------------
# Configurable cooldown
# ---------------------------------------------------------------------------

class TestCooldownConfigurable:
    def test_cooldown_zero_toujours_autorise(self) -> None:
        """Cooldown=0: each notification is immediately allowed."""
        t = Throttler(cooldown=0)
        now = 1_700_000_000.0
        t.record("cam", now=now)
        # Gap = 0 >= 0
        assert t.should_notify("cam", now=now) is True

    def test_cooldown_tres_long(self) -> None:
        """Cooldown of 86400s (24h): 1h later → still blocked."""
        t = Throttler(cooldown=86400)
        t.record("cam", now=0.0)
        # 1h later → gap = 3600 < 86400
        assert t.should_notify("cam", now=3600.0) is False

    def test_cooldown_tres_long_ecoule(self) -> None:
        """Cooldown of 86400s: exactly 86400s later → allowed."""
        t = Throttler(cooldown=86400)
        t.record("cam", now=0.0)
        assert t.should_notify("cam", now=86400.0) is True

    def test_cooldown_defaut_est_60s(self) -> None:
        """Default cooldown is 60 seconds."""
        t = Throttler()
        assert t._cooldown == 60
