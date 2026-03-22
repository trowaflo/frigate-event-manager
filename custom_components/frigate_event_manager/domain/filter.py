"""Frigate event filters — pure domain filtering logic.

Each filter implements the `Filter` protocol (method `apply`).
Convention: empty list = accept all (no filtering).

Filter chain: FilterChain applies each filter in sequence.
A single rejection is enough to block the event.
"""

from __future__ import annotations

from datetime import datetime, timezone
from collections.abc import Callable
from typing import Protocol, runtime_checkable

from .model import FrigateEvent


@runtime_checkable
class Filter(Protocol):
    """Common protocol for all event filters."""

    def apply(self, event: FrigateEvent) -> bool:
        """Return True if the event is accepted, False if blocked."""
        ...


class ZoneFilter:
    """Filter by active zones in the event.

    Two operating modes:
    - Without order (zone_order_enforced=False): all zones in `zone_multi`
      must be present in the event, in any order.
    - With order (zone_order_enforced=True): zones in `zone_multi` must
      appear as an ordered subsequence in the event's zone list.

    Convention: if `zone_multi` is empty, all events are accepted.
    """

    def __init__(
        self,
        zone_multi: list[str],
        zone_order_enforced: bool = False,
    ) -> None:
        self.zone_multi = zone_multi
        self.zone_order_enforced = zone_order_enforced

    def apply(self, event: FrigateEvent) -> bool:
        """Return True if the event passes the zone filter."""
        if not self.zone_multi:
            return True

        if self.zone_order_enforced:
            return _est_sous_sequence(self.zone_multi, event.zones)

        zones_event = set(event.zones)
        return all(zone in zones_event for zone in self.zone_multi)


def _est_sous_sequence(requises: list[str], disponibles: list[str]) -> bool:
    """Check that `requises` is an ordered subsequence of `disponibles`."""
    it = iter(disponibles)
    return all(zone in it for zone in requises)


class LabelFilter:
    """Filter by labels (detected objects) in the event.

    At least one object in the event must match a configured label.
    Convention: if `labels` is empty, all events are accepted.
    """

    def __init__(self, labels: list[str]) -> None:
        self.labels = labels

    def apply(self, event: FrigateEvent) -> bool:
        """Return True if at least one event object is in the labels list."""
        if not self.labels:
            return True

        labels_autorises = set(self.labels)
        return any(obj in labels_autorises for obj in event.objects)


class TimeFilter:
    """Filter by time range — blocks events during disabled hours.

    Convention: if `disabled_hours` is empty, all events are accepted.
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
        """Return True if the current hour is not a disabled hour."""
        if not self.disabled_hours:
            return True

        heure_courante = self._clock().hour
        return heure_courante not in self.disabled_hours


class SeverityFilter:
    """Filter by Frigate severity — empty list = accept all.

    Convention: if `severities` is empty, all events are accepted.
    """

    def __init__(self, severities: list[str]) -> None:
        self.severities = severities

    def apply(self, event: FrigateEvent) -> bool:
        """Return True if the event severity is in the allowed list."""
        if not self.severities:
            return True
        return event.severity in self.severities


class FilterChain:
    """Chain of filters applied in sequence to each event.

    All filters must accept the event for it to be processed.
    Short-circuit: stops at the first rejection.
    """

    def __init__(self, filters: list[Filter]) -> None:
        self.filters = filters

    def apply(self, event: FrigateEvent) -> bool:
        """Return True if all filters accept the event."""
        return all(f.apply(event) for f in self.filters)
