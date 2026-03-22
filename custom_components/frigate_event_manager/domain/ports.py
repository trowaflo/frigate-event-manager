"""Domain ports — abstract interfaces, zero HA dependency."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol

from .model import FrigateEvent


class NotifierPort(Protocol):
    """Outgoing port — contract that any notification adapter must fulfill."""

    async def async_notify(self, event: FrigateEvent) -> None:
        """Send a notification for a Frigate event."""
        ...


class EventSourcePort(Protocol):
    """Incoming port — MQTT event source to listen to."""

    async def async_subscribe(
        self,
        topic: str,
        callback: Callable[[Any], None],
    ) -> Callable[[], None]:
        """Subscribe to the topic. Returns the unsubscribe function."""
        ...


class FrigatePort(Protocol):
    """Outgoing port — access to the Frigate REST API."""

    async def get_cameras(self) -> list[str]:
        """Return the list of camera names."""
        ...


class MediaSignerPort(Protocol):
    """Port — signing and verification of presigned media URLs."""

    def sign_url(self, path: str) -> str:
        """Sign a path and return the full URL with ?exp=...&sig=..."""
        ...

    def verify(self, path: str, exp_str: str, sig: str) -> bool:
        """Verify that a presigned URL is valid and not expired."""
        ...
