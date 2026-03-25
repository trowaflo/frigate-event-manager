"""Tests for the HMAC-SHA256 MediaSigner."""

from __future__ import annotations

import time
from urllib.parse import parse_qs, urlparse

from custom_components.frigate_event_manager.domain.signer import MediaSigner


def _make_signer(ttl: int = 3600, now: float | None = None, rotation_period: int = 86400) -> MediaSigner:
    fixed = now or time.time()
    return MediaSigner(
        "https://ha.local/api/frigate_em/media",
        ttl=ttl,
        rotation_period=rotation_period,
        _now=lambda: fixed,
    )


def _parse_url(url: str) -> dict[str, str]:
    return {k: v[0] for k, v in parse_qs(urlparse(url).query).items()}


# ---------------------------------------------------------------------------
# Tests sign_url
# ---------------------------------------------------------------------------


def test_sign_url_contient_exp_kid_et_sig() -> None:
    """Generated URL contains exp, kid and sig parameters."""
    signer = _make_signer()
    url = signer.sign_url("/api/events/abc/snapshot.jpg")
    assert "?exp=" in url
    assert "&kid=" in url
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
    params = _parse_url(url)

    assert signer.verify(
        "/api/events/abc/snapshot.jpg", params["exp"], params["kid"], params["sig"]
    ) is True


def test_verify_url_expiree() -> None:
    """An expired URL is rejected."""
    now = time.time()
    signer = _make_signer(ttl=3600, now=now)
    url = signer.sign_url("/api/events/abc/snapshot.jpg")
    params = _parse_url(url)

    exp_passé = str(int(now) - 1)
    assert signer.verify(
        "/api/events/abc/snapshot.jpg", exp_passé, params["kid"], params["sig"]
    ) is False


def test_verify_signature_falsifiee() -> None:
    """A forged signature is rejected."""
    now = time.time()
    signer = _make_signer(now=now)
    # Ensure key slot exists
    signer.sign_url("/api/events/abc/snapshot.jpg")
    kid = str(signer._kid())
    assert signer.verify(
        "/api/events/abc/snapshot.jpg", str(int(now) + 3600), kid, "fakesig"
    ) is False


def test_verify_exp_invalide() -> None:
    """A non-numeric exp is rejected cleanly."""
    now = time.time()
    signer = _make_signer(now=now)
    signer.sign_url("/api/events/abc/snapshot.jpg")
    kid = str(signer._kid())
    assert signer.verify("/api/events/abc/snapshot.jpg", "notanumber", kid, "sig") is False


def test_verify_kid_invalide() -> None:
    """A non-numeric kid is rejected cleanly."""
    signer = _make_signer()
    assert signer.verify(
        "/api/events/abc/snapshot.jpg", str(int(time.time()) + 3600), "notakid", "sig"
    ) is False


def test_verify_kid_inconnu_rejete() -> None:
    """A valid kid that has no key in memory is rejected."""
    signer = _make_signer()
    # Do not sign anything — _keys is empty
    assert signer.verify(
        "/api/events/abc/snapshot.jpg", str(int(time.time()) + 3600), "9999", "sig"
    ) is False


def test_verify_path_different_rejete() -> None:
    """A valid signature does not apply to a different path."""
    now = time.time()
    signer = _make_signer(now=now)
    url = signer.sign_url("/api/events/abc/snapshot.jpg")
    params = _parse_url(url)

    assert signer.verify(
        "/api/events/abc/clip.mp4", params["exp"], params["kid"], params["sig"]
    ) is False


# ---------------------------------------------------------------------------
# Tests key rotation
# ---------------------------------------------------------------------------


def test_rotation_nouvelle_cle_apres_periode() -> None:
    """After one rotation period, a new kid is generated."""
    now = 1_000_000.0
    rotation = 86400

    signer = MediaSigner(
        "https://ha.local/api/frigate_em/media",
        ttl=3600,
        rotation_period=rotation,
        _now=lambda: now,
    )
    url1 = signer.sign_url("/api/events/a/snapshot.jpg")
    kid1 = _parse_url(url1)["kid"]

    # Advance time by one full rotation period
    signer._now = lambda: now + rotation
    url2 = signer.sign_url("/api/events/b/snapshot.jpg")
    kid2 = _parse_url(url2)["kid"]

    assert kid1 != kid2


def test_rotation_ancienne_cle_toujours_valide_pendant_transition() -> None:
    """URL signed just before rotation is still verifiable just after rotation."""
    # Use a 1-second rotation period and sign just before the boundary (t=0.9)
    rotation = 1
    t_sign = 0.9   # kid = int(0.9 // 1) = 0
    t_verify = 1.5  # kid = int(1.5 // 1) = 1 — new slot, but previous key still in memory

    signer = MediaSigner(
        "https://ha.local/api/frigate_em/media",
        ttl=3600,
        rotation_period=rotation,
        _now=lambda: t_sign,
    )
    url = signer.sign_url("/api/events/abc/snapshot.jpg")
    params = _parse_url(url)

    # Advance to next slot and generate a new key (triggers pruning)
    signer._now = lambda: t_verify
    signer.sign_url("/api/events/xyz/snapshot.jpg")

    # Previous kid (0) should still be in memory (current kid 1, keep k >= 0)
    assert signer.verify(
        "/api/events/abc/snapshot.jpg", params["exp"], params["kid"], params["sig"]
    ) is True


def test_rotation_cle_trop_ancienne_rejetee() -> None:
    """URL signed 2 rotation periods ago is rejected (key pruned)."""
    rotation = 1
    t_sign = 0.5   # kid = 0
    t_verify = 2.5  # kid = 2 — 2 slots later, kid=0 pruned (keep k >= 1)

    signer = MediaSigner(
        "https://ha.local/api/frigate_em/media",
        ttl=3600,  # still valid on expiry side
        rotation_period=rotation,
        _now=lambda: t_sign,
    )
    url = signer.sign_url("/api/events/abc/snapshot.jpg")
    params = _parse_url(url)

    # Advance 2 full rotation periods and generate a new key
    signer._now = lambda: t_verify
    signer.sign_url("/api/events/xyz/snapshot.jpg")  # prunes kid=0

    # kid=0 is now gone from memory
    assert signer.verify(
        "/api/events/abc/snapshot.jpg", params["exp"], params["kid"], params["sig"]
    ) is False


def test_is_expired_exp_invalide_retourne_false() -> None:
    """is_expired returns False when exp_str cannot be parsed as an integer."""
    signer = _make_signer()
    assert signer.is_expired("not_a_number") is False
    assert signer.is_expired("") is False
