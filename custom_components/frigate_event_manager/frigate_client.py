"""Client HTTP pour l'API Frigate REST."""

from __future__ import annotations

import aiohttp


class FrigateClient:
    """Client HTTP asyncio pour interroger l'API REST de Frigate. Satisfait FrigatePort."""

    def __init__(
        self,
        url: str,
        username: str | None = None,
        password: str | None = None,
    ) -> None:
        """Initialise le client avec l'URL et les credentials optionnels."""
        self._url = url.rstrip("/")
        self._username = username or None
        self._password = password or ""

    async def get_cameras(self) -> list[str]:
        """Retourne la liste des noms de caméras depuis GET {url}/api/config.

        Si des credentials sont fournis, effectue un POST /api/login (Frigate 0.14+)
        pour obtenir un token JWT, puis l'envoie en cookie sur les requêtes suivantes.
        Retourne [] si aucune caméra n'est trouvée.
        Lève aiohttp.ClientError si la connexion est impossible.
        """
        timeout = aiohttp.ClientTimeout(total=10)
        headers: dict[str, str] = {}

        async with aiohttp.ClientSession(timeout=timeout) as session:
            if self._username:
                async with session.post(
                    f"{self._url}/api/login",
                    json={"user": self._username, "password": self._password},
                ) as resp:
                    resp.raise_for_status()
                    token_cookie = resp.cookies.get("frigate_token")
                    if token_cookie:
                        headers["Cookie"] = f"frigate_token={token_cookie.value}"

            async with session.get(
                f"{self._url}/api/config", headers=headers
            ) as response:
                response.raise_for_status()
                data = await response.json()
                if not isinstance(data, dict):
                    return []
                return list(data.get("cameras", {}).keys())
