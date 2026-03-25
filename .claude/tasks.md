# Tasks — Frigate Event Manager

> Protocole complet : `.claude/agents/orchestrator.md`

---

## Blackboard Actif

### T-541 | Publication HACS

- Status: DONE
- Owner: humain + python-architect
- Priority: P1
- Scope: racine du projet, `hacs.json`
- Locks: —
- Depends: —
- Blocks: —
- Notes: |
    Repo public, HACS custom repository fonctionnel (v0.11.0 latest release).
    Icon "not available" dans HACS store — cause identifiée : cache HACS local.
    Fix : forcer un rescan HACS (Redownload ou restart HA).
    Les fichiers icon sont corrects (256x256 RGB, brand/icon.png accessible HTTP 200).

### T-542 | Refonte `frigate_client.py` — session HA partagée

- Status: DONE
- Owner: python-architect
- Priority: P1
- Scope: `frigate_client.py`, `__init__.py`, `tests/test_frigate_client.py`
- Locks: —
- Depends: —
- Blocks: —
- Notes: |
    `async_get_clientsession(hass)` utilisé à la place de `aiohttp.ClientSession`.
    Mergé sur main.

### T-543 | Traduction anglais — code, commentaires, logs, docs

- Status: DONE
- Owner: orchestrator
- Priority: P1
- Scope: tous les fichiers Python, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `docs/`
- Locks: —
- Depends: —
- Blocks: T-541
- Notes: |
    Tout traduit en anglais. `translations/fr.json` reste en français (UI HA).

### T-544 | Redirect HA sur URL signée expirée

- Status: DONE
- Owner: python-architect
- Priority: P2
- Scope: `media_proxy.py`, `domain/signer.py`, `domain/ports.py`, `tests/`
- Locks: —
- Depends: —
- Blocks: —
- Notes: |
    `is_expired()` ajouté sur `MediaSigner` et `MediaSignerPort`.
    302 redirect vers `external_url or internal_url` si URL expirée.
    401 conservé pour signature invalide / `kid` inconnu.
    Tests : `test_proxy_url_expiree_retourne_302_redirect` + sans URL HA → 401.
    Docstring `MediaSignerPort.sign_url` corrigée : `?exp=...&kid=...&sig=...`.
    PR #22 (`feat/t544-expired-url-redirect`) — CI verte, prête à merger.

### T-547 | Proxy sécurisé — 404 uniforme + event sécurité

- Status: DONE
- Owner: orchestrator
- Priority: P2
- Scope: `media_proxy.py`, `tests/test_media_proxy.py`, `README.md`, `docs/architecture.md`
- Locks: —
- Depends: T-544
- Blocks: —
- Notes: |
    Implémentation terminée (commits sur `feat/t544-expired-url-redirect`).
    404 uniforme pour toute URL rejetée (plus de 302/401).
    `verify()` → 404 ; `is_expired()` pour sélectionner le niveau de log.
    Signature invalide → WARNING + `frigate_em_security_event` + persistent notification.
    URL expirée → DEBUG uniquement, aucun event.
    Pipeline rattrapé : reviewer + quality-guard → simplify.

### T-547b | Review qualité + sécurité

- Status: DONE
- Owner: reviewer
- Priority: P2
- Scope: `media_proxy.py`, `tests/test_media_proxy.py`
- Locks: T-547c, T-547d
- Depends: T-547
- Blocks: T-547c
- Notes: |
    M-01 (MAJOR) corrigé : `full_path[:512]` avant event bus + notification.
    PENDING_FIXUP appliqués par simplifier : PF-01 (503 sans text), PF-02 (whitelist content-type),
    PF-03 (async callbacks), PF-04 (TYPE_CHECKING import).

### T-547d | Tests + couverture

- Status: DONE
- Owner: quality-guard
- Priority: P2
- Scope: `tests/test_media_proxy.py`
- Locks: T-547c
- Depends: T-547b
- Blocks: T-547c
- Notes: 100% couverture `media_proxy.py`, 6/6 tests passent.

### T-547c | Simplification

- Status: DONE
- Owner: code-simplifier
- Priority: P2
- Scope: `media_proxy.py`, `tests/test_media_proxy.py`
- Locks: —
- Depends: T-547b, T-547d
- Blocks: —
- Notes: Appliquer PF-01 à PF-04 depuis T-547b.

### T-545 | Codecov PR check manquant

