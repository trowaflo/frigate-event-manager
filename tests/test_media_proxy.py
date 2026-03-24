"""Tests for FrigateMediaProxyView — HMAC validation and Frigate proxy."""

from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock

from homeassistant.core import HomeAssistant

from custom_components.frigate_event_manager.const import PROXY_CLIENT_KEY, SIGNER_DOMAIN_KEY
from custom_components.frigate_event_manager.domain.signer import MediaSigner
from custom_components.frigate_event_manager.media_proxy import FrigateMediaProxyView


def _make_signer(ttl: int = 3600) -> MediaSigner:
    now = time.time()
    return MediaSigner("https://ha.local/api/frigate_em/media", ttl=ttl, _now=lambda: now)


def _make_client(content: bytes = b"imgdata", content_type: str = "image/jpeg") -> AsyncMock:
    client = AsyncMock()
    client.get_media.return_value = (content, content_type)
    return client


def _make_request(hass: HomeAssistant, url_params: str) -> MagicMock:
    """Build a fake aiohttp.web.Request."""
    from urllib.parse import parse_qs
    params = parse_qs(url_params)
    request = MagicMock()
    request.app = {"hass": hass}
    request.query = {k: v[0] for k, v in params.items()}
    return request


# ---------------------------------------------------------------------------


async def test_proxy_signature_valide_retourne_media(hass: HomeAssistant) -> None:
    """A request with a valid signature returns the Frigate content."""
    signer = _make_signer()
    client = _make_client(b"jpeg_content", "image/jpeg")
    hass.data[SIGNER_DOMAIN_KEY] = signer
    hass.data[PROXY_CLIENT_KEY] = client

    path = "/api/events/abc/snapshot.jpg"
    url = signer.sign_url(path)
    qs = url.split("?")[1]

    view = FrigateMediaProxyView()
    response = await view.get(_make_request(hass, qs), "api/events/abc/snapshot.jpg")

    assert response.status == 200
    assert response.body == b"jpeg_content"
    client.get_media.assert_called_once_with(path)


async def test_proxy_signature_invalide_retourne_401(hass: HomeAssistant) -> None:
    """A forged signature returns 401."""
    signer = _make_signer()
    hass.data[SIGNER_DOMAIN_KEY] = signer
    hass.data[PROXY_CLIENT_KEY] = _make_client()

    exp = str(int(time.time()) + 3600)
    view = FrigateMediaProxyView()
    response = await view.get(
        _make_request(hass, f"exp={exp}&sig=fakesig"),
        "api/events/abc/snapshot.jpg",
    )
    assert response.status == 401


async def test_proxy_url_expiree_retourne_302_redirect(hass: HomeAssistant) -> None:
    """An expired URL redirects to the HA root when external_url is set."""
    signer = _make_signer()
    hass.data[SIGNER_DOMAIN_KEY] = signer
    hass.data[PROXY_CLIENT_KEY] = _make_client()
    hass.config.external_url = "https://ha.example.com"

    exp_past = str(int(time.time()) - 1)
    view = FrigateMediaProxyView()
    response = await view.get(
        _make_request(hass, f"exp={exp_past}&sig=whatever"),
        "api/events/abc/snapshot.jpg",
    )
    assert response.status == 302
    assert response.headers["Location"] == "https://ha.example.com"


async def test_proxy_url_expiree_sans_ha_url_retourne_401(hass: HomeAssistant) -> None:
    """An expired URL returns 401 when no HA URL is configured."""
    signer = _make_signer()
    hass.data[SIGNER_DOMAIN_KEY] = signer
    hass.data[PROXY_CLIENT_KEY] = _make_client()
    hass.config.external_url = None
    hass.config.internal_url = None

    exp_past = str(int(time.time()) - 1)
    view = FrigateMediaProxyView()
    response = await view.get(
        _make_request(hass, f"exp={exp_past}&sig=whatever"),
        "api/events/abc/snapshot.jpg",
    )
    assert response.status == 401


async def test_proxy_url_expiree_signature_invalide_retourne_302(hass: HomeAssistant) -> None:
    """Expired URL with invalid signature still redirects — exp is checked before HMAC."""
    signer = _make_signer()
    hass.data[SIGNER_DOMAIN_KEY] = signer
    hass.data[PROXY_CLIENT_KEY] = _make_client()
    hass.config.external_url = "https://ha.example.com"

    exp_past = str(int(time.time()) - 1)
    view = FrigateMediaProxyView()
    response = await view.get(
        _make_request(hass, f"exp={exp_past}&kid=9999&sig=forged"),
        "api/events/abc/snapshot.jpg",
    )
    assert response.status == 302


async def test_proxy_frigate_erreur_retourne_502(hass: HomeAssistant) -> None:
    """A Frigate error returns 502."""
    signer = _make_signer()
    client = AsyncMock()
    client.get_media.side_effect = Exception("connection refused")
    hass.data[SIGNER_DOMAIN_KEY] = signer
    hass.data[PROXY_CLIENT_KEY] = client

    path = "/api/events/abc/snapshot.jpg"
    url = signer.sign_url(path)
    qs = url.split("?")[1]

    view = FrigateMediaProxyView()
    response = await view.get(_make_request(hass, qs), "api/events/abc/snapshot.jpg")
    assert response.status == 502


async def test_proxy_sans_signer_retourne_503(hass: HomeAssistant) -> None:
    """Without a signer in hass.data, returns 503."""
    hass.data[PROXY_CLIENT_KEY] = _make_client()
    # SIGNER_DOMAIN_KEY absent

    view = FrigateMediaProxyView()
    response = await view.get(
        _make_request(hass, "exp=9999&sig=x"),
        "api/events/abc/snapshot.jpg",
    )
    assert response.status == 503
