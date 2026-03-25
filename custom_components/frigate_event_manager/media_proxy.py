"""HA HTTP proxy for Frigate media — protected by HMAC presigned URL."""

from __future__ import annotations

import logging
from html import escape

from aiohttp import web
from homeassistant.components.http import HomeAssistantView
from homeassistant.components.persistent_notification import async_create as pn_create

from .const import PROXY_CLIENT_KEY, SIGNER_DOMAIN_KEY

_LOGGER = logging.getLogger(__name__)

_SECURITY_EVENT = "frigate_em_security_event"
_SECURITY_NOTIF_ID = "fem_invalid_signature"

_ALLOWED_CONTENT_TYPE_PREFIXES = ("image/", "video/", "application/octet-stream")
_FALLBACK_CONTENT_TYPE = "application/octet-stream"


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
            return web.Response(status=503)

        exp_str = request.query.get("exp", "")
        kid_str = request.query.get("kid", "")
        sig = request.query.get("sig", "")
        full_path = f"/{path}"

        if signer.verify(full_path, exp_str, kid_str, sig):
            try:
                content, content_type = await client.get_media(full_path)
            except Exception:
                _LOGGER.exception("Frigate proxy error — path=%s", full_path)
                return web.Response(status=502, text="bad gateway")
            if not any(content_type.startswith(p) for p in _ALLOWED_CONTENT_TYPE_PREFIXES):
                content_type = _FALLBACK_CONTENT_TYPE
            return web.Response(body=content, content_type=content_type)

        # verify() failed — distinguish expired-but-legitimate from forged
        if signer.has_valid_signature(full_path, exp_str, kid_str, sig):
            # Valid HMAC but past expiry — expected, no alert
            _LOGGER.debug("presigned URL expired — path=%s", full_path)
        else:
            remote = request.remote or "unknown"
            safe_path = full_path[:512]
            _LOGGER.warning(
                "presigned URL rejected — invalid signature, path=%s ip=%s",
                safe_path,
                remote,
            )
            hass.bus.async_fire(
                _SECURITY_EVENT,
                {"reason": "invalid_signature", "path": safe_path, "ip": remote},
            )
            pn_create(
                hass,
                message=f"Invalid presigned URL from **{escape(remote)}**: `{escape(safe_path)}`",
                title="Frigate EM — suspicious request",
                notification_id=_SECURITY_NOTIF_ID,
            )

        return web.Response(status=404, text="not found")
