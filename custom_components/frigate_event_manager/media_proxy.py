"""Proxy HTTP HA pour les médias Frigate — protégé par presigned URL HMAC."""

from __future__ import annotations

import logging

from aiohttp import web
from homeassistant.components.http import HomeAssistantView

from .const import PROXY_CLIENT_KEY, SIGNER_DOMAIN_KEY

_LOGGER = logging.getLogger(__name__)


class FrigateMediaProxyView(HomeAssistantView):
    """View HA qui valide une presigned URL HMAC et proxifie vers Frigate.

    Enregistrée une seule fois dans hass.http. Le signer et le client Frigate
    sont lus depuis hass.data à chaque requête pour rester à jour après un reload.
    """

    url = "/api/frigate_em/media/{path:.*}"
    name = "api:frigate_em:media"
    requires_auth = False  # l'auth est assurée par la signature HMAC

    async def get(self, request: web.Request, path: str) -> web.Response:
        """Valide la presigned URL et retourne le média Frigate."""
        hass = request.app["hass"]
        signer = hass.data.get(SIGNER_DOMAIN_KEY)
        client = hass.data.get(PROXY_CLIENT_KEY)

        if signer is None or client is None:
            return web.Response(status=503, text="service unavailable")

        exp_str = request.query.get("exp", "")
        sig = request.query.get("sig", "")
        full_path = f"/{path}"

        if not signer.verify(full_path, exp_str, sig):
            _LOGGER.warning("presigned URL invalide ou expirée — path=%s", full_path)
            return web.Response(status=401, text="unauthorized")

        try:
            content, content_type = await client.get_media(full_path)
        except Exception:
            _LOGGER.exception("erreur proxy Frigate — path=%s", full_path)
            return web.Response(status=502, text="bad gateway")

        return web.Response(body=content, content_type=content_type)
