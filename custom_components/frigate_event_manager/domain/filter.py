"""Filtres d'événements Frigate — logique de filtrage domaine pur.

Chaque filtre implémente le protocole `Filter` (méthode `apply`).
Convention : liste vide = tout accepter (aucun filtrage).

Chaîne de filtres : FilterChain applique chaque filtre en séquence.
Un seul refus suffit pour bloquer l'événement.
"""

from __future__ import annotations

from datetime import datetime, timezone
from collections.abc import Callable
from typing import Protocol, runtime_checkable

from .model import FrigateEvent


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
        self.zone_multi = zone_multi
        self.zone_order_enforced = zone_order_enforced

    def apply(self, event: FrigateEvent) -> bool:
        """Retourne True si l'événement passe le filtre de zones."""
        if not self.zone_multi:
            return True

        if self.zone_order_enforced:
            return _est_sous_sequence(self.zone_multi, event.zones)

        zones_event = set(event.zones)
        return all(zone in zones_event for zone in self.zone_multi)


def _est_sous_sequence(requises: list[str], disponibles: list[str]) -> bool:
    """Vérifie que `requises` est une sous-séquence ordonnée de `disponibles`."""
    it = iter(disponibles)
    return all(zone in it for zone in requises)


class LabelFilter:
    """Filtre par labels (objets détectés) dans l'événement.

    Au moins un objet de l'événement doit correspondre à un label configuré.
    Convention : si `labels` est vide, tous les événements sont acceptés.
    """

    def __init__(self, labels: list[str]) -> None:
        self.labels = labels

    def apply(self, event: FrigateEvent) -> bool:
        """Retourne True si au moins un objet de l'événement est dans les labels."""
        if not self.labels:
            return True

        labels_autorises = set(self.labels)
        return any(obj in labels_autorises for obj in event.objects)


class TimeFilter:
    """Filtre par plage horaire — bloque les événements aux heures désactivées.

    Convention : si `disabled_hours` est vide, tous les événements sont acceptés.
    """

    def __init__(
        self,
        disabled_hours: list[int],
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.disabled_hours = disabled_hours
        self._clock: Callable[[], datetime] = (
            clock if clock is not None else lambda: datetime.now(tz=timezone.utc).astimezone()
        )

    def apply(self, event: FrigateEvent) -> bool:  # noqa: ARG002
        """Retourne True si l'heure courante n'est pas une heure désactivée."""
        if not self.disabled_hours:
            return True

        heure_courante = self._clock().hour
        return heure_courante not in self.disabled_hours


class SeverityFilter:
    """Filtre par severity Frigate — liste vide = tout accepter."""

    def __init__(self, severities: list[str]) -> None:
        self._severities = severities

    def apply(self, event: FrigateEvent) -> bool:
        """Retourne True si la severity de l'événement est dans la liste autorisée."""
        if not self._severities:
            return True
        return event.severity in self._severities


class FilterChain:
    """Chaîne de filtres appliqués en séquence à chaque événement.

    Tous les filtres doivent accepter l'événement pour qu'il soit traité.
    Court-circuit : s'arrête au premier refus.
    """

    def __init__(self, filters: list[Filter]) -> None:
        self.filters = filters

    def apply(self, event: FrigateEvent) -> bool:
        """Retourne True si tous les filtres acceptent l'événement."""
        return all(f.apply(event) for f in self.filters)
