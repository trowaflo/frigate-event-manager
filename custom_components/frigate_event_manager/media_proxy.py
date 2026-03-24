"""HA HTTP proxy for Frigate media — protected by HMAC presigned URL."""

from __future__ import annotations

import logging

from aiohttp import web
from homeassistant.components.http import HomeAssistantView

from .const import PROXY_CLIENT_KEY, SIGNER_DOMAIN_KEY

_LOGGER = logging.getLogger(__name__)


class FrigateMediaProxyView(HomeAssistantView):
    """HA view that validates an HMAC presigned URL and proxies to Frigate.

    Registered once in hass.http. The signer and Frigate client are
    read from hass.data on each request to stay current after a reload.
    """

    url = "/api/frigate_em/media/{path:.*}"
    name = "api:frigate_em:media"
    requires_auth = False  # auth is handled by the HMAC signature

    async def get(self, request: web.Request, path: str) -> web.Response:
        """Validate the presigned URL and return the Frigate media."""
        hass = request.app["hass"]
        signer = hass.data.get(SIGNER_DOMAIN_KEY)
        client = hass.data.get(PROXY_CLIENT_KEY)

        if signer is None or client is None:
            return web.Response(status=503, text="service unavailable")

        exp_str = request.query.get("exp", "")
        kid_str = request.query.get("kid", "")
        sig = request.query.get("sig", "")
        full_path = f"/{path}"

        # Expiry is checked before signature: any URL past its exp is redirected
        # to HA root regardless of signature validity. This maximises UX (the user
        # can re-authenticate) without weakening security — an attacker with a
        # forged but expired URL is harmlessly sent to the HA login page.
        if signer.is_expired(exp_str):
            ha_url = hass.config.external_url or hass.config.internal_url
            if ha_url:
                _LOGGER.debug("expired presigned URL — redirecting to HA root, path=%s", full_path)
                return web.HTTPFound(location=ha_url)
            return web.Response(status=401, text="unauthorized")

        if not signer.verify(full_path, exp_str, kid_str, sig):
            _LOGGER.warning("invalid presigned URL — path=%s", full_path)
            return web.Response(status=401, text="unauthorized")

        try:
            content, content_type = await client.get_media(full_path)
        except Exception:
            _LOGGER.exception("Frigate proxy error — path=%s", full_path)
            return web.Response(status=502, text="bad gateway")

        return web.Response(body=content, content_type=content_type)
