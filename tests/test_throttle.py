"""Tests du Throttler anti-spam par caméra.

Couvre :
- should_notify() : première notification (aucun historique) → True
- should_notify() : après record(), avant écoulement du cooldown → False
- should_notify() : après record(), cooldown exactement écoulé → True
- should_notify() : cooldown non écoulé → False
- Indépendance des caméras : le cooldown d'une caméra n'affecte pas les autres
- now=0.0 : traité comme un timestamp valide (pas comme None/falsy)
- Clock injectable : comportement via self._clock quand now est None
- record() sans should_notify() préalable : état mis à jour correctement
- Cooldown personnalisé : valeur autre que 60s respectée
- Caméra inconnue : toujours autorisée quelle que soit l'heure courante
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from custom_components.frigate_event_manager.throttle import Throttler


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _throttler(cooldown: int = 60, clock_value: float = 1_700_000_000.0) -> Throttler:
    """Construit un Throttler avec une clock figée sur clock_value."""
    clock = MagicMock(return_value=clock_value)
    return Throttler(cooldown=cooldown, clock=clock)


# ---------------------------------------------------------------------------
# should_notify() — première notification (aucun historique)
# ---------------------------------------------------------------------------

class TestShouldNotifyPremiere:
    def test_premiere_notification_autorisee(self) -> None:
        """Quand aucune notification n'a été enregistrée, should_notify() → True."""
        t = _throttler()
        assert t.should_notify("jardin", now=1_700_000_000.0) is True

    def test_premiere_notification_camera_inconnue(self) -> None:
        """Une caméra jamais vue est toujours autorisée."""
        t = Throttler(cooldown=60)
        assert t.should_notify("entree") is True

    def test_plusieurs_cameras_inconnues_autorisees(self) -> None:
        """Plusieurs caméras inconnues sont toutes autorisées indépendamment."""
        t = _throttler()
        now = 1_700_000_000.0
        assert t.should_notify("cam_a", now=now) is True
        assert t.should_notify("cam_b", now=now) is True
        assert t.should_notify("cam_c", now=now) is True


# ---------------------------------------------------------------------------
# should_notify() — cooldown non écoulé
# ---------------------------------------------------------------------------

class TestShouldNotifyCooldownNonEcoule:
    def test_juste_apres_record_cooldown_non_ecoule(self) -> None:
        """Immédiatement après record(), should_notify() → False."""
        t = _throttler(cooldown=60)
        t.record("jardin", now=1_700_000_000.0)
        # Même instant → écart = 0 < 60
        assert t.should_notify("jardin", now=1_700_000_000.0) is False

    def test_un_instant_avant_cooldown(self) -> None:
        """1 seconde avant la fin du cooldown → False."""
        t = _throttler(cooldown=60)
        t.record("jardin", now=1_700_000_000.0)
        # Écart = 59 < 60
        assert t.should_notify("jardin", now=1_700_000_059.0) is False

    def test_cooldown_personalise_non_ecoule(self) -> None:
        """Cooldown de 120s : à 119s d'écart → False."""
        t = _throttler(cooldown=120)
        t.record("garage", now=0.0)
        assert t.should_notify("garage", now=119.0) is False


# ---------------------------------------------------------------------------
# should_notify() — cooldown exactement écoulé ou dépassé
# ---------------------------------------------------------------------------

class TestShouldNotifyCooldownEcoule:
    def test_cooldown_exactement_ecoule(self) -> None:
        """À exactement cooldown secondes d'écart, should_notify() → True."""
        t = _throttler(cooldown=60)
        t.record("jardin", now=1_700_000_000.0)
        # Écart = 60 == 60 → autorisé (>= cooldown)
        assert t.should_notify("jardin", now=1_700_000_060.0) is True

    def test_cooldown_depasse(self) -> None:
        """Au-delà du cooldown, should_notify() → True."""
        t = _throttler(cooldown=60)
        t.record("cour", now=1_700_000_000.0)
        # Écart = 120 > 60 → autorisé
        assert t.should_notify("cour", now=1_700_000_120.0) is True

    def test_cooldown_personnalise_exactement_ecoule(self) -> None:
        """Cooldown de 300s : à exactement 300s d'écart → True."""
        t = _throttler(cooldown=300)
        t.record("parking", now=500.0)
        assert t.should_notify("parking", now=800.0) is True


