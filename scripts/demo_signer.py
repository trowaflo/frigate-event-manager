"""Demo interactif du MediaSigner — lancer avec .venv/bin/python scripts/demo_signer.py"""

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


# ── 1. Génération d'une URL signée ─────────────────────────────────────────

section("1. Génération d'une URL signée")

now = time.time()
ttl = 30  # 30 secondes pour voir l'expiration rapidement
signer = MediaSigner("https://ha.example.com/api/frigate_em/media", ttl=ttl, _now=lambda: now)

path = "/api/events/abc123/snapshot.jpg"
url = signer.sign_url(path)

from urllib.parse import parse_qs, urlparse
params = {k: v[0] for k, v in parse_qs(urlparse(url).query).items()}

print(f"\n  URL générée :\n  {url}\n")
print(f"  exp = {params['exp']}  (expire dans {ttl}s)")
print(f"  kid = {params['kid']}  (slot de clé actuel)")
print(f"  sig = {params['sig'][:16]}...  (HMAC-SHA256 tronqué)")

# ── 2. Vérification valide ─────────────────────────────────────────────────

section("2. Vérification")

result = signer.verify(path, params["exp"], params["kid"], params["sig"])
print(ok("URL valide → verify() = True") if result else ko("ERREUR — devrait être True"))

# ── 3. Signature falsifiée ─────────────────────────────────────────────────

section("3. Signature falsifiée")

result = signer.verify(path, params["exp"], params["kid"], "fakesig0000000000")
print(ko("Fausse signature rejetée → verify() = False") if not result else ko("ERREUR — devrait être False"))

# ── 4. Path modifié ───────────────────────────────────────────────────────

section("4. Path modifié (même sig, autre path)")

result = signer.verify("/api/events/abc123/clip.mp4", params["exp"], params["kid"], params["sig"])
print(ko("Path différent rejeté → verify() = False") if not result else ko("ERREUR — devrait être False"))

# ── 5. URL expirée ────────────────────────────────────────────────────────

section("5. Expiration — TTL dépassé")

signer_expired = MediaSigner(
    "https://ha.example.com/api/frigate_em/media",
    ttl=ttl,
    _now=lambda: now + ttl + 1,  # 1 seconde après expiration
)
# On réutilise la même clé pour tester uniquement l'expiration
signer_expired._keys = dict(signer._keys)

result = signer_expired.verify(path, params["exp"], params["kid"], params["sig"])
print(ko(f"URL expirée (t+{ttl+1}s) rejetée → verify() = False") if not result else ko("ERREUR — devrait être False"))

# ── 6. Rotation de clé ────────────────────────────────────────────────────

section("6. Rotation de clé (période = 2 secondes)")

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
print(f"  t=12s  → kid={p2['kid']} (slot {int((t0 + rotation) // rotation)}) — nouvelle clé")

# L'ancienne URL (kid précédent) est toujours valide (fenêtre de transition)
result_old = signer_rot.verify("/api/events/evt1/snapshot.jpg", p1["exp"], p1["kid"], p1["sig"])
print()
print(ok("Ancienne URL encore valide (kid-1 conservé en mémoire)") if result_old else ko("ERREUR — devrait être True"))

signer_rot._now = lambda: t0 + 2 * rotation
signer_rot.sign_url("/api/events/evt3/snapshot.jpg")  # prune kid trop vieux

result_pruned = signer_rot.verify("/api/events/evt1/snapshot.jpg", p1["exp"], p1["kid"], p1["sig"])
print(ko("URL 2 rotations en arrière rejetée (clé purgée)") if not result_pruned else ko("ERREUR — devrait être False"))

print(f"\n{SEP}\n  Tout OK — le signer fonctionne comme attendu.\n{SEP}\n")
