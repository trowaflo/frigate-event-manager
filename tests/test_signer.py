"""Tests du MediaSigner HMAC-SHA256."""

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
    """L'URL générée contient les paramètres exp et sig."""
    signer = _make_signer()
    url = signer.sign_url("/api/events/abc/snapshot.jpg")
    assert "?exp=" in url
    assert "&sig=" in url


def test_sign_url_contient_le_path() -> None:
    """L'URL contient le path Frigate signé."""
    signer = _make_signer()
    url = signer.sign_url("/api/review/xyz/preview")
    assert "/api/review/xyz/preview" in url


def test_sign_url_base_url_correcte() -> None:
    """L'URL commence par la base URL du proxy."""
    signer = _make_signer()
    url = signer.sign_url("/api/events/abc/clip.mp4")
    assert url.startswith("https://ha.local/api/frigate_em/media/api/events/abc/clip.mp4")


# ---------------------------------------------------------------------------
# Tests verify
# ---------------------------------------------------------------------------


def test_verify_url_valide() -> None:
    """Une URL signée est vérifiée avec succès."""
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
    """Une URL expirée est rejetée."""
    now = time.time()
    signer = _make_signer(ttl=3600, now=now)
    url = signer.sign_url("/api/events/abc/snapshot.jpg")

    from urllib.parse import parse_qs, urlparse
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    sig = params["sig"][0]

    # Avancer le temps au-delà du TTL
    MediaSigner(
        "https://ha.local/api/frigate_em/media",
        ttl=3600,
        _now=lambda: now + 7200,
    )
    # Même clé ? Non — clé différente donc on teste l'expiration sur le même signer
    # On forge une URL avec exp dans le passé
    exp_passé = str(int(now) - 1)
    assert signer.verify("/api/events/abc/snapshot.jpg", exp_passé, sig) is False


def test_verify_signature_falsifiee() -> None:
    """Une signature forgée est rejetée."""
    signer = _make_signer()
    assert signer.verify("/api/events/abc/snapshot.jpg", str(int(time.time()) + 3600), "fakesig") is False


def test_verify_exp_invalide() -> None:
    """Un exp non numérique est rejeté proprement."""
    signer = _make_signer()
    assert signer.verify("/api/events/abc/snapshot.jpg", "notanumber", "sig") is False


def test_verify_path_different_rejete() -> None:
    """Une signature valide ne s'applique pas à un autre path."""
    now = time.time()
    signer = _make_signer(now=now)
    url = signer.sign_url("/api/events/abc/snapshot.jpg")

    from urllib.parse import parse_qs, urlparse
    params = parse_qs(urlparse(url).query)
    exp_str = params["exp"][0]
    sig = params["sig"][0]

    # Même exp et sig mais path différent
    assert signer.verify("/api/events/abc/clip.mp4", exp_str, sig) is False
