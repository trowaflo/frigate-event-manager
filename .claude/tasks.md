# Tasks — Frigate Event Manager

> Protocole complet : `.claude/agents/orchestrator.md`

---

## Blackboard Actif

### T-541 | Publication HACS

- Status: TODO
- Owner: humain + python-architect
- Priority: P1
- Scope: racine du projet, `hacs.json`
- Locks: —
- Depends: —
- Blocks: —
- Notes: |
    Prérequis HACS (à valider avant soumission) :
    Repo public avec description, GitHub Release (Release Please),
    `manifest.json` valide (domain, version, codeowners, iot_class, config_flow),
    aucun secret dans l'historique (T-534 audité — OK).
    Étapes :
    1. Passer le repo en public (terraform-github : `visibility = "public"` → terraform apply)
    2. Merger PR #13 (`feat/python-migration` → `main`)
    3. Merger `feat/security-analysis` dans terraform-github → terraform apply
    4. Créer une première release via Release Please (merger la PR release v0.9.0)
    5. Ajouter le repo comme custom repository HACS pour valider en local
    6. Soumission HACS default (optionnel) : PR sur <https://github.com/hacs/default>

### T-542 | Refonte `frigate_client.py` — session HA partagée

- Status: TODO
- Owner: python-architect
- Priority: P1
- Scope: `frigate_client.py`, `__init__.py`, `tests/test_frigate_client.py`
- Locks: —
- Depends: —
- Blocks: —
- Notes: |
    Objectif : utiliser `async_get_clientsession(hass)` (session HTTP partagée HA)
    au lieu de créer une nouvelle `aiohttp.ClientSession` par requête.
    Changements attendus :
    1. `FrigateClient.__init__` : ajouter paramètre `hass: HomeAssistant`
    2. `_fetch_frigate_config` + `get_media` : utiliser `async_get_clientsession(hass)`
       au lieu de `aiohttp.ClientSession(timeout=...)`. Le timeout reste injectable
       via `aiohttp.ClientTimeout`.
    3. `__init__.py` : passer `hass` lors de l'instanciation de `FrigateClient`
    4. `tests/test_frigate_client.py` : adapter le mock — patcher
       `homeassistant.helpers.aiohttp_client.async_get_clientsession` au lieu de
       `aiohttp.ClientSession`.
    Pipeline : T-542 → review + tests (parallèle) → simplification → commit.

### T-543 | Traduction anglais — code, commentaires, logs, docs

- Status: DONE
- Owner: orchestrator
- Priority: P1
- Scope: tous les fichiers Python, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `docs/`
- Locks: —
- Depends: —
- Blocks: T-541
- Notes: |
    Traduire en anglais :
    Commentaires inline et docstrings dans tous les fichiers Python.
    Messages de log (`_LOGGER.xxx`).
    `CODE_OF_CONDUCT.md`.
    `docs/architecture.md`.
    Exception : `translations/fr.json` reste en français (traduction UI HA).

### T-544 | Redirect HA sur URL signée expirée

- Status: TODO
- Owner: python-architect
- Priority: P2
- Scope: `media_proxy.py`, `tests/test_media_proxy.py`
- Locks: —
- Depends: —
- Blocks: —
- Notes: |
    Actuellement le proxy retourne 401 pour toute vérification échouée (signature
    invalide OU expiration). Distinguer les deux cas :
  - Signature invalide / `kid` inconnu → 401 (sécurité, ne pas rediriger)
  - URL expirée (`now > exp`, mais signature valide) → 302 redirect vers
    `hass.config.external_url or hass.config.internal_url` (racine HA)
    Logique dans `media_proxy.py` : vérifier l'expiration avant le HMAC,
    ou ajouter une méthode `is_expired(exp_str)` sur le signer.
    Aucune modification du config flow, aucun couplage à une vue spécifique.
    Ajouter test : `test_proxy_url_expiree_retourne_302_redirect`.

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