# ---------------------------------------------------------------------------
# now=0.0 — valeur falsy mais timestamp valide
# ---------------------------------------------------------------------------

class TestNowZero:
    def test_should_notify_now_zero_premiere_fois(self) -> None:
        """now=0.0 sur une caméra inconnue → True (pas de faux-négatif falsy)."""
        t = _throttler(cooldown=60)
        assert t.should_notify("cam", now=0.0) is True

    def test_record_now_zero_puis_should_notify_avant_cooldown(self) -> None:
        """record(now=0.0) suivi de should_notify(now=30.0) → False."""
        t = _throttler(cooldown=60)
        t.record("cam", now=0.0)
        # Écart = 30 < 60
        assert t.should_notify("cam", now=30.0) is False

    def test_record_now_zero_puis_should_notify_cooldown_ecoule(self) -> None:
        """record(now=0.0) suivi de should_notify(now=60.0) → True."""
        t = _throttler(cooldown=60)
        t.record("cam", now=0.0)
        # Écart = 60 >= 60
        assert t.should_notify("cam", now=60.0) is True

    def test_should_notify_now_zero_apres_record_negatif(self) -> None:
        """now=0.0 en should_notify après record(now=0.0) même instant → False."""
        t = _throttler(cooldown=60)
        t.record("cam", now=0.0)
        # Écart = 0 < 60
        assert t.should_notify("cam", now=0.0) is False


# ---------------------------------------------------------------------------
# Clock injectable — should_notify et record sans paramètre now
# ---------------------------------------------------------------------------

class TestClockInjectable:
    def test_should_notify_utilise_clock_quand_now_est_none(self) -> None:
        """Sans paramètre now, should_notify() lit self._clock()."""
        clock = MagicMock(return_value=1_700_000_000.0)
        t = Throttler(cooldown=60, clock=clock)

        # Première notification → clock appelée, retourne True
        result = t.should_notify("jardin")

        assert result is True
        clock.assert_called_once()

    def test_record_utilise_clock_quand_now_est_none(self) -> None:
        """Sans paramètre now, record() lit self._clock() pour stocker le timestamp."""
        clock = MagicMock(return_value=1_700_000_000.0)
        t = Throttler(cooldown=60, clock=clock)

        t.record("jardin")

        # La clock a été appelée pour obtenir le timestamp
        clock.assert_called_once()
        # Le timestamp stocké doit correspondre à la valeur de la clock
        assert t._last_notified["jardin"] == 1_700_000_000.0

    def test_clock_avance_entre_record_et_should_notify(self) -> None:
        """La clock est lue à chaque appel : avancer la clock permet le déblocage."""
        timestamps = iter([
            1_700_000_000.0,  # record()
            1_700_000_060.0,  # should_notify() → écart = 60 >= 60
        ])
        clock = MagicMock(side_effect=timestamps)
        t = Throttler(cooldown=60, clock=clock)

        t.record("cam")
        result = t.should_notify("cam")

        assert result is True

    def test_clock_figee_bloque_la_notification(self) -> None:
        """Avec une clock figée, la deuxième notification est toujours bloquée."""
        clock = MagicMock(return_value=1_700_000_000.0)
        t = Throttler(cooldown=60, clock=clock)

        t.record("cam")
        result = t.should_notify("cam")

        assert result is False


# ---------------------------------------------------------------------------
# Indépendance des caméras
# ---------------------------------------------------------------------------

