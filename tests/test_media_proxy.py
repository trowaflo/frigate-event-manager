"""Tests for FrigateMediaProxyView — HMAC validation and Frigate proxy."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

from custom_components.frigate_event_manager.const import (
    PROXY_CLIENT_KEY,
    SECURITY_EVENT,
    SECURITY_NOTIF_ID,
    SIGNER_DOMAIN_KEY,
)
from custom_components.frigate_event_manager.domain.signer import MediaSigner
from custom_components.frigate_event_manager.media_proxy import FrigateMediaProxyView


def _make_signer(ttl: int = 3600) -> MediaSigner:
    now = time.time()
    return MediaSigner("https://ha.local/api/frigate_em/media", ttl=ttl, _now=lambda: now)


def _make_client(content: bytes = b"imgdata", content_type: str = "image/jpeg") -> AsyncMock:
    client = AsyncMock()
    client.get_media.return_value = (content, content_type)
    return client


def _make_request(hass: HomeAssistant, url_params: str, remote: str = "127.0.0.1") -> MagicMock:
    """Build a fake aiohttp.web.Request."""
    from urllib.parse import parse_qs
    params = parse_qs(url_params)
    request = MagicMock()
    request.app = {"hass": hass}
    request.query = {k: v[0] for k, v in params.items()}
    request.remote = remote
    return request


# ---------------------------------------------------------------------------
# Happy path
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


# ---------------------------------------------------------------------------
# Invalid / forged URL → 404 + security event + persistent notification
# ---------------------------------------------------------------------------


async def test_proxy_signature_invalide_retourne_404(hass: HomeAssistant) -> None:
    """A forged signature returns 404, fires a security event, and creates a notification."""
    signer = _make_signer()
    hass.data[SIGNER_DOMAIN_KEY] = signer
    hass.data[PROXY_CLIENT_KEY] = _make_client()

    events: list = []

    async def _collect(event):  # noqa: ANN001
        events.append(event)

    hass.bus.async_listen(SECURITY_EVENT, _collect)

    exp = str(int(time.time()) + 3600)
    view = FrigateMediaProxyView()

    with patch("custom_components.frigate_event_manager.media_proxy.pn_create") as mock_pn:
        response = await view.get(
            _make_request(hass, f"exp={exp}&kid=0&sig=fakesig", remote="10.0.0.1"),
            "api/events/abc/snapshot.jpg",
        )
    await hass.async_block_till_done()

    assert response.status == 404
    assert len(events) == 1
    assert events[0].data == {
        "reason": "invalid_signature",
        "path": "/api/events/abc/snapshot.jpg",
        "ip": "10.0.0.1",
    }
    mock_pn.assert_called_once()
    _, kwargs = mock_pn.call_args
    assert kwargs["notification_id"] == SECURITY_NOTIF_ID
    assert "10.0.0.1" in kwargs["message"]


async def test_proxy_signature_invalide_sans_ip_retourne_404(hass: HomeAssistant) -> None:
    """A forged request without a remote IP uses 'unknown' in the security event."""
    signer = _make_signer()
    hass.data[SIGNER_DOMAIN_KEY] = signer
    hass.data[PROXY_CLIENT_KEY] = _make_client()

    events: list = []

    async def _collect(event):  # noqa: ANN001
        events.append(event)

    hass.bus.async_listen(SECURITY_EVENT, _collect)

    exp = str(int(time.time()) + 3600)
    view = FrigateMediaProxyView()

    with patch("custom_components.frigate_event_manager.media_proxy.pn_create"):
        request = _make_request(hass, f"exp={exp}&kid=0&sig=fakesig")
        request.remote = None
        response = await view.get(request, "api/events/abc/snapshot.jpg")
    await hass.async_block_till_done()

    assert response.status == 404
    assert events[0].data["ip"] == "unknown"


# ---------------------------------------------------------------------------
# Expired URL → 404, no security event
# ---------------------------------------------------------------------------


async def test_proxy_url_expiree_retourne_404(hass: HomeAssistant) -> None:
    """An expired URL with a valid signature returns 404 without firing a security event."""
    # Build a signer with a mutable time reference so we can sign in the past.
    t = [time.time()]
    signer = MediaSigner(
        "https://ha.local/api/frigate_em/media", ttl=3600, _now=lambda: t[0]
    )
    hass.data[SIGNER_DOMAIN_KEY] = signer
    hass.data[PROXY_CLIENT_KEY] = _make_client()

    # Sign a URL 2 h ago → exp = t[0] - 3600, already expired at current time.
    path = "/api/events/abc/snapshot.jpg"
    t[0] -= 7200
    url = signer.sign_url(path)
    qs = url.split("?")[1]
    t[0] += 7200  # restore to "now"

    events: list = []

    async def _collect(event):  # noqa: ANN001
        events.append(event)

    hass.bus.async_listen(SECURITY_EVENT, _collect)

    view = FrigateMediaProxyView()

    with patch("custom_components.frigate_event_manager.media_proxy.pn_create") as mock_pn:
        response = await view.get(_make_request(hass, qs), "api/events/abc/snapshot.jpg")
    await hass.async_block_till_done()

    assert response.status == 404
    assert events == []
    mock_pn.assert_not_called()


async def test_proxy_url_expiree_et_forgee_retourne_404_avec_event(
    hass: HomeAssistant,
) -> None:
    """An expired URL with an *invalid* signature fires a security event (forged request)."""
    signer = _make_signer()
    hass.data[SIGNER_DOMAIN_KEY] = signer
    hass.data[PROXY_CLIENT_KEY] = _make_client()

    events: list = []

    async def _collect(event):  # noqa: ANN001
        events.append(event)

    hass.bus.async_listen(SECURITY_EVENT, _collect)

    exp_past = str(int(time.time()) - 1)
    view = FrigateMediaProxyView()

    with patch("custom_components.frigate_event_manager.media_proxy.pn_create") as mock_pn:
        response = await view.get(
            _make_request(hass, f"exp={exp_past}&kid=0&sig=forgedsig", remote="10.0.0.2"),
            "api/events/abc/snapshot.jpg",
        )
    await hass.async_block_till_done()

    assert response.status == 404
    assert len(events) == 1
    assert events[0].data["reason"] == "invalid_signature"
    assert events[0].data["ip"] == "10.0.0.2"
    assert events[0].data["path"] == "/api/events/abc/snapshot.jpg"
    mock_pn.assert_called_once()


# ---------------------------------------------------------------------------
# Infrastructure errors
# ---------------------------------------------------------------------------


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

    view = FrigateMediaProxyView()
    response = await view.get(
        _make_request(hass, "exp=9999&sig=x"),
        "api/events/abc/snapshot.jpg",
    )
    assert response.status == 503
