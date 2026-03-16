"""Client HTTP pour l'API Frigate REST."""

from __future__ import annotations

import aiohttp


class FrigateClient:
    """Client HTTP asyncio pour interroger l'API REST de Frigate."""

    def __init__(self, url: str) -> None:
        """Initialise le client avec l'URL de base de Frigate."""
        self._url = url.rstrip("/")

    async def get_cameras(self) -> list[str]:
        """Retourne la liste des noms de caméras depuis GET {url}/api/cameras.

        Retourne [] si la réponse n'est pas un dict.
        Lève aiohttp.ClientError si la connexion est impossible.
        """
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(f"{self._url}/api/cameras") as response:
                response.raise_for_status()
                data = await response.json()
                if not isinstance(data, dict):
                    return []
                return list(data.keys())