- Status: TODO
- Owner: sre-cloud
- Priority: P2
- Scope: `validation.yml` + `trowaflo/github-actions/.github/workflows/ha-integration.yml`
- Locks: —
- Depends: —
- Blocks: —
- Notes: |
    `CODECOV_TOKEN` existe déjà comme repo secret dans `frigate-event-manager`.
    Problème : reusable workflow `ha-integration.yml` n'utilise pas le token
    → upload tokenless OK (pas d'erreur CI) mais aucun PR status check Codecov.
    Fix en 2 étapes :
    1. `validation.yml` : ajouter `secrets: inherit` au job `python`
    2. `trowaflo/github-actions` `ha-integration.yml` : ajouter
       `token: ${{ secrets.CODECOV_TOKEN }}` dans l'étape `Upload coverage`
    Nécessite un commit dans les 2 repos.

### T-546 | Re-activer kics après supply chain attack

- Status: TODO
- Owner: sre-cloud
- Priority: P3
- Scope: `.github/workflows/validation.yml`
- Locks: —
- Depends: —
- Blocks: —
- Notes: |
    kics désactivé le 2026-03-23 (supply chain attack sur checkmarx/kics-github-action).
    Re-activer quand Checkmarx confirme que l'action est sûre et le SHA vérifié.
    Dé-commenter le job `kics` dans `validation.yml`.
    Vérifier le SHA du reusable workflow `kics.yml` dans `trowaflo/github-actions`.

### T-548 | Proxy sécurisé — distinction expired vs forged via `has_valid_signature()`

- Status: DONE
- Owner: python-architect
- Scope: `custom_components/frigate_event_manager/domain/signer.py`, `custom_components/frigate_event_manager/domain/ports.py`, `custom_components/frigate_event_manager/media_proxy.py`, `tests/test_media_proxy.py`, `docs/architecture.md`
- Locks: —
- Depends: —
- Blocks: T-548b, T-548d
- Notes: |
    Ajouter `has_valid_signature(path, exp_str, kid_str, sig) -> bool` sur `MediaSigner`
    et `MediaSignerPort` : vérifie HMAC uniquement, sans short-circuit sur expiry.
    Mettre à jour `media_proxy.py` : après `verify()` échoue, appeler `has_valid_signature()`.
    Si forged (sig invalide), déclencher le security event même si l'URL est expirée.
    Si expired avec sig valide : DEBUG uniquement (comportement inchangé).
    Corriger `test_proxy_url_expiree_retourne_404` : utiliser une vraie sig expirée (pas `sig=whatever`).
    Ajouter cas de test : forged+expired → security event déclenché.
    Corriger `docs/architecture.md` : diagram aligné sur "404 uniforme", supprimer implication
    de distinction "expired-but-valid-sig" dans le diagram actuel.

### T-548b | Review qualité + sécurité — `has_valid_signature()`

- Status: DONE
- Owner: reviewer
- Scope: `custom_components/frigate_event_manager/domain/signer.py`, `custom_components/frigate_event_manager/domain/ports.py`, `custom_components/frigate_event_manager/media_proxy.py`, `tests/test_media_proxy.py`, `docs/architecture.md`
- Locks: —
- Depends: T-548
- Blocks: T-548c
- Notes: |
    Status: APPROVED
    Security: SECURITY_OK
    Doc: NO_CHANGE_NEEDED
    PENDING_FIXUP:
      PF-01 (INFO) — `tests/test_media_proxy.py`:201 : `test_proxy_url_expiree_et_forgee_retourne_404_avec_event`
        ne vérifie pas `events[0].data["path"]`.
        Ajouter `assert events[0].data["path"] == "/api/events/abc/snapshot.jpg"`
        pour cohérence avec `test_proxy_signature_invalide_retourne_404`.

### T-548d | Tests + couverture — `has_valid_signature()`

- Status: DONE
- Owner: quality-guard
- Scope: `tests/test_media_proxy.py`
- Locks: —
- Depends: T-548
- Blocks: T-548c
- Notes: |
    Coverage: `media_proxy.py` 98%, `domain/signer.py` 97%, TOTAL 99%.
    7/7 tests passent, 419 passent globalement.
    Tous les cas obligatoires couverts : forged+expired → security event (T+T),
    expired+valid-sig → debug only (T+F), `has_valid_signature()` kid inconnu/sig invalide/sig valide.
    Seule ligne non couverte : `except (ValueError, TypeError)` dans `has_valid_signature()`
    pour paramètres non-numériques — cas défensif, non requis par T-548d.

### T-548c | Simplification — batch fixes T-548b

- Status: DONE
- Owner: code-simplifier
- Scope: `custom_components/frigate_event_manager/domain/signer.py`, `custom_components/frigate_event_manager/domain/ports.py`, `custom_components/frigate_event_manager/media_proxy.py`, `tests/test_media_proxy.py`
- Locks: —
- Depends: T-548b, T-548d
- Blocks: —
- Notes: |
    PF-01 appliqué : `assert events[0].data["path"] == "/api/events/abc/snapshot.jpg"`
    ajouté dans `test_proxy_url_expiree_et_forgee_retourne_404_avec_event`.
    ruff OK, 7/7 tests passent.

---

<!--
### T-XXX | [Titre]

- Status: TODO
- Owner: —
- Scope: —
- Locks: —
- Depends: —
- Blocks: —
- Notes: —
-->
