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
