# Tasks — Frigate Event Manager

> Protocole complet : `.claude/agents/orchestrator.md`

---

## Blackboard Actif

### T-432 | Tests T-430

- Status: DONE
- Owner: quality-guard
- Scope: tests/
- Locks: —
- Depends: T-430
- Blocks: T-433
- Notes: Reprendre les cas de tests Go (zone_multi, order_enforced, clock mock).

### T-433 | Simplification T-430

- Status: DONE
- Owner: code-simplifier
- Scope: custom_components/frigate_event_manager/filter.py
- Locks: —
- Depends: T-431, T-432
- Blocks: T-440
- Notes: |
    Issue MINOR de T-431 à traiter :
    1. filter.py : datetime.now sans timezone explicite.
       Documenter l'hypothèse "heure locale du serveur HA via .astimezone()".

### T-442 | Tests T-440

- Status: DONE
- Owner: quality-guard
- Scope: tests/
- Locks: —
- Depends: T-440
- Blocks: T-443
- Notes: —

### T-443 | Simplification T-440

- Status: DONE
- Owner: code-simplifier
- Scope: custom_components/frigate_event_manager/registry.py
- Locks: —
- Depends: T-441, T-442
- Blocks: T-450
- Notes: —

### T-453 | Simplification T-450

- Status: DONE
- Owner: code-simplifier
- Scope: custom_components/frigate_event_manager/event_store.py
- Locks: —
- Depends: T-451, T-452
- Blocks: T-460
- Notes: |
    Issue MINOR de T-451 à traiter :
    1. event_store.py L82 : `list(candidats)[:limit]` → remplacer par list(itertools.islice(candidats, limit)).

### T-462 | Tests T-460

- Status: DONE
- Owner: quality-guard
- Scope: tests/
- Locks: —
- Depends: T-460
- Blocks: T-463
- Notes: —

### T-490 | Docs — README + architecture.md + tasks.md

- Status: DONE
- Owner: reviewer
- Reviewer: reviewer
- Security: SECURITY_OK
- Doc: SYNCED
- Scope: README.md, docs/architecture.md, docs/tasks.md
- Locks: —
- Depends: T-483
- Blocks: T-499
- Notes: |
    README.md : réécrit entièrement (HACS, config flow, entités par caméra, unique_ids, prérequis MQTT).
    docs/architecture.md : réécrit pour l'architecture Python (Mermaid à jour, plus de mention Go).
    docs/tasks.md : tâches DONE archivées, blackboard allégé aux tâches actives uniquement.

### T-499 | PR finale — migration Python

- Status: TODO
- Owner: orchestrator
- Scope: feat/python-migration → main
- Locks: —
- Depends: T-490
- Blocks: —
- Notes: |
    Vérifier : pytest vert, coverage ≥80%, ruff 0 erreur, markdownlint 0 erreur.
    PR avec description complète de la migration.
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

---

## Archive — Migration Python (tâches DONE)

> Toutes les tâches ci-dessous sont terminées et validées.
> Elles sont conservées ici pour traçabilité.

### T-400 | Prérequis — Merger Go → main + créer branche Python

- Status: DONE
- Owner: humain
- Notes: |
    Branche Claude-review mergée dans main (--no-ff).
    Branche `feat/python-migration` créée.

### T-401 | Nettoyage — Supprimer les fichiers Go et résidus

- Status: DONE
- Owner: sre-cloud
- Notes: |
    Supprimé : internal/, cmd/, go.mod, go.sum, Dockerfile, Taskfile.yml,
    coverage.out, .devcontainer/, config/, maquette/, dev/.
    Supprimé fichiers racine Go/infra : config.yaml, docker-bake.hcl, etc.
    Conservé : custom_components/, hacs.json, .claude/, docs/, .github/.

### T-402 | Infra — Adapter CI/CD et Taskfile pour Python

- Status: DONE
- Owner: sre-cloud
- Notes: |
    validation.yml : pytest + coverage ≥80%, ruff, markdownlint.
    Nouveau Taskfile.yml : task test (pytest + coverage), task lint (ruff + markdownlint).

### T-410 | Squelette + config flow complet

- Status: DONE
- Owner: python-architect
- Notes: |
    config_flow.py, strings.json, translations/fr.json, manifest.json,
    `__init__.py`, const.py créés et fonctionnels.

### T-411 | Review T-410

- Status: DONE
- Owner: reviewer
- Notes: REVIEW_OK. Issues non-bloquantes corrigées en T-413.

### T-412 | Tests T-410

- Status: DONE
- Owner: quality-guard

### T-413 | Simplification T-410

- Status: DONE
- Owner: code-simplifier

### T-420 | Coordinator MQTT — subscribe + parse payload Frigate

- Status: DONE
- Owner: python-architect
- Notes: |
    coordinator.py : MQTT push via intégration native HA.
    FrigateEvent + CameraState dataclasses.
    _parse_event, _to_float, _cameras_as_list.
    async_start / async_stop.

### T-421 | Review T-420

- Status: DONE
- Owner: reviewer
- Security: SECURITY_OK
- Notes: REVIEW_OK. Issues MINOR corrigées en T-423.

