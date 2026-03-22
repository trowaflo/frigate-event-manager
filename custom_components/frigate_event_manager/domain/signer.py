"""HMAC-SHA256 signer for presigned media URLs — no HA dependency."""

from __future__ import annotations

import hashlib
import hmac
import os
import time
from collections.abc import Callable


class MediaSigner:
    """Generate and validate HMAC-SHA256 presigned URLs.

    Signed payload: "{path}\\n{exp}" — identical to the Go implementation.
    The secret key is generated randomly at startup and kept in memory.
    """

    def __init__(
        self,
        base_url: str,
        ttl: int = 3600,
        *,
        _now: Callable[[], float] | None = None,
    ) -> None:
        """Initialize with the proxy base URL and TTL in seconds."""
        self._base_url = base_url.rstrip("/")
        self._ttl = ttl
        self._key = os.urandom(32)
        self._now: Callable[[], float] = _now or time.time

    def sign_url(self, path: str) -> str:
        """Return a presigned full URL for the given Frigate path.

        Ex: sign_url("/api/events/abc/snapshot.jpg")
        → "https://ha.local/api/frigate_em/media/api/events/abc/snapshot.jpg?exp=...&sig=..."
        """
        exp = int(self._now()) + self._ttl
        sig = self._compute_hmac(self._key, path, exp)
        return f"{self._base_url}{path}?exp={exp}&sig={sig}"

    def verify(self, path: str, exp_str: str, sig: str) -> bool:
        """Verify the signature and expiration of a presigned URL."""
        try:
            exp = int(exp_str)
        except (ValueError, TypeError):
            return False

        if self._now() > exp:
            return False

        expected = self._compute_hmac(self._key, path, exp)
        return hmac.compare_digest(sig, expected)

    @staticmethod
    def _compute_hmac(key: bytes, path: str, exp: int) -> str:
        payload = f"{path}\n{exp}".encode()
        return hmac.new(key, payload, hashlib.sha256).hexdigest()
