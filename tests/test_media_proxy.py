"""Tests de FrigateMediaProxyView — validation HMAC et proxy Frigate."""

from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock

import pytest
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
    """Construit un faux aiohttp.web.Request."""
    from urllib.parse import parse_qs
    params = parse_qs(url_params)
    request = MagicMock()
    request.app = {"hass": hass}
    request.query = {k: v[0] for k, v in params.items()}
    return request


# ---------------------------------------------------------------------------


async def test_proxy_signature_valide_retourne_media(hass: HomeAssistant) -> None:
    """Une requête avec une signature valide retourne le contenu Frigate."""
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
    """Une signature forgée retourne 401."""
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


async def test_proxy_url_expiree_retourne_401(hass: HomeAssistant) -> None:
    """Une URL expirée retourne 401."""
    signer = _make_signer()
    hass.data[SIGNER_DOMAIN_KEY] = signer
    hass.data[PROXY_CLIENT_KEY] = _make_client()

    exp_passé = str(int(time.time()) - 1)
    view = FrigateMediaProxyView()
    response = await view.get(
        _make_request(hass, f"exp={exp_passé}&sig=whatever"),
        "api/events/abc/snapshot.jpg",
    )
    assert response.status == 401


async def test_proxy_frigate_erreur_retourne_502(hass: HomeAssistant) -> None:
    """Une erreur Frigate retourne 502."""
    signer = _make_signer()
    client = AsyncMock()
    client.get_media.side_effect = Exception("connexion refusée")
    hass.data[SIGNER_DOMAIN_KEY] = signer
    hass.data[PROXY_CLIENT_KEY] = client

    path = "/api/events/abc/snapshot.jpg"
    url = signer.sign_url(path)
    qs = url.split("?")[1]

    view = FrigateMediaProxyView()
    response = await view.get(_make_request(hass, qs), "api/events/abc/snapshot.jpg")
    assert response.status == 502


async def test_proxy_sans_signer_retourne_503(hass: HomeAssistant) -> None:
    """Sans signer dans hass.data, retourne 503."""
    hass.data[PROXY_CLIENT_KEY] = _make_client()
    # SIGNER_DOMAIN_KEY absent

    view = FrigateMediaProxyView()
    response = await view.get(
        _make_request(hass, "exp=9999&sig=x"),
        "api/events/abc/snapshot.jpg",
    )
    assert response.status == 503
