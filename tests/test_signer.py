"""Tests for the HMAC-SHA256 MediaSigner."""

from __future__ import annotations

import time


from custom_components.frigate_event_manager.domain.signer import MediaSigner


def _make_signer(ttl: int = 3600, now: float | None = None) -> MediaSigner:
    fixed = now or time.time()
    return MediaSigner("https://ha.local/api/frigate_em/media", ttl=ttl, _now=lambda: fixed)


# ---------------------------------------------------------------------------
# Tests sign_url
# ---------------------------------------------------------------------------


def test_sign_url_contient_exp_et_sig() -> None:
    """Generated URL contains exp and sig parameters."""
    signer = _make_signer()
    url = signer.sign_url("/api/events/abc/snapshot.jpg")
    assert "?exp=" in url
    assert "&sig=" in url


def test_sign_url_contient_le_path() -> None:
    """URL contains the signed Frigate path."""
    signer = _make_signer()
    url = signer.sign_url("/api/review/xyz/preview")
    assert "/api/review/xyz/preview" in url


def test_sign_url_base_url_correcte() -> None:
    """URL starts with the proxy base URL."""
    signer = _make_signer()
    url = signer.sign_url("/api/events/abc/clip.mp4")
    assert url.startswith("https://ha.local/api/frigate_em/media/api/events/abc/clip.mp4")


# ---------------------------------------------------------------------------
# Tests verify
# ---------------------------------------------------------------------------


def test_verify_url_valide() -> None:
    """A signed URL is successfully verified."""
    now = time.time()
    signer = _make_signer(ttl=3600, now=now)
    url = signer.sign_url("/api/events/abc/snapshot.jpg")

    from urllib.parse import parse_qs, urlparse
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    exp_str = params["exp"][0]
    sig = params["sig"][0]

    assert signer.verify("/api/events/abc/snapshot.jpg", exp_str, sig) is True


def test_verify_url_expiree() -> None:
    """An expired URL is rejected."""
    now = time.time()
    signer = _make_signer(ttl=3600, now=now)
    url = signer.sign_url("/api/events/abc/snapshot.jpg")

    from urllib.parse import parse_qs, urlparse
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    sig = params["sig"][0]

    # Forge a URL with exp in the past
    exp_passé = str(int(now) - 1)
    assert signer.verify("/api/events/abc/snapshot.jpg", exp_passé, sig) is False


def test_verify_signature_falsifiee() -> None:
    """A forged signature is rejected."""
    signer = _make_signer()
    assert signer.verify("/api/events/abc/snapshot.jpg", str(int(time.time()) + 3600), "fakesig") is False


def test_verify_exp_invalide() -> None:
    """A non-numeric exp is rejected cleanly."""
    signer = _make_signer()
    assert signer.verify("/api/events/abc/snapshot.jpg", "notanumber", "sig") is False


def test_verify_path_different_rejete() -> None:
    """A valid signature does not apply to a different path."""
    now = time.time()
    signer = _make_signer(now=now)
    url = signer.sign_url("/api/events/abc/snapshot.jpg")

    from urllib.parse import parse_qs, urlparse
    params = parse_qs(urlparse(url).query)
    exp_str = params["exp"][0]
    sig = params["sig"][0]

    # Same exp and sig but different path
    assert signer.verify("/api/events/abc/clip.mp4", exp_str, sig) is False
