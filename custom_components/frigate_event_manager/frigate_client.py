"""Client HTTP pour l'API Frigate REST."""

from __future__ import annotations

import aiohttp

from .domain.ports import FrigatePort


class FrigateClient(FrigatePort):
    """Client HTTP asyncio pour interroger l'API REST de Frigate."""

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

    async def get_camera_config(self, camera: str) -> dict:
        """Retourne les zones et labels configurés pour une caméra.

        Appelle GET {url}/api/config et extrait :
        - zones : list(data["cameras"][camera]["zones"].keys())
        - labels : data["cameras"][camera].get("objects", {}).get("track", [])

        Retourne {"zones": [], "labels": []} si la caméra est absente.
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
                    return {"zones": [], "labels": []}
                cam_data = data.get("cameras", {}).get(camera, None)
                if cam_data is None:
                    return {"zones": [], "labels": []}
                zones = list(cam_data.get("zones", {}).keys())
                labels = cam_data.get("objects", {}).get("track", [])
                return {"zones": zones, "labels": labels}

    async def get_media(self, path: str) -> tuple[bytes, str]:
        """Récupère un média Frigate (image, clip, preview) avec auth.

        Retourne (contenu_brut, content_type).
        Lève aiohttp.ClientError si la connexion échoue.
        """
        timeout = aiohttp.ClientTimeout(total=30)
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

            url = f"{self._url.rstrip('/')}{path}"
            async with session.get(url, headers=headers) as resp:
                resp.raise_for_status()
                content_type = resp.headers.get("Content-Type", "application/octet-stream")
                return await resp.read(), content_type
