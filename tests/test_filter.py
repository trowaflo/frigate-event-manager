"""Tests des filtres d'événements Frigate — ZoneFilter, LabelFilter, TimeFilter, FilterChain.

Traduit les cas de tests Go (zone_multi, order_enforced, clock mock) en Python.
Convention testée : liste vide = tout accepter (aucun filtrage).
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

import pytest

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
# Helpers — constructeurs minimaux de FrigateEvent
# ---------------------------------------------------------------------------


def make_event(
    *,
    camera: str = "jardin",
    type: str = "new",
    severity: str = "alert",
    objects: list[str] | None = None,
    zones: list[str] | None = None,
) -> FrigateEvent:
    """Construit un FrigateEvent minimal pour les tests de filtres."""
    return FrigateEvent(
        type=type,
        camera=camera,
        severity=severity,
        objects=objects if objects is not None else [],
        zones=zones if zones is not None else [],
    )


def make_clock(hour: int) -> MagicMock:
    """Retourne une clock mockée dont l'heure est fixée à `hour`."""
    dt = MagicMock(spec=datetime)
    dt.hour = hour
    clock = MagicMock(return_value=dt)
    return clock


# ---------------------------------------------------------------------------
# Tests du protocole Filter
# ---------------------------------------------------------------------------


class TestFilterProtocol:
    """Vérifie que les classes implémentent bien le protocole Filter."""

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
    """Tests du filtre de zones — sans ordre et avec ordre."""

    # --- Liste vide = tout accepter ---

    def test_liste_vide_accepte_tout_zones_vides(self) -> None:
        """Filtre sans zones requises accepte un événement sans zones."""
        f = ZoneFilter([])
        assert f.apply(make_event(zones=[])) is True

    def test_liste_vide_accepte_tout_avec_zones(self) -> None:
        """Filtre sans zones requises accepte un événement avec zones."""
        f = ZoneFilter([])
        assert f.apply(make_event(zones=["entree", "jardin"])) is True

    # --- Sans ordre (zone_order_enforced=False) ---

    def test_zone_multi_sans_ordre_toutes_presentes(self) -> None:
        """Toutes les zones requises présentes → True."""
        f = ZoneFilter(["entree", "jardin"])
        assert f.apply(make_event(zones=["jardin", "entree", "rue"])) is True

    def test_zone_multi_sans_ordre_exactement_presentes(self) -> None:
        """Zones requises exactement égales à zones de l'événement → True."""
        f = ZoneFilter(["entree", "jardin"])
        assert f.apply(make_event(zones=["entree", "jardin"])) is True

    def test_zone_multi_sans_ordre_une_manquante(self) -> None:
        """Une zone requise absente → False."""
        f = ZoneFilter(["entree", "jardin", "rue"])
        assert f.apply(make_event(zones=["entree", "jardin"])) is False

    def test_zone_multi_sans_ordre_toutes_manquantes(self) -> None:
        """Aucune zone requise présente → False."""
        f = ZoneFilter(["garage", "piscine"])
        assert f.apply(make_event(zones=["entree", "jardin"])) is False

    def test_zone_multi_sans_ordre_event_sans_zones(self) -> None:
        """Zones requises non vides mais événement sans zones → False."""
        f = ZoneFilter(["entree"])
        assert f.apply(make_event(zones=[])) is False

    def test_zone_multi_sans_ordre_une_zone_requise(self) -> None:
        """Une seule zone requise, présente → True."""
        f = ZoneFilter(["jardin"])
        assert f.apply(make_event(zones=["jardin", "rue"])) is True

    def test_zone_multi_sans_ordre_une_zone_requise_absente(self) -> None:
        """Une seule zone requise, absente → False."""
        f = ZoneFilter(["piscine"])
        assert f.apply(make_event(zones=["jardin", "rue"])) is False

    # --- Avec ordre (zone_order_enforced=True) ---

    def test_zone_order_enforced_sous_sequence_correcte(self) -> None:
        """Sous-séquence ordonnée correcte → True."""
        f = ZoneFilter(["jardin", "rue"], zone_order_enforced=True)
        assert f.apply(make_event(zones=["entree", "jardin", "rue"])) is True

    def test_zone_order_enforced_sequence_exacte(self) -> None:
        """Séquence identique aux zones de l'événement → True."""
        f = ZoneFilter(["entree", "jardin"], zone_order_enforced=True)
        assert f.apply(make_event(zones=["entree", "jardin"])) is True

    def test_zone_order_enforced_ordre_incorrect(self) -> None:
        """Zones présentes mais dans le mauvais ordre → False."""
        f = ZoneFilter(["jardin", "entree"], zone_order_enforced=True)
        # événement : entree, puis jardin — sous-séquence requise est jardin→entree
        assert f.apply(make_event(zones=["entree", "jardin"])) is False

    def test_zone_order_enforced_ordre_inverse(self) -> None:
        """Sous-séquence requise en ordre inverse → False."""
        f = ZoneFilter(["rue", "jardin"], zone_order_enforced=True)
        assert f.apply(make_event(zones=["jardin", "rue"])) is False

    def test_zone_order_enforced_une_zone_manquante(self) -> None:
        """Une zone de la sous-séquence absente → False."""
        f = ZoneFilter(["jardin", "piscine"], zone_order_enforced=True)
        assert f.apply(make_event(zones=["entree", "jardin", "rue"])) is False

    def test_zone_order_enforced_event_sans_zones(self) -> None:
        """Zones requises non vides, événement sans zones → False."""
        f = ZoneFilter(["jardin"], zone_order_enforced=True)
        assert f.apply(make_event(zones=[])) is False

    def test_zone_order_enforced_liste_vide_accepte_tout(self) -> None:
        """Zone_order_enforced=True avec liste vide → tout accepter."""
        f = ZoneFilter([], zone_order_enforced=True)
        assert f.apply(make_event(zones=["entree"])) is True

    def test_zone_order_enforced_une_zone_correcte(self) -> None:
        """Sous-séquence d'une seule zone présente → True."""
        f = ZoneFilter(["jardin"], zone_order_enforced=True)
        assert f.apply(make_event(zones=["entree", "jardin", "rue"])) is True

    def test_zone_order_enforced_non_contigu(self) -> None:
        """Zones requises non contiguës mais dans le bon ordre → True.

        Go implémente une sous-séquence (pas une sous-chaîne contiguë).
        """
        f = ZoneFilter(["entree", "rue"], zone_order_enforced=True)
        # entree est avant rue → sous-séquence valide même si jardin intercalé
        assert f.apply(make_event(zones=["entree", "jardin", "rue"])) is True


