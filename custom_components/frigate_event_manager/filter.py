"""Filtres d'événements Frigate — traduction des filtres Go en Python.

Chaque filtre implémente le protocole `Filter` (méthode `apply`).
Convention : liste vide = tout accepter (aucun filtrage).

Chaîne de filtres : FilterChain applique chaque filtre en séquence.
Un seul refus suffit pour bloquer l'événement.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable, Protocol, runtime_checkable

from .coordinator import FrigateEvent


@runtime_checkable
class Filter(Protocol):
    """Protocole commun à tous les filtres d'événements."""

    def apply(self, event: FrigateEvent) -> bool:
        """Retourne True si l'événement est accepté, False s'il est bloqué."""
        ...


class ZoneFilter:
    """Filtre par zones actives dans l'événement.

    Deux modes de fonctionnement :
    - Sans ordre (zone_order_enforced=False) : toutes les zones de `zone_multi`
      doivent être présentes dans l'événement, mais dans n'importe quel ordre.
    - Avec ordre (zone_order_enforced=True) : les zones de `zone_multi` doivent
      apparaître comme sous-séquence ordonnée dans la liste des zones de l'événement.

    Convention : si `zone_multi` est vide, tous les événements sont acceptés.
    """

    def __init__(
        self,
        zone_multi: list[str],
        zone_order_enforced: bool = False,
    ) -> None:
        """Initialise le filtre de zones.

        Args:
            zone_multi: Liste des zones requises (vide = tout accepter).
            zone_order_enforced: Si True, les zones doivent apparaître dans
                l'ordre comme sous-séquence ordonnée dans l'événement.
        """
        self.zone_multi = zone_multi
        self.zone_order_enforced = zone_order_enforced

    def apply(self, event: FrigateEvent) -> bool:
        """Retourne True si l'événement passe le filtre de zones.

        - Liste vide : accepte tout.
        - Sans ordre : toutes les zones requises sont présentes (set ⊆ set).
        - Avec ordre : les zones requises forment une sous-séquence ordonnée.
        """
        # Convention : liste vide = tout accepter
        if not self.zone_multi:
            return True

        if self.zone_order_enforced:
            return _est_sous_sequence(self.zone_multi, event.zones)

        # Sans ordre : toutes les zones requises doivent être présentes
        zones_event = set(event.zones)
        return all(zone in zones_event for zone in self.zone_multi)


def _est_sous_sequence(requises: list[str], disponibles: list[str]) -> bool:
    """Vérifie que `requises` est une sous-séquence ordonnée de `disponibles`.

    Exemple : ["jardin", "rue"] est sous-séquence de ["entrée", "jardin", "rue"]
    mais pas de ["rue", "jardin"].
    """
    it = iter(disponibles)
    return all(zone in it for zone in requises)


class LabelFilter:
    """Filtre par labels (objets détectés) dans l'événement.

    Au moins un objet de l'événement doit correspondre à un label configuré.
    Convention : si `labels` est vide, tous les événements sont acceptés.
    """

    def __init__(self, labels: list[str]) -> None:
        """Initialise le filtre de labels.

        Args:
            labels: Liste des labels acceptés (vide = tout accepter).
        """
        self.labels = labels

    def apply(self, event: FrigateEvent) -> bool:
        """Retourne True si au moins un objet de l'événement est dans les labels.

        - Liste vide : accepte tout.
        - Sinon : au moins une intersection entre objets de l'événement et labels.
        """
        # Convention : liste vide = tout accepter
        if not self.labels:
            return True

        labels_autorises = set(self.labels)
        return any(obj in labels_autorises for obj in event.objects)


class TimeFilter:
    """Filtre par plage horaire — bloque les événements aux heures désactivées.

    Les heures désactivées (0-23) définissent des plages où les événements
    sont rejetés. La clock est injectable pour faciliter les tests.

    Convention : si `disabled_hours` est vide, tous les événements sont acceptés.
    """

    def __init__(
        self,
        disabled_hours: list[int],
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        """Initialise le filtre temporel.

        Args:
            disabled_hours: Heures (0-23) où les événements sont bloqués
                (liste vide = tout accepter).
            clock: Fonction retournant l'heure courante. Défaut : datetime.now()
                   converti en heure locale du serveur via .astimezone() — les
                   disabled_hours doivent donc être exprimées en heure locale du
                   serveur Home Assistant. Si HA tourne en UTC, configurer les
                   heures en UTC. Injectable pour les tests unitaires.
        """
        self.disabled_hours = disabled_hours
        self._clock: Callable[[], datetime] = (
            clock if clock is not None else lambda: datetime.now(tz=timezone.utc).astimezone()
        )

    def apply(self, event: FrigateEvent) -> bool:  # noqa: ARG002
        """Retourne True si l'heure courante n'est pas une heure désactivée.

        Le paramètre `event` n'est pas utilisé — le filtre est uniquement
        basé sur l'heure courante.

        - Liste vide : accepte tout.
        - Sinon : bloque si l'heure courante est dans `disabled_hours`.
        """
        # Convention : liste vide = tout accepter
        if not self.disabled_hours:
            return True

        heure_courante = self._clock().hour
        return heure_courante not in self.disabled_hours


class FilterChain:
    """Chaîne de filtres appliqués en séquence à chaque événement.

    Tous les filtres doivent accepter l'événement pour qu'il soit traité.
    Un seul refus suffit pour bloquer l'événement (logique ET).
    Court-circuit : s'arrête au premier refus.
    """

    def __init__(self, filters: list[Filter]) -> None:
        """Initialise la chaîne avec une liste de filtres ordonnés.

        Args:
            filters: Liste de filtres à appliquer en séquence.
                     Une liste vide accepte tous les événements.
        """
        self.filters = filters

    def apply(self, event: FrigateEvent) -> bool:
        """Retourne True si tous les filtres acceptent l'événement.

        Court-circuit dès le premier refus pour optimiser les performances.
        Une chaîne vide accepte tous les événements.
        """
        return all(f.apply(event) for f in self.filters)