class TestIndependanceCameras:
    def test_cooldown_camera_a_naffecte_pas_camera_b(self) -> None:
        """Le cooldown de cam_a ne bloque pas cam_b."""
        t = _throttler(cooldown=60)
        now = 1_700_000_000.0
        t.record("cam_a", now=now)

        # cam_b n'a jamais été enregistrée → autorisée
        assert t.should_notify("cam_b", now=now) is True

    def test_cooldown_ecoule_pour_a_pas_pour_b(self) -> None:
        """cam_a peut être notifiée à T+60, cam_b a été enregistrée à T+30 → bloquée."""
        t = _throttler(cooldown=60)
        t.record("cam_a", now=1_700_000_000.0)
        t.record("cam_b", now=1_700_000_030.0)

        now_check = 1_700_000_060.0
        # cam_a : écart = 60 >= 60 → True
        assert t.should_notify("cam_a", now=now_check) is True
        # cam_b : écart = 30 < 60 → False
        assert t.should_notify("cam_b", now=now_check) is False

    def test_trois_cameras_independantes(self) -> None:
        """Trois caméras avec historiques différents gérées indépendamment."""
        t = _throttler(cooldown=60)
        t.record("cam_x", now=1_700_000_000.0)
        t.record("cam_y", now=1_700_000_010.0)
        # cam_z jamais enregistrée

        now = 1_700_000_065.0
        # cam_x : écart = 65 >= 60 → True
        assert t.should_notify("cam_x", now=now) is True
        # cam_y : écart = 55 < 60 → False
        assert t.should_notify("cam_y", now=now) is False
        # cam_z : jamais enregistrée → True
        assert t.should_notify("cam_z", now=now) is True


# ---------------------------------------------------------------------------
# record() sans should_notify() préalable
# ---------------------------------------------------------------------------

class TestRecordSansShouldNotify:
    def test_record_met_a_jour_le_dictionnaire(self) -> None:
        """record() seul stocke le timestamp sans appel préalable à should_notify()."""
        t = _throttler(cooldown=60)
        t.record("cam", now=1_700_000_000.0)

        assert t._last_notified["cam"] == 1_700_000_000.0

    def test_record_ecrase_le_timestamp_precedent(self) -> None:
        """Un deuxième record() écrase le premier timestamp."""
        t = _throttler(cooldown=60)
        t.record("cam", now=1_700_000_000.0)
        t.record("cam", now=1_700_000_500.0)

        assert t._last_notified["cam"] == 1_700_000_500.0

    def test_record_puis_should_notify_blocked(self) -> None:
        """Après record() sans should_notify(), la caméra est bien bloquée."""
        t = _throttler(cooldown=60)
        t.record("cam", now=1_700_000_000.0)

        # Aucun appel à should_notify() avant : l'état doit quand même bloquer
        assert t.should_notify("cam", now=1_700_000_010.0) is False

    def test_record_multiple_cameras_sans_should_notify(self) -> None:
        """record() sur plusieurs caméras sans should_notify() met à jour chacune."""
        t = _throttler(cooldown=60)
        t.record("cam_a", now=100.0)
        t.record("cam_b", now=200.0)
        t.record("cam_c", now=300.0)

        assert t._last_notified["cam_a"] == 100.0
        assert t._last_notified["cam_b"] == 200.0
        assert t._last_notified["cam_c"] == 300.0


# ---------------------------------------------------------------------------
# Cooldown configurable
# ---------------------------------------------------------------------------

class TestCooldownConfigurable:
    def test_cooldown_zero_toujours_autorise(self) -> None:
        """Cooldown=0 : chaque notification est immédiatement autorisée."""
        t = Throttler(cooldown=0)
        now = 1_700_000_000.0
        t.record("cam", now=now)
        # Écart = 0 >= 0
        assert t.should_notify("cam", now=now) is True

    def test_cooldown_tres_long(self) -> None:
        """Cooldown de 86400s (24h) : 1h après → toujours bloqué."""
        t = Throttler(cooldown=86400)
        t.record("cam", now=0.0)
        # 1h après → écart = 3600 < 86400
        assert t.should_notify("cam", now=3600.0) is False

    def test_cooldown_tres_long_ecoule(self) -> None:
        """Cooldown de 86400s : exactement 86400s après → autorisé."""
        t = Throttler(cooldown=86400)
        t.record("cam", now=0.0)
        assert t.should_notify("cam", now=86400.0) is True

    def test_cooldown_defaut_est_60s(self) -> None:
        """Le cooldown par défaut est 60 secondes."""
        t = Throttler()
        assert t._cooldown == 60