# ---------------------------------------------------------------------------
# Tests _est_sous_sequence (helper interne)
# ---------------------------------------------------------------------------


class TestEstSousSequence:
    """Tests de la fonction helper _est_sous_sequence."""

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
    """Tests du filtre par labels (objets détectés)."""

    # --- Liste vide = tout accepter ---

    def test_liste_vide_accepte_tout_objets_vides(self) -> None:
        """Filtre sans labels accepte un événement sans objets."""
        f = LabelFilter([])
        assert f.apply(make_event(objects=[])) is True

    def test_liste_vide_accepte_tout_avec_objets(self) -> None:
        """Filtre sans labels accepte un événement avec objets."""
        f = LabelFilter([])
        assert f.apply(make_event(objects=["personne", "chien"])) is True

    # --- Au moins un match → True ---

    def test_un_objet_match(self) -> None:
        """Un objet de l'événement dans les labels → True."""
        f = LabelFilter(["personne", "voiture"])
        assert f.apply(make_event(objects=["personne"])) is True

    def test_plusieurs_objets_un_match(self) -> None:
        """Plusieurs objets, au moins un match → True."""
        f = LabelFilter(["personne"])
        assert f.apply(make_event(objects=["chien", "personne", "chat"])) is True

    def test_tous_les_objets_matchent(self) -> None:
        """Tous les objets de l'événement sont dans les labels → True."""
        f = LabelFilter(["personne", "chien"])
        assert f.apply(make_event(objects=["personne", "chien"])) is True

    def test_un_label_exactement_matching(self) -> None:
        """Label unique correspondant exactement → True."""
        f = LabelFilter(["voiture"])
        assert f.apply(make_event(objects=["voiture"])) is True

    # --- Aucun match → False ---

    def test_aucun_match(self) -> None:
        """Aucun objet de l'événement dans les labels → False."""
        f = LabelFilter(["personne", "voiture"])
        assert f.apply(make_event(objects=["chien", "chat"])) is False

    def test_event_sans_objets(self) -> None:
        """Labels non vides mais événement sans objets → False."""
        f = LabelFilter(["personne"])
        assert f.apply(make_event(objects=[])) is False

    def test_labels_non_vides_objets_differents(self) -> None:
        """Labels présents mais aucune intersection → False."""
        f = LabelFilter(["voiture", "moto"])
        assert f.apply(make_event(objects=["personne", "chien"])) is False

    def test_correspondance_sensible_casse(self) -> None:
        """La correspondance est sensible à la casse (Python str)."""
        f = LabelFilter(["Personne"])
        # "personne" (minuscule) != "Personne" (majuscule)
        assert f.apply(make_event(objects=["personne"])) is False


