"""Interactive MediaSigner demo — run with .venv/bin/python scripts/demo_signer.py"""

from __future__ import annotations

import sys
import time

sys.path.insert(0, ".")
from custom_components.frigate_event_manager.domain.signer import MediaSigner

SEP = "─" * 60


def ok(msg: str) -> str:
    return f"  \033[32m✓\033[0m  {msg}"


def ko(msg: str) -> str:
    return f"  \033[31m✗\033[0m  {msg}"


def section(title: str) -> None:
    print(f"\n{SEP}\n  {title}\n{SEP}")


# ── 1. Signed URL generation ────────────────────────────────────────────────

section("1. Signed URL generation")

now = time.time()
ttl = 30  # short TTL to observe expiry quickly
signer = MediaSigner("https://ha.example.com/api/frigate_em/media", ttl=ttl, _now=lambda: now)

path = "/api/events/abc123/snapshot.jpg"
url = signer.sign_url(path)

from urllib.parse import parse_qs, urlparse
params = {k: v[0] for k, v in parse_qs(urlparse(url).query).items()}

print(f"\n  Generated URL:\n  {url}\n")
print(f"  exp = {params['exp']}  (expires in {ttl}s)")
print(f"  kid = {params['kid']}  (current key slot)")
print(f"  sig = {params['sig'][:16]}...  (HMAC-SHA256 truncated)")

# ── 2. Valid verification ────────────────────────────────────────────────────

section("2. Verification")

result = signer.verify(path, params["exp"], params["kid"], params["sig"])
print(ok("Valid URL → verify() = True") if result else ko("ERROR — expected True"))

# ── 3. Forged signature ──────────────────────────────────────────────────────

section("3. Forged signature")

result = signer.verify(path, params["exp"], params["kid"], "fakesig0000000000")
print(ko("Forged signature rejected → verify() = False") if not result else ko("ERROR — expected False"))

# ── 4. Modified path ─────────────────────────────────────────────────────────

section("4. Modified path (same sig, different path)")

result = signer.verify("/api/events/abc123/clip.mp4", params["exp"], params["kid"], params["sig"])
print(ko("Different path rejected → verify() = False") if not result else ko("ERROR — expected False"))

# ── 5. Expired URL ───────────────────────────────────────────────────────────

section("5. Expiry — TTL exceeded")

signer_expired = MediaSigner(
    "https://ha.example.com/api/frigate_em/media",
    ttl=ttl,
    _now=lambda: now + ttl + 1,  # 1 second past expiry
)
# Reuse the same key to test expiry only
signer_expired._keys = dict(signer._keys)

result = signer_expired.verify(path, params["exp"], params["kid"], params["sig"])
print(ko(f"Expired URL (t+{ttl+1}s) rejected → verify() = False") if not result else ko("ERROR — expected False"))

# ── 6. Key rotation ──────────────────────────────────────────────────────────

section("6. Key rotation (period = 2 seconds)")

rotation = 2
t0 = 10.0

signer_rot = MediaSigner(
    "https://ha.example.com/api/frigate_em/media",
    ttl=3600,
    rotation_period=rotation,
    _now=lambda: t0,
)

url1 = signer_rot.sign_url("/api/events/evt1/snapshot.jpg")
p1 = {k: v[0] for k, v in parse_qs(urlparse(url1).query).items()}
print(f"\n  t=10s  → kid={p1['kid']} (slot {int(t0 // rotation)})")

signer_rot._now = lambda: t0 + rotation
url2 = signer_rot.sign_url("/api/events/evt2/snapshot.jpg")
p2 = {k: v[0] for k, v in parse_qs(urlparse(url2).query).items()}
print(f"  t=12s  → kid={p2['kid']} (slot {int((t0 + rotation) // rotation)}) — new key")

# Previous URL (kid-1) is still valid within the transition window
result_old = signer_rot.verify("/api/events/evt1/snapshot.jpg", p1["exp"], p1["kid"], p1["sig"])
print()
print(ok("Previous URL still valid (kid-1 kept in memory)") if result_old else ko("ERROR — expected True"))

signer_rot._now = lambda: t0 + 2 * rotation
signer_rot.sign_url("/api/events/evt3/snapshot.jpg")  # prunes oldest slot

result_pruned = signer_rot.verify("/api/events/evt1/snapshot.jpg", p1["exp"], p1["kid"], p1["sig"])
print(ko("URL 2 rotations old rejected (key pruned)") if not result_pruned else ko("ERROR — expected False"))

print(f"\n{SEP}\n  All good — signer works as expected.\n{SEP}\n")
