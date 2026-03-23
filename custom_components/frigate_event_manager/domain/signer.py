"""HMAC-SHA256 signer for presigned media URLs — no HA dependency."""

from __future__ import annotations

import hashlib
import hmac
import os
import time
from collections.abc import Callable


class MediaSigner:
    """Generate and validate HMAC-SHA256 presigned URLs with time-based key rotation.

    A new signing key is generated once per rotation slot (default: 86400s = 24h).
    The slot ID (kid) is included in the URL so the verifier knows which key to use.
    At most 2 keys are kept in memory (current + previous) to handle URLs signed
    just before a rotation boundary.

    Signed payload: "{path}\\n{exp}\\n{kid}"
    """

    def __init__(
        self,
        base_url: str,
        ttl: int = 3600,
        rotation_period: int = 86400,
        *,
        _now: Callable[[], float] | None = None,
    ) -> None:
        """Initialize with the proxy base URL, TTL and rotation period in seconds."""
        self._base_url = base_url.rstrip("/")
        self._ttl = ttl
        self._rotation_period = rotation_period
        self._keys: dict[int, bytes] = {}
        self._now: Callable[[], float] = _now or time.time

    def _kid(self) -> int:
        """Return the current key slot ID."""
        return int(self._now() // self._rotation_period)

    def _ensure_key(self, kid: int) -> bytes:
        """Return the key for the given slot, generating it if needed.

        Prunes slots older than current - 1 to bound memory to 2 keys.
        """
        if kid not in self._keys:
            self._keys[kid] = os.urandom(32)
        self._keys = {k: v for k, v in self._keys.items() if k >= kid - 1}
        return self._keys[kid]

    def _get_key(self, kid: int) -> bytes | None:
        """Return the key for the given slot, or None if not in memory."""
        return self._keys.get(kid)

    def sign_url(self, path: str) -> str:
        """Return a presigned full URL for the given Frigate path.

        Ex: sign_url("/api/events/abc/snapshot.jpg")
        → "https://ha.local/api/frigate_em/media/api/events/abc/snapshot.jpg?exp=...&kid=...&sig=..."
        """
        kid = self._kid()
        key = self._ensure_key(kid)
        exp = int(self._now()) + self._ttl
        sig = self._compute_hmac(key, path, exp, kid)
        return f"{self._base_url}{path}?exp={exp}&kid={kid}&sig={sig}"

    def verify(self, path: str, exp_str: str, kid_str: str, sig: str) -> bool:
        """Verify the signature, expiration and key slot of a presigned URL."""
        try:
            exp = int(exp_str)
            kid = int(kid_str)
        except (ValueError, TypeError):
            return False

        if self._now() > exp:
            return False

        key = self._get_key(kid)
        if key is None:
            return False

        expected = self._compute_hmac(key, path, exp, kid)
        return hmac.compare_digest(sig, expected)

    @staticmethod
    def _compute_hmac(key: bytes, path: str, exp: int, kid: int) -> str:
        payload = f"{path}\n{exp}\n{kid}".encode()
        return hmac.new(key, payload, hashlib.sha256).hexdigest()