# ---------------------------------------------------------------------------
# Tests TimeFilter
# ---------------------------------------------------------------------------


class TestTimeFilter:
    """Tests du filtre horaire avec clock injectable."""

    # --- Liste vide = tout accepter ---

    def test_liste_vide_accepte_tout_nimporte_quelle_heure(self) -> None:
        """Aucune heure désactivée → toujours accepter."""
        f = TimeFilter([], clock=make_clock(3))
        assert f.apply(make_event()) is True

    def test_liste_vide_accepte_minuit(self) -> None:
        """Aucune heure désactivée, heure=0 → accepter."""
        f = TimeFilter([], clock=make_clock(0))
        assert f.apply(make_event()) is True

    # --- Heure dans disabled_hours → False ---

    def test_heure_dans_disabled_hours_bloque(self) -> None:
        """Heure courante dans disabled_hours → False."""
        f = TimeFilter([2, 3, 4], clock=make_clock(3))
        assert f.apply(make_event()) is False

    def test_heure_minuit_desactivee(self) -> None:
        """Heure 0 (minuit) désactivée → False."""
        f = TimeFilter([0, 1, 2], clock=make_clock(0))
        assert f.apply(make_event()) is False

    def test_heure_23_desactivee(self) -> None:
        """Heure 23 désactivée → False."""
        f = TimeFilter([22, 23], clock=make_clock(23))
        assert f.apply(make_event()) is False

    def test_toutes_heures_desactivees(self) -> None:
        """Toutes les heures désactivées → toujours False."""
        f = TimeFilter(list(range(24)), clock=make_clock(12))
        assert f.apply(make_event()) is False

    # --- Heure hors disabled_hours → True ---

    def test_heure_hors_disabled_hours_accepte(self) -> None:
        """Heure courante hors disabled_hours → True."""
        f = TimeFilter([2, 3, 4], clock=make_clock(10))
        assert f.apply(make_event()) is True

    def test_heure_juste_avant_plage_desactivee(self) -> None:
        """Heure juste avant la plage désactivée → True."""
        f = TimeFilter([2, 3, 4], clock=make_clock(1))
        assert f.apply(make_event()) is True

    def test_heure_juste_apres_plage_desactivee(self) -> None:
        """Heure juste après la plage désactivée → True."""
        f = TimeFilter([2, 3, 4], clock=make_clock(5))
        assert f.apply(make_event()) is True

    def test_clock_appelee_a_chaque_apply(self) -> None:
        """La clock est appelée à chaque appel d'apply (pas mis en cache)."""
        clock = make_clock(10)
        f = TimeFilter([10], clock=clock)
        f.apply(make_event())
        f.apply(make_event())
        assert clock.call_count == 2

    def test_event_non_utilise(self) -> None:
        """Le filtre horaire ignore le contenu de l'événement."""
        f = TimeFilter([14], clock=make_clock(14))
        # L'événement n'a aucun objet ni zone — aucune importance
        assert f.apply(make_event(objects=["personne"], zones=["jardin"])) is False

    def test_clock_par_defaut_est_datetime_now(self) -> None:
        """Sans clock injectable, le filtre utilise datetime.now (pas d'erreur)."""
        f = TimeFilter([])  # liste vide = tout accepter, peu importe l'heure
        assert f.apply(make_event()) is True


# ---------------------------------------------------------------------------
# Tests FilterChain
# ---------------------------------------------------------------------------


