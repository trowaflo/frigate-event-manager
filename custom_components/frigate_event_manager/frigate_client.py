"""HTTP client for the Frigate REST API."""

from __future__ import annotations

import aiohttp

from .domain.ports import FrigatePort


class FrigateClient(FrigatePort):
    """Asyncio HTTP client for querying the Frigate REST API."""

    def __init__(
        self,
        url: str,
        username: str | None = None,
        password: str | None = None,
    ) -> None:
        """Initialize the client with the URL and optional credentials."""
        self._url = url.rstrip("/")
        self._username = username or None
        self._password = password or ""

    async def _get_auth_headers(self, session: aiohttp.ClientSession) -> dict[str, str]:
        """Authenticate the Frigate session and return JWT headers if credentials provided."""
        headers: dict[str, str] = {}
        if self._username:
            async with session.post(
                f"{self._url}/api/login",
                json={"user": self._username, "password": self._password},
            ) as resp:
                resp.raise_for_status()
                token_cookie = resp.cookies.get("frigate_token")
                if token_cookie:
                    headers["Cookie"] = f"frigate_token={token_cookie.value}"
        return headers

    async def _fetch_frigate_config(self) -> dict:
        """Fetch the full JSON from GET {url}/api/config with auth.

        Raises aiohttp.ClientError if the connection fails.
        """
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            headers = await self._get_auth_headers(session)
            async with session.get(
                f"{self._url}/api/config", headers=headers
            ) as response:
                response.raise_for_status()
                data = await response.json()
                return data if isinstance(data, dict) else {}

    async def get_cameras(self) -> list[str]:
        """Return the list of camera names from GET {url}/api/config.

        Returns [] if no cameras are found.
        Raises aiohttp.ClientError if the connection fails.
        """
        data = await self._fetch_frigate_config()
        return list(data.get("cameras", {}).keys())

    async def get_camera_config(self, camera: str) -> dict:
        """Return the zones and labels configured for a camera from GET {url}/api/config.

        Returns {"zones": [], "labels": []} if the camera is absent.
        Raises aiohttp.ClientError if the connection fails.
        """
        data = await self._fetch_frigate_config()
        cam_data = data.get("cameras", {}).get(camera)
        if cam_data is None:
            return {"zones": [], "labels": []}
        zones = list(cam_data.get("zones", {}).keys())
        labels = cam_data.get("objects", {}).get("track", [])
        return {"zones": zones, "labels": labels}

    async def get_media(self, path: str) -> tuple[bytes, str]:
        """Fetch a Frigate media file (image, clip, preview) with auth.

        Returns (raw_content, content_type).
        Raises aiohttp.ClientError if the connection fails.
        """
        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            headers = await self._get_auth_headers(session)
            url = f"{self._url.rstrip('/')}{path}"
            async with session.get(url, headers=headers) as resp:
                resp.raise_for_status()
                content_type = resp.headers.get("Content-Type", "application/octet-stream")
                return await resp.read(), content_type
