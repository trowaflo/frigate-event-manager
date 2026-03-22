"""Tests for Frigate event filters — ZoneFilter, LabelFilter, TimeFilter, FilterChain.

Translated from Go test cases (zone_multi, order_enforced, clock mock) to Python.
Tested convention: empty list = accept all (no filtering).
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock


from custom_components.frigate_event_manager.domain.filter import (
    Filter,
    FilterChain,
    LabelFilter,
    SeverityFilter,
    TimeFilter,
    ZoneFilter,
    _est_sous_sequence,
)
from custom_components.frigate_event_manager.domain.model import FrigateEvent


# ---------------------------------------------------------------------------
# Helpers — minimal FrigateEvent constructors
# ---------------------------------------------------------------------------


def make_event(
    *,
    camera: str = "jardin",
    type: str = "new",
    severity: str = "alert",
    objects: list[str] | None = None,
    zones: list[str] | None = None,
) -> FrigateEvent:
    """Build a minimal FrigateEvent for filter tests."""
    return FrigateEvent(
        type=type,
        camera=camera,
        severity=severity,
        objects=objects if objects is not None else [],
        zones=zones if zones is not None else [],
    )


def make_clock(hour: int) -> MagicMock:
    """Return a mocked clock with hour fixed at `hour`."""
    dt = MagicMock(spec=datetime)
    dt.hour = hour
    clock = MagicMock(return_value=dt)
    return clock


# ---------------------------------------------------------------------------
# Tests for the Filter protocol
# ---------------------------------------------------------------------------


class TestFilterProtocol:
    """Verify that classes correctly implement the Filter protocol."""

    def test_zone_filter_implements_protocol(self) -> None:
        assert isinstance(ZoneFilter([]), Filter)

    def test_label_filter_implements_protocol(self) -> None:
        assert isinstance(LabelFilter([]), Filter)

    def test_time_filter_implements_protocol(self) -> None:
        assert isinstance(TimeFilter([]), Filter)

    def test_severity_filter_implements_protocol(self) -> None:
        assert isinstance(SeverityFilter([]), Filter)

    def test_filter_chain_implements_protocol(self) -> None:
        assert isinstance(FilterChain([]), Filter)


# ---------------------------------------------------------------------------
# Tests ZoneFilter
# ---------------------------------------------------------------------------


class TestZoneFilter:
    """Tests for zone filter — without order and with order."""

    # --- Empty list = accept all ---

    def test_liste_vide_accepte_tout_zones_vides(self) -> None:
        """Filter with no required zones accepts an event with no zones."""
        f = ZoneFilter([])
        assert f.apply(make_event(zones=[])) is True

    def test_liste_vide_accepte_tout_avec_zones(self) -> None:
        """Filter with no required zones accepts an event with zones."""
        f = ZoneFilter([])
        assert f.apply(make_event(zones=["entree", "jardin"])) is True

    # --- Without order (zone_order_enforced=False) ---

    def test_zone_multi_sans_ordre_toutes_presentes(self) -> None:
        """All required zones present → True."""
        f = ZoneFilter(["entree", "jardin"])
        assert f.apply(make_event(zones=["jardin", "entree", "rue"])) is True

    def test_zone_multi_sans_ordre_exactement_presentes(self) -> None:
        """Required zones exactly equal to event zones → True."""
        f = ZoneFilter(["entree", "jardin"])
        assert f.apply(make_event(zones=["entree", "jardin"])) is True

    def test_zone_multi_sans_ordre_une_manquante(self) -> None:
        """One required zone missing → False."""
        f = ZoneFilter(["entree", "jardin", "rue"])
        assert f.apply(make_event(zones=["entree", "jardin"])) is False

    def test_zone_multi_sans_ordre_toutes_manquantes(self) -> None:
        """No required zone present → False."""
        f = ZoneFilter(["garage", "piscine"])
        assert f.apply(make_event(zones=["entree", "jardin"])) is False

    def test_zone_multi_sans_ordre_event_sans_zones(self) -> None:
        """Required zones not empty but event has no zones → False."""
        f = ZoneFilter(["entree"])
        assert f.apply(make_event(zones=[])) is False

    def test_zone_multi_sans_ordre_une_zone_requise(self) -> None:
        """Single required zone, present → True."""
        f = ZoneFilter(["jardin"])
        assert f.apply(make_event(zones=["jardin", "rue"])) is True

    def test_zone_multi_sans_ordre_une_zone_requise_absente(self) -> None:
        """Single required zone, absent → False."""
        f = ZoneFilter(["piscine"])
        assert f.apply(make_event(zones=["jardin", "rue"])) is False

    # --- With order (zone_order_enforced=True) ---

    def test_zone_order_enforced_sous_sequence_correcte(self) -> None:
        """Correct ordered subsequence → True."""
        f = ZoneFilter(["jardin", "rue"], zone_order_enforced=True)
        assert f.apply(make_event(zones=["entree", "jardin", "rue"])) is True

    def test_zone_order_enforced_sequence_exacte(self) -> None:
        """Sequence identical to event zones → True."""
        f = ZoneFilter(["entree", "jardin"], zone_order_enforced=True)
        assert f.apply(make_event(zones=["entree", "jardin"])) is True

    def test_zone_order_enforced_ordre_incorrect(self) -> None:
        """Zones present but in wrong order → False."""
        f = ZoneFilter(["jardin", "entree"], zone_order_enforced=True)
        # event: entree, then jardin — required subsequence is jardin→entree
        assert f.apply(make_event(zones=["entree", "jardin"])) is False

    def test_zone_order_enforced_ordre_inverse(self) -> None:
        """Required subsequence in reverse order → False."""
        f = ZoneFilter(["rue", "jardin"], zone_order_enforced=True)
        assert f.apply(make_event(zones=["jardin", "rue"])) is False

    def test_zone_order_enforced_une_zone_manquante(self) -> None:
        """One zone of the subsequence missing → False."""
        f = ZoneFilter(["jardin", "piscine"], zone_order_enforced=True)
        assert f.apply(make_event(zones=["entree", "jardin", "rue"])) is False

    def test_zone_order_enforced_event_sans_zones(self) -> None:
        """Required zones not empty, event with no zones → False."""
        f = ZoneFilter(["jardin"], zone_order_enforced=True)
        assert f.apply(make_event(zones=[])) is False

    def test_zone_order_enforced_liste_vide_accepte_tout(self) -> None:
        """zone_order_enforced=True with empty list → accept all."""
        f = ZoneFilter([], zone_order_enforced=True)
        assert f.apply(make_event(zones=["entree"])) is True

    def test_zone_order_enforced_une_zone_correcte(self) -> None:
        """Single-zone subsequence present → True."""
        f = ZoneFilter(["jardin"], zone_order_enforced=True)
        assert f.apply(make_event(zones=["entree", "jardin", "rue"])) is True

    def test_zone_order_enforced_non_contigu(self) -> None:
        """Required zones non-contiguous but in correct order → True.

        Go implements a subsequence (not a contiguous substring).
        """
        f = ZoneFilter(["entree", "rue"], zone_order_enforced=True)
        # entree is before rue → valid subsequence even with jardin interleaved
        assert f.apply(make_event(zones=["entree", "jardin", "rue"])) is True


# ---------------------------------------------------------------------------
# Tests _est_sous_sequence (internal helper)
# ---------------------------------------------------------------------------


class TestEstSousSequence:
    """Tests for the _est_sous_sequence helper function."""

    def test_sous_sequence_simple(self) -> None:
        assert _est_sous_sequence(["a", "b"], ["a", "x", "b"]) is True

    def test_sous_sequence_non_contigue(self) -> None:
        assert _est_sous_sequence(["a", "c"], ["a", "b", "c", "d"]) is True

    def test_sequence_identique(self) -> None:
        assert _est_sous_sequence(["a", "b", "c"], ["a", "b", "c"]) is True

    def test_ordre_incorrect(self) -> None:
        assert _est_sous_sequence(["b", "a"], ["a", "b"]) is False

    def test_element_manquant(self) -> None:
        assert _est_sous_sequence(["a", "d"], ["a", "b", "c"]) is False

    def test_requises_vide(self) -> None:
        assert _est_sous_sequence([], ["a", "b"]) is True

    def test_disponibles_vide(self) -> None:
        assert _est_sous_sequence(["a"], []) is False

    def test_les_deux_vides(self) -> None:
        assert _est_sous_sequence([], []) is True


# ---------------------------------------------------------------------------
# Tests LabelFilter
# ---------------------------------------------------------------------------


class TestLabelFilter:
    """Tests for label (detected objects) filter."""

    # --- Empty list = accept all ---

    def test_liste_vide_accepte_tout_objets_vides(self) -> None:
        """Filter with no labels accepts an event with no objects."""
        f = LabelFilter([])
        assert f.apply(make_event(objects=[])) is True

    def test_liste_vide_accepte_tout_avec_objets(self) -> None:
        """Filter with no labels accepts an event with objects."""
        f = LabelFilter([])
        assert f.apply(make_event(objects=["personne", "chien"])) is True

    # --- At least one match → True ---

    def test_un_objet_match(self) -> None:
        """One event object in labels → True."""
        f = LabelFilter(["personne", "voiture"])
        assert f.apply(make_event(objects=["personne"])) is True

    def test_plusieurs_objets_un_match(self) -> None:
        """Multiple objects, at least one match → True."""
        f = LabelFilter(["personne"])
        assert f.apply(make_event(objects=["chien", "personne", "chat"])) is True

    def test_tous_les_objets_matchent(self) -> None:
        """All event objects are in the labels → True."""
        f = LabelFilter(["personne", "chien"])
        assert f.apply(make_event(objects=["personne", "chien"])) is True

    def test_un_label_exactement_matching(self) -> None:
        """Unique label matching exactly → True."""
        f = LabelFilter(["voiture"])
        assert f.apply(make_event(objects=["voiture"])) is True

    # --- No match → False ---

    def test_aucun_match(self) -> None:
        """No event object in labels → False."""
        f = LabelFilter(["personne", "voiture"])
        assert f.apply(make_event(objects=["chien", "chat"])) is False

    def test_event_sans_objets(self) -> None:
        """Labels not empty but event has no objects → False."""
        f = LabelFilter(["personne"])
        assert f.apply(make_event(objects=[])) is False

    def test_labels_non_vides_objets_differents(self) -> None:
        """Labels present but no intersection → False."""
        f = LabelFilter(["voiture", "moto"])
        assert f.apply(make_event(objects=["personne", "chien"])) is False

    def test_correspondance_sensible_casse(self) -> None:
        """Matching is case-sensitive (Python str)."""
        f = LabelFilter(["Personne"])
        # "personne" (lowercase) != "Personne" (capitalized)
        assert f.apply(make_event(objects=["personne"])) is False


# ---------------------------------------------------------------------------
# Tests TimeFilter
# ---------------------------------------------------------------------------


class TestTimeFilter:
    """Tests for time filter with injectable clock."""

    # --- Empty list = accept all ---

    def test_liste_vide_accepte_tout_nimporte_quelle_heure(self) -> None:
        """No disabled hours → always accept."""
        f = TimeFilter([], clock=make_clock(3))
        assert f.apply(make_event()) is True

    def test_liste_vide_accepte_minuit(self) -> None:
        """No disabled hours, hour=0 → accept."""
        f = TimeFilter([], clock=make_clock(0))
        assert f.apply(make_event()) is True

    # --- Hour in disabled_hours → False ---

    def test_heure_dans_disabled_hours_bloque(self) -> None:
        """Current hour in disabled_hours → False."""
        f = TimeFilter([2, 3, 4], clock=make_clock(3))
        assert f.apply(make_event()) is False

    def test_heure_minuit_desactivee(self) -> None:
        """Hour 0 (midnight) disabled → False."""
        f = TimeFilter([0, 1, 2], clock=make_clock(0))
        assert f.apply(make_event()) is False

    def test_heure_23_desactivee(self) -> None:
        """Hour 23 disabled → False."""
        f = TimeFilter([22, 23], clock=make_clock(23))
        assert f.apply(make_event()) is False

    def test_toutes_heures_desactivees(self) -> None:
        """All hours disabled → always False."""
        f = TimeFilter(list(range(24)), clock=make_clock(12))
        assert f.apply(make_event()) is False

    # --- Hour outside disabled_hours → True ---

    def test_heure_hors_disabled_hours_accepte(self) -> None:
        """Current hour outside disabled_hours → True."""
        f = TimeFilter([2, 3, 4], clock=make_clock(10))
        assert f.apply(make_event()) is True

    def test_heure_juste_avant_plage_desactivee(self) -> None:
        """Hour just before disabled range → True."""
        f = TimeFilter([2, 3, 4], clock=make_clock(1))
        assert f.apply(make_event()) is True

    def test_heure_juste_apres_plage_desactivee(self) -> None:
        """Hour just after disabled range → True."""
        f = TimeFilter([2, 3, 4], clock=make_clock(5))
        assert f.apply(make_event()) is True

    def test_clock_appelee_a_chaque_apply(self) -> None:
        """Clock is called on each apply() call (not cached)."""
        clock = make_clock(10)
        f = TimeFilter([10], clock=clock)
        f.apply(make_event())
        f.apply(make_event())
        assert clock.call_count == 2

    def test_event_non_utilise(self) -> None:
        """Time filter ignores event content."""
        f = TimeFilter([14], clock=make_clock(14))
        # Event has no objects or zones — irrelevant
        assert f.apply(make_event(objects=["personne"], zones=["jardin"])) is False

    def test_clock_par_defaut_est_datetime_now(self) -> None:
        """Without injectable clock, filter uses datetime.now (no error)."""
        f = TimeFilter([])  # empty list = accept all, regardless of hour
        assert f.apply(make_event()) is True


# ---------------------------------------------------------------------------
# Tests FilterChain
# ---------------------------------------------------------------------------


class TestFilterChain:
    """Tests for filter chain — AND logic with short-circuit."""

    # --- Empty chain → accept all ---

    def test_chaine_vide_accepte_tout(self) -> None:
        """Chain with no filters → True for any event."""
        chain = FilterChain([])
        assert chain.apply(make_event()) is True

    def test_chaine_vide_accepte_event_vide(self) -> None:
        """Empty chain → True even for event with no data."""
        chain = FilterChain([])
        assert chain.apply(make_event(objects=[], zones=[])) is True

    # --- All accept → True ---

    def test_tous_filtres_acceptent(self) -> None:
        """All filters accept → True."""
        chain = FilterChain([
            ZoneFilter([]),
            LabelFilter([]),
            TimeFilter([], clock=make_clock(12)),
        ])
        assert chain.apply(make_event()) is True

    def test_filtres_avec_conditions_toutes_verifiees(self) -> None:
        """Filters with real conditions, all satisfied → True."""
        chain = FilterChain([
            ZoneFilter(["jardin"]),
            LabelFilter(["personne"]),
            TimeFilter([2, 3], clock=make_clock(10)),
        ])
        event = make_event(objects=["personne"], zones=["jardin"])
        assert chain.apply(event) is True

    def test_un_seul_filtre_qui_accepte(self) -> None:
        """Chain of one accepting filter → True."""
        chain = FilterChain([LabelFilter([])])
        assert chain.apply(make_event()) is True

    # --- One rejects → False (short-circuit) ---

    def test_premier_filtre_refuse(self) -> None:
        """First filter rejects → False (short-circuit)."""
        chain = FilterChain([
            LabelFilter(["voiture"]),   # rejects: no car
            LabelFilter([]),             # would accept all
        ])
        event = make_event(objects=["personne"])
        assert chain.apply(event) is False

    def test_dernier_filtre_refuse(self) -> None:
        """All filters accept except the last → False."""
        chain = FilterChain([
            ZoneFilter([]),
            LabelFilter([]),
            TimeFilter([12], clock=make_clock(12)),  # rejects at 12h
        ])
        assert chain.apply(make_event()) is False

    def test_filtre_du_milieu_refuse(self) -> None:
        """Middle filter rejects → False."""
        chain = FilterChain([
            ZoneFilter([]),                          # accepts
            LabelFilter(["voiture"]),                # rejects
            TimeFilter([], clock=make_clock(10)),    # would accept
        ])
        event = make_event(objects=["personne"])
        assert chain.apply(event) is False

    def test_court_circuit_verifie_via_mock(self) -> None:
        """Short-circuit: third filter is not called if second rejects."""
        filtre_espion = MagicMock(spec=Filter)
        filtre_espion.apply.return_value = True

        filtre_refus = MagicMock(spec=Filter)
        filtre_refus.apply.return_value = False

        filtre_non_appele = MagicMock(spec=Filter)
        filtre_non_appele.apply.return_value = True

        chain = FilterChain([filtre_espion, filtre_refus, filtre_non_appele])
        result = chain.apply(make_event())

        assert result is False
        filtre_espion.apply.assert_called_once()
        filtre_refus.apply.assert_called_once()
        # Short-circuit: third filter is never called
        filtre_non_appele.apply.assert_not_called()

    def test_chaine_mixte_zone_label_time(self) -> None:
        """Realistic full chain — compliant event passes, non-compliant fails."""
        chain = FilterChain([
            ZoneFilter(["entree", "jardin"]),
            LabelFilter(["personne"]),
            TimeFilter([2, 3, 4], clock=make_clock(10)),
        ])
        event_ok = make_event(objects=["personne"], zones=["entree", "jardin"])
        event_mauvaise_zone = make_event(objects=["personne"], zones=["entree"])
        event_mauvais_label = make_event(objects=["chien"], zones=["entree", "jardin"])

        assert chain.apply(event_ok) is True
        assert chain.apply(event_mauvaise_zone) is False
        assert chain.apply(event_mauvais_label) is False

    def test_chaine_avec_severity_filter(self) -> None:
        """SeverityFilter integrated in the chain — unauthorized severity is blocked."""
        chain = FilterChain([
            LabelFilter([]),
            SeverityFilter(["alert"]),
        ])
        assert chain.apply(make_event(severity="alert")) is True
        assert chain.apply(make_event(severity="detection")) is False


# ---------------------------------------------------------------------------
# Tests SeverityFilter
# ---------------------------------------------------------------------------


class TestSeverityFilter:
    """Tests for Frigate severity filter."""

    # --- Empty list = accept all ---

    def test_liste_vide_accepte_alert(self) -> None:
        """Filter with no severities accepts alert severity."""
        f = SeverityFilter([])
        assert f.apply(make_event(severity="alert")) is True

    def test_liste_vide_accepte_detection(self) -> None:
        """Filter with no severities accepts detection severity."""
        f = SeverityFilter([])
        assert f.apply(make_event(severity="detection")) is True

    def test_liste_vide_accepte_severity_inconnue(self) -> None:
        """Filter with no severities accepts any severity."""
        f = SeverityFilter([])
        assert f.apply(make_event(severity="unknown")) is True

    # --- Severity in list → True ---

    def test_alert_dans_filtre_alert(self) -> None:
        """Alert severity with filter ["alert"] → True."""
        f = SeverityFilter(["alert"])
        assert f.apply(make_event(severity="alert")) is True

    def test_detection_dans_filtre_detection(self) -> None:
        """Detection severity with filter ["detection"] → True."""
        f = SeverityFilter(["detection"])
        assert f.apply(make_event(severity="detection")) is True

    def test_alert_dans_filtre_alert_et_detection(self) -> None:
        """Alert severity with filter ["alert", "detection"] → True."""
        f = SeverityFilter(["alert", "detection"])
        assert f.apply(make_event(severity="alert")) is True

    def test_detection_dans_filtre_alert_et_detection(self) -> None:
        """Detection severity with filter ["alert", "detection"] → True."""
        f = SeverityFilter(["alert", "detection"])
        assert f.apply(make_event(severity="detection")) is True

    # --- Severity outside list → False ---

    def test_detection_bloquee_par_filtre_alert(self) -> None:
        """Detection severity with filter ["alert"] → False."""
        f = SeverityFilter(["alert"])
        assert f.apply(make_event(severity="detection")) is False

    def test_alert_bloquee_par_filtre_detection(self) -> None:
        """Alert severity with filter ["detection"] → False."""
        f = SeverityFilter(["detection"])
        assert f.apply(make_event(severity="alert")) is False

    def test_severity_inconnue_bloquee(self) -> None:
        """Severity not in filter → False."""
        f = SeverityFilter(["alert"])
        assert f.apply(make_event(severity="unknown")) is False