class TestFilterChain:
    """Tests de la chaîne de filtres — logique ET avec court-circuit."""

    # --- Chaîne vide → accepte tout ---

    def test_chaine_vide_accepte_tout(self) -> None:
        """Chaîne sans filtres → True pour tout événement."""
        chain = FilterChain([])
        assert chain.apply(make_event()) is True

    def test_chaine_vide_accepte_event_vide(self) -> None:
        """Chaîne vide → True même pour un événement sans données."""
        chain = FilterChain([])
        assert chain.apply(make_event(objects=[], zones=[])) is True

    # --- Tous acceptent → True ---

    def test_tous_filtres_acceptent(self) -> None:
        """Tous les filtres acceptent → True."""
        chain = FilterChain([
            ZoneFilter([]),
            LabelFilter([]),
            TimeFilter([], clock=make_clock(12)),
        ])
        assert chain.apply(make_event()) is True

    def test_filtres_avec_conditions_toutes_verifiees(self) -> None:
        """Filtres avec conditions réelles, toutes satisfaites → True."""
        chain = FilterChain([
            ZoneFilter(["jardin"]),
            LabelFilter(["personne"]),
            TimeFilter([2, 3], clock=make_clock(10)),
        ])
        event = make_event(objects=["personne"], zones=["jardin"])
        assert chain.apply(event) is True

    def test_un_seul_filtre_qui_accepte(self) -> None:
        """Chaîne d'un seul filtre acceptant → True."""
        chain = FilterChain([LabelFilter([])])
        assert chain.apply(make_event()) is True

    # --- Un refuse → False (court-circuit) ---

    def test_premier_filtre_refuse(self) -> None:
        """Le premier filtre refuse → False (court-circuit)."""
        chain = FilterChain([
            LabelFilter(["voiture"]),   # refuse : pas de voiture
            LabelFilter([]),             # accepterait tout
        ])
        event = make_event(objects=["personne"])
        assert chain.apply(event) is False

    def test_dernier_filtre_refuse(self) -> None:
        """Tous les filtres acceptent sauf le dernier → False."""
        chain = FilterChain([
            ZoneFilter([]),
            LabelFilter([]),
            TimeFilter([12], clock=make_clock(12)),  # refuse à 12h
        ])
        assert chain.apply(make_event()) is False

    def test_filtre_du_milieu_refuse(self) -> None:
        """Le filtre intermédiaire refuse → False."""
        chain = FilterChain([
            ZoneFilter([]),                          # accepte
            LabelFilter(["voiture"]),                # refuse
            TimeFilter([], clock=make_clock(10)),    # accepterait
        ])
        event = make_event(objects=["personne"])
        assert chain.apply(event) is False

    def test_court_circuit_verifie_via_mock(self) -> None:
        """Court-circuit : le troisième filtre n'est pas appelé si le second refuse."""
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
        # Court-circuit : le troisième filtre n'est jamais appelé
        filtre_non_appele.apply.assert_not_called()

    def test_chaine_mixte_zone_label_time(self) -> None:
        """Chaîne réaliste complète — event conforme passe, non-conforme échoue."""
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
        """SeverityFilter intégré dans la chaîne — severity non autorisée bloque."""
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
    """Tests du filtre par severity Frigate."""

    # --- Liste vide = tout accepter ---

    def test_liste_vide_accepte_alert(self) -> None:
        """Filtre sans severities accepte une severity alert."""
        f = SeverityFilter([])
        assert f.apply(make_event(severity="alert")) is True

    def test_liste_vide_accepte_detection(self) -> None:
        """Filtre sans severities accepte une severity detection."""
        f = SeverityFilter([])
        assert f.apply(make_event(severity="detection")) is True

    def test_liste_vide_accepte_severity_inconnue(self) -> None:
        """Filtre sans severities accepte n'importe quelle severity."""
        f = SeverityFilter([])
        assert f.apply(make_event(severity="unknown")) is True

    # --- Severity dans la liste → True ---

    def test_alert_dans_filtre_alert(self) -> None:
        """Severity alert avec filtre ["alert"] → True."""
        f = SeverityFilter(["alert"])
        assert f.apply(make_event(severity="alert")) is True

    def test_detection_dans_filtre_detection(self) -> None:
        """Severity detection avec filtre ["detection"] → True."""
        f = SeverityFilter(["detection"])
        assert f.apply(make_event(severity="detection")) is True

    def test_alert_dans_filtre_alert_et_detection(self) -> None:
        """Severity alert avec filtre ["alert", "detection"] → True."""
        f = SeverityFilter(["alert", "detection"])
        assert f.apply(make_event(severity="alert")) is True

    def test_detection_dans_filtre_alert_et_detection(self) -> None:
        """Severity detection avec filtre ["alert", "detection"] → True."""
        f = SeverityFilter(["alert", "detection"])
        assert f.apply(make_event(severity="detection")) is True

    # --- Severity hors liste → False ---

    def test_detection_bloquee_par_filtre_alert(self) -> None:
        """Severity detection avec filtre ["alert"] → False."""
        f = SeverityFilter(["alert"])
        assert f.apply(make_event(severity="detection")) is False

    def test_alert_bloquee_par_filtre_detection(self) -> None:
        """Severity alert avec filtre ["detection"] → False."""
        f = SeverityFilter(["detection"])
        assert f.apply(make_event(severity="alert")) is False

    def test_severity_inconnue_bloquee(self) -> None:
        """Severity non listée dans le filtre → False."""
        f = SeverityFilter(["alert"])
        assert f.apply(make_event(severity="unknown")) is False
