"""Signer HMAC-SHA256 pour presigned URLs médias — aucune dépendance HA."""

from __future__ import annotations

import hashlib
import hmac
import os
import time
from collections.abc import Callable


class MediaSigner:
    """Génère et valide des presigned URLs HMAC-SHA256.

    Payload signé : "{path}\\n{exp}" — identique à l'implémentation Go.
    La clé secrète est générée aléatoirement au démarrage et reste en mémoire.
    """

    def __init__(
        self,
        base_url: str,
        ttl: int = 3600,
        *,
        _now: Callable[[], float] | None = None,
    ) -> None:
        """Initialise avec l'URL de base du proxy et le TTL en secondes."""
        self._base_url = base_url.rstrip("/")
        self._ttl = ttl
        self._key = os.urandom(32)
        self._now: Callable[[], float] = _now or time.time

    def sign_url(self, path: str) -> str:
        """Retourne une URL presignée complète pour le path Frigate donné.

        Ex: sign_url("/api/events/abc/snapshot.jpg")
        → "https://ha.local/api/frigate_em/media/api/events/abc/snapshot.jpg?exp=...&sig=..."
        """
        exp = int(self._now()) + self._ttl
        sig = self._compute_hmac(self._key, path, exp)
        return f"{self._base_url}{path}?exp={exp}&sig={sig}"

    def verify(self, path: str, exp_str: str, sig: str) -> bool:
        """Vérifie la signature et l'expiration d'une URL presignée."""
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
