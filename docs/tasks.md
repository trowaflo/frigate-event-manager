# Tasks — Frigate Event Manager

> Protocole complet : `.claude/agents/orchestrator.md`

---

## Blackboard Actif

### T-499 | PR finale — migration Python

- Status: DONE
- Owner: orchestrator
- Scope: feat/python-migration → main
- Locks: —
- Depends: —
- Blocks: —
- Notes: PR #7 créée, en attente de validation humaine avant merge.

---

## Refactoring v2 — Architecture HA native

> Branche : `feat/ha-refactor`
> Objectif : config entry par caméra, 2 entités (switch + binary_sensor), suppression EventStore/Registry/sensors redondants.

### Phase 1 — Nettoyage

### T-500 | Supprimer composants obsolètes

- Status: IN_PROGRESS
- Owner: python-architect
- Scope: `event_store.py`, `registry.py`, `sensor.py`, `tests/test_event_store.py`, `tests/test_registry.py`, `tests/test_entities.py` (partiel), `__init__.py`, `coordinator.py`
- Locks: [LOCKED by T-500: custom_components/frigate_event_manager/event_store.py | since: 2026-03-16T00:00:00Z | ttl: 10m]
         [LOCKED by T-500: custom_components/frigate_event_manager/registry.py | since: 2026-03-16T00:00:00Z | ttl: 10m]
         [LOCKED by T-500: custom_components/frigate_event_manager/sensor.py | since: 2026-03-16T00:00:00Z | ttl: 10m]
         [LOCKED by T-500: custom_components/frigate_event_manager/__init__.py | since: 2026-03-16T00:00:00Z | ttl: 10m]
         [LOCKED by T-500: custom_components/frigate_event_manager/coordinator.py | since: 2026-03-16T00:00:00Z | ttl: 10m]
         [LOCKED by T-500: tests/test_event_store.py | since: 2026-03-16T00:00:00Z | ttl: 10m]
         [LOCKED by T-500: tests/test_registry.py | since: 2026-03-16T00:00:00Z | ttl: 10m]
         [LOCKED by T-500: tests/test_entities.py | since: 2026-03-16T00:00:00Z | ttl: 10m]
- Depends: —
- Blocks: T-504
- Notes: |
    Supprimer event_store.py, registry.py, sensor.py.
    Retirer sensor de PLATFORMS dans __init__.py.
    Nettoyer coordinator.py (_cameras_as_list ne retourne plus que switch + binary_sensor).
    Adapter/supprimer les tests correspondants.

### T-501 | Review — nettoyage

- Status: TODO
- Owner: reviewer
- Scope: tous les fichiers modifiés par T-500
- Locks: —
- Depends: T-500
- Blocks: T-503
- Notes: —

### T-502 | Tests — nettoyage

- Status: TODO
- Owner: quality-guard
- Scope: `tests/`
- Locks: —
- Depends: T-500
- Blocks: T-503
- Notes: Coverage ≥80% après suppression.

### T-503 | Simplification — nettoyage

- Status: TODO
- Owner: code-simplifier
- Scope: tous les fichiers modifiés par T-500
- Locks: —
- Depends: T-501, T-502
- Blocks: T-504
- Notes: —

---

### Phase 2 — Frigate API client + Config flow

### T-504 | Frigate API client + config flow 2 étapes

- Status: TODO
- Owner: python-architect
- Scope: `frigate_client.py` (nouveau), `config_flow.py`, `const.py`
- Locks: —
- Depends: T-503
- Blocks: T-508
- Notes: |
    frigate_client.py : GET {url}/api/cameras → liste noms caméras. Pas de valeur par défaut pour URL/port.
    Config flow étape 1 (global, unique si absent) :
      - URL Frigate (pas de défaut), notify_target global
      - Test connexion API → erreur explicite si injoignable
      - unique_id = DOMAIN (une seule entrée globale)
    Config flow étape 2 (caméra, répétable via "+ Add entry") :
      - Appelle API Frigate → sélecteur de caméras disponibles
      - notify_target optionnel (vide = hérite du global)
      - unique_id = f"fem_{camera_name}"
    _abort_if_unique_id_configured() empêche les doublons par caméra.

### T-505 | Review — config flow

- Status: TODO
- Owner: reviewer
- Scope: `frigate_client.py`, `config_flow.py`, `const.py`
- Locks: —
- Depends: T-504
- Blocks: T-507
- Notes: —

### T-506 | Tests — config flow

- Status: TODO
- Owner: quality-guard
- Scope: `tests/test_config_flow.py`, `tests/test_frigate_client.py` (nouveau)
- Locks: —
- Depends: T-504
- Blocks: T-507
- Notes: Mocker les appels HTTP Frigate API avec aioresponses ou unittest.mock.

### T-507 | Simplification — config flow

- Status: TODO
- Owner: code-simplifier
- Scope: `frigate_client.py`, `config_flow.py`
- Locks: —
- Depends: T-505, T-506
- Blocks: T-508
- Notes: —

---

### Phase 3 — Coordinator par caméra + entités

### T-508 | Coordinator par caméra + switch + binary_sensor

- Status: TODO
- Owner: python-architect
- Scope: `coordinator.py`, `switch.py`, `binary_sensor.py`, `__init__.py`, `notifier.py`, `filter.py`, `throttle.py`
- Locks: —
- Depends: T-507
- Blocks: T-512
- Notes: |
    Coordinator reçoit un seul nom de caméra (depuis entry.data["camera"]).
    MQTT topic dérivé du nom : f"frigate/reviews" filtré par camera dans le payload.
    Notifications : entry.data.get("notify_target") ou fallback sur entrée globale.
    filter.py et throttle.py instanciés par coordinator à partir de entry.data.
    switch.py et binary_sensor.py : une entité par config entry caméra.
    __init__.py : async_setup_entry distingue type global vs type caméra.

### T-509 | Review — coordinator + entités

- Status: TODO
- Owner: reviewer
- Scope: tous les fichiers modifiés par T-508
- Locks: —
- Depends: T-508
- Blocks: T-511
- Notes: —

### T-510 | Tests — coordinator + entités

- Status: TODO
- Owner: quality-guard
- Scope: `tests/test_coordinator.py`, `tests/test_entities.py`
- Locks: —
- Depends: T-508
- Blocks: T-511
- Notes: Coverage ≥80%. Un coordinator par caméra, tester le fallback notify_target.

### T-511 | Simplification — coordinator + entités

- Status: TODO
- Owner: code-simplifier
- Scope: tous les fichiers modifiés par T-508
- Locks: —
- Depends: T-509, T-510
- Blocks: T-512
- Notes: —

---

### Phase 4 — PR

### T-512 | PR finale — refactoring v2

- Status: TODO
- Owner: orchestrator
- Scope: `feat/ha-refactor` → `main`
- Locks: —
- Depends: T-511
- Blocks: —
- Notes: |
    Vérifier : pytest vert, coverage ≥80%, ruff 0 erreur, markdownlint 0 erreur.
    Validation humaine obligatoire avant merge.

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