### T-422 | Tests T-420

- Status: DONE
- Owner: quality-guard
- Notes: tests/test_coordinator.py — 44 tests.

### T-423 | Simplification T-420

- Status: DONE
- Owner: code-simplifier
- Notes: |
    _to_float() helper, _sync_data() supprimé, migration mqtt.async_subscribe API ≥2023.x.

### T-430 | Filtres — ZoneFilter, LabelFilter, TimeFilter

- Status: DONE
- Owner: python-architect
- Notes: |
    filter.py créé : Filter (protocole), ZoneFilter, LabelFilter, TimeFilter, FilterChain.
    Convention liste vide = tout accepter sur les 3 filtres.

### T-431 | Review T-430

- Status: DONE
- Owner: reviewer
- Security: SECURITY_OK
- Notes: APPROVED. Issue MINOR datetime timezone documentée (corrigée partiellement en T-433).

### T-440 | Registry — état caméras en mémoire

- Status: DONE
- Owner: python-architect
- Notes: |
    registry.py : CameraRegistry, persistence atomique JSON, auto-découverte enabled=True.

### T-441 | Review T-440

- Status: DONE
- Owner: reviewer
- Security: SECURITY_OK
- Notes: REVIEW_OK. Issues MINOR corrigées en T-443.

### T-450 | Event Store — ring buffer événements

- Status: DONE
- Owner: python-architect
- Notes: |
    event_store.py : deque(maxlen=200), EventRecord, add(), list(), stats().

### T-451 | Review T-450

- Status: DONE
- Owner: reviewer
- Security: SECURITY_OK
- Notes: REVIEW_OK. Issue MINOR islice corrigée en T-453.

### T-452 | Tests T-450

- Status: DONE
- Owner: quality-guard
- Notes: tests/test_event_store.py — 31 tests.

### T-460 | Throttler — anti-spam par caméra

- Status: DONE
- Owner: python-architect
- Notes: |
    throttle.py : Throttler, cooldown configurable, clock injectable, should_notify / record.

### T-461 | Review T-460

- Status: DONE
- Owner: reviewer
- Security: SECURITY_OK
- Notes: APPROVED — aucune issue.

### T-463 | Simplification T-460

- Status: DONE
- Owner: code-simplifier

### T-470 | Notifier — notifications HA Companion

- Status: DONE
- Owner: python-architect
- Notes: |
    notifier.py : HANotifier, html.escape sur tous les champs, tag, actions,
    critical iOS, guard URL thumb_url (startswith http).

### T-471 | Review T-470

- Status: DONE
- Owner: reviewer
- Security: SECURITY_OK
- Notes: APPROVED. Issue MINOR thumb_url validation ajoutée en T-473.

### T-472 | Tests T-470

- Status: DONE
- Owner: quality-guard
- Notes: tests/test_notifier.py — 35 tests.

### T-473 | Simplification T-470

- Status: DONE
- Owner: code-simplifier
- Notes: Guard URL ajouté, test adapté.

### T-480 | Entités HA — sensor, switch, binary_sensor

- Status: DONE
- Owner: python-architect
- Notes: |
    sensor.py (3 sensors), switch.py, binary_sensor.py (FrigateMotionSensor).
    Tous : has_entity_name=True, unique_id fem_{cam}_{key}, CoordinatorEntity.

### T-481 | Review T-480

- Status: DONE
- Owner: reviewer
- Security: SECURITY_OK
- Notes: APPROVED. Limitation découverte dynamique documentée, T-484 prévu.

### T-482 | Tests T-480

- Status: DONE
- Owner: quality-guard
- Notes: tests/test_entities.py — 44 tests.

### T-483 | Simplification T-480

- Status: DONE
- Owner: code-simplifier
- Notes: Docstrings ajoutées sur async_setup_entry des 3 fichiers.

---

## Archive — Phases Go (référence)

> Code Go archivé sur la branche `main` après merge de `Claude-review`.
> Les concepts métier (filtres, throttler, registry, event_store) sont traduits en Python dans la migration.

### Phase 1 : MQTT Discovery (FAIT)

- [x] 1.1 Camera Registry — persistence + auto-decouverte
- [x] 1.2 MQTT Discovery Publisher — 5 entites par camera
- [x] 1.3 Subscriber enrichi — Connect/Wait, routing commandes
- [x] 1.4 Branchement main.go

### Phase 2 : Web UI (FAIT)

- [x] 2.1 Event Store (ring buffer Go)
- [x] 2.2 Config.Sanitized()
- [x] 2.3–2.7 Serveur HTTP + SPA + API Management

### Phase 3 : Filtres (PARTIELLEMENT FAIT en Go — traduits Python)

- [x] ZoneFilter, LabelFilter, TimeFilter (Go → T-430)
- [ ] ScoreFilter (abandonné)

### Phases 4–5 : Différenciation + HACS (REMPLACÉES par migration Python)

> Toutes les fonctionnalités prévues (multi-canal, présence, services HA, entités natives)
> sont implémentées directement dans l'intégration Python.
