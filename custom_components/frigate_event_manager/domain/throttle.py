"""Anti-spam par caméra — Throttler à cooldown configurable.

Sépare la décision (should_notify) de l'enregistrement (record)
pour permettre une utilisation sans effet de bord involontaire.

Utilisation typique :
    if throttler.should_notify(camera):
        await notifier.notify(...)
        throttler.record(camera)
"""

from __future__ import annotations

import time
from collections.abc import Callable


class Throttler:
    """Contrôle l'anti-spam par caméra via un cooldown configurable."""

    def __init__(
        self,
        cooldown: int = 60,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._cooldown = cooldown
        self._clock = clock
        self._last_notified: dict[str, float] = {}

    def should_notify(self, camera: str, now: float | None = None) -> bool:
        """Indique si une notification peut être envoyée pour cette caméra."""
        instant = now if now is not None else self._clock()
        derniere = self._last_notified.get(camera)

        if derniere is None:
            return True

        return (instant - derniere) >= self._cooldown

    def record(self, camera: str, now: float | None = None) -> None:
        """Enregistre le timestamp de la dernière notification pour une caméra."""
        instant = now if now is not None else self._clock()
        self._last_notified[camera] = instant

    def release(self, camera: str) -> None:
        """Supprime le cooldown d'une caméra (event terminé)."""
        self._last_notified.pop(camera, None)
