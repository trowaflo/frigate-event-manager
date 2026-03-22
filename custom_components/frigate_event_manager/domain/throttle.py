"""Per-camera anti-spam — Throttler with configurable cooldown.

Separates the decision (should_notify) from the recording (record)
to allow usage without unintended side effects.

Typical usage:
    if throttler.should_notify(camera):
        await notifier.notify(...)
        throttler.record(camera)
"""

from __future__ import annotations

import time
from collections.abc import Callable


class Throttler:
    """Controls per-camera anti-spam via a configurable cooldown."""

    def __init__(
        self,
        cooldown: int = 60,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._cooldown = cooldown
        self._clock = clock
        self._last_notified: dict[str, float] = {}

    def should_notify(self, camera: str, now: float | None = None) -> bool:
        """Indicate whether a notification can be sent for this camera."""
        instant = now if now is not None else self._clock()
        derniere = self._last_notified.get(camera)

        if derniere is None:
            return True

        return (instant - derniere) >= self._cooldown

    def record(self, camera: str, now: float | None = None) -> None:
        """Record the timestamp of the last notification for a camera."""
        instant = now if now is not None else self._clock()
        self._last_notified[camera] = instant

    def release(self, camera: str) -> None:
        """Remove the cooldown for a camera (event ended)."""
        self._last_notified.pop(camera, None)
