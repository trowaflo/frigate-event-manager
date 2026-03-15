# Tasks — Frigate Event Manager

> Protocole complet : `.claude/agents/orchestrator.md`

---

## Blackboard Actif

### T-400 | Prérequis — Merger Go → main + créer branche Python

- Status: DONE
- Owner: humain
- Scope: git
- Locks: —
- Depends: —
- Blocks: T-401
- Notes: |
    Merger la branche Claude-review dans main (--no-ff) pour snapshot du code Go.
    Créer la branche `feat/python-migration`.
    Aucune tâche suivante ne démarre avant que T-400 soit DONE.

### T-401 | Nettoyage — Supprimer les fichiers Go et résidus

- Status: DONE
- Owner: sre-cloud
- Scope: racine du repo
- Locks: —
- Depends: T-400
- Blocks: T-410
- Notes: |
    Supprimer : internal/, cmd/, go.mod, go.sum, Dockerfile, Taskfile.yml,
    coverage.out, .devcontainer/, config/, maquette/, dev/.
    Supprimer fichiers racine Go/infra : config.yaml, docker-bake.hcl,
    kics-config.json, release-please-config.json, renovate.json5.
    Supprimer docs obsolètes : BLUEPRINT_FRIGATE_ANALYSIS.md, Besoin.md.
    Garder : custom_components/, hacs.json, .claude/, docs/, .github/, .gitignore,
    .markdownlint.json, README.md.
    Mettre à jour .gitignore.

### T-402 | Infra — Adapter CI/CD et Taskfile pour Python

- Status: DONE
- Owner: sre-cloud
- Scope: .github/workflows/validation.yml, Taskfile.yml (nouveau)
- Locks: —
- Depends: T-401
- Blocks: T-410
- Notes: |
    validation.yml : remplacer jobs Go (golangci-lint, hadolint, addon-lint, docker build)
    par pytest + coverage ≥80%, ruff (lint Python), markdownlint (inchangé).
    Nouveau Taskfile.yml : task test (pytest + coverage), task lint (ruff + markdownlint).
    Pas de task dev ni task build (plus de Docker).

### T-410 | Squelette + config flow complet

- Status: DONE
- Owner: python-architect
- Scope: custom_components/frigate_event_manager/
- Locks: —
- Depends: T-401, T-402
- Blocks: T-411, T-412
- Notes: |
    Réécrire config_flow.py : formulaire complet avec tous les champs de config
    (MQTT broker URL, port, username, password, topic, notify_target,
    severity_filter, zones, labels, disable_times, cooldown).
    Mettre à jour strings.json + translations/fr.json avec tous les labels.
    Mettre à jour manifest.json (dependencies: mqtt).
    `__init__.py` : PLATFORMS, async_setup_entry, async_unload_entry.
    const.py : toutes les constantes (DOMAIN, CONF_*, DEFAULTS).

### T-411 | Review T-410

- Status: DONE
- Owner: reviewer
- Scope: custom_components/frigate_event_manager/
- Locks: —
- Depends: T-410
- Blocks: T-413
- Notes: |
    REVIEW_OK. Points non-bloquants pour T-413 :
    1. config_flow.py L57 : check cooldown<0 redondant avec vol.Range(min=0) — branche morte à supprimer
    2. __init__.py L32 : utiliser CONF_MQTT_TOPIC au lieu de la string littérale "mqtt_topic"

### T-412 | Tests T-410

- Status: DONE
- Owner: quality-guard
- Scope: tests/
- Locks: —
- Depends: T-410
- Blocks: T-413
- Notes: Utiliser pytest-homeassistant-custom-component. Config flow : happy path + erreurs de connexion.

### T-413 | Simplification T-410

- Status: DONE
- Owner: code-simplifier
- Scope: custom_components/frigate_event_manager/
- Locks: —
- Depends: T-411, T-412
- Blocks: T-420
- Notes: —

### T-420 | Coordinator MQTT — subscribe + parse payload Frigate

- Status: DONE
- Owner: python-architect
- Scope: custom_components/frigate_event_manager/coordinator.py
- Locks: —
- Depends: T-413
- Blocks: T-421, T-422
- Notes: |
    CONTEXT REVIEWER (issues BLOCKING à corriger) :
    1. coordinator.py actuel utilise aiohttp vers /api/cameras de l'addon Go — à supprimer entièrement.
    2. __init__.py appelle coordinator.async_config_entry_first_refresh() — incompatible avec MQTT push.
       Remplacer par un coordinator sans polling (update_interval=None) + démarrage MQTT dans async_setup.
    3. switch.py utilise entry.data["url"] (KeyError car la clé n'existe plus) et aiohttp PATCH — à corriger.
    4. sensor.py attend cam["name"], cam["last_severity"], cam["last_objects"], cam["event_count_24h"] —
       la shape de coordinator.data doit être cohérente avec ces clés (ou sensor.py doit être adapté).

    SPEC T-420 :
    Utiliser hass.components.mqtt.async_subscribe (intégration MQTT native HA).
    Souscrire à frigate/reviews (ou topic configuré via CONF_MQTT_TOPIC).
    Parser le payload JSON → dataclass FrigateEvent (type, camera, severity, objects,
    zones, score, thumb_path, review_id, start_time, end_time).
    Gérer reconnexion automatique (HA MQTT s'en charge).
    Exposer coordinator.data : dict[str, CameraState] — clé = camera_name.
    CameraState expose : name, last_severity, last_objects, event_count_24h, last_event_time, enabled.
    coordinator.async_start() souscrit au topic MQTT + stocke l'unsubscribe callback.
    coordinator.async_stop() appelle l'unsubscribe callback.
    __init__.py : remplacer async_config_entry_first_refresh() par coordinator.async_start().
    async_unload_entry : appeler coordinator.async_stop() avant async_unload_platforms().
    switch.py : remplacer aiohttp PATCH par coordinator.set_camera_enabled(cam_name, enabled).
    Ne pas modifier sensor.py (T-480 s'en chargera), mais s'assurer que coordinator.data
    est itérable comme liste de dicts avec les clés "name", "last_severity", "last_objects",
    "event_count_24h" pour préserver la compatibilité avec l'existant.

### T-421 | Review T-420

- Status: REVIEW_OK
- Owner: reviewer
- Security: SECURITY_OK
- Scope: custom_components/frigate_event_manager/coordinator.py
- Locks: —
- Depends: T-420
- Blocks: T-423
- Notes: |
    REVIEW_OK — aucune issue bloquante. Issues MINOR pour T-423 (code-simplifier) :
    1. coordinator.py _parse_event L95 : float(score) peut lever ValueError si score est une string
       non-numérique (ex: "N/A"). Entourer d'un try/except ou utiliser une conversion sécurisée.
    2. coordinator.py _parse_event L99 : end_time non converti en float — inconsistance avec start_time.
    3. coordinator.py set_camera_enabled L143-144 et _handle_mqtt_message L210-211 : _sync_data()
       avant async_set_updated_data() est redondant (async_set_updated_data met déjà à jour self.data).
       Supprimer _sync_data() ou redéfinir le pattern.
    4. event_count_24h croît indéfiniment (pas de fenêtre glissante). Nom trompeur.
       Acceptable pour T-420, à corriger en T-450 (EventStore) ou T-480.
    5. hass.components.mqtt.async_subscribe : API deprecated en HA >= 2023.x.
       Migrer vers `from homeassistant.components.mqtt import async_subscribe` en T-423.
    __init__.py : conforme spec T-420. switch.py : conforme spec T-420 (zéro aiohttp, zéro KeyError).

### T-422 | Tests T-420

- Status: IN_REVIEW
- Owner: quality-guard
- Scope: tests/
- Locks: —
- Depends: T-420
- Blocks: T-423
- Notes: |
    Fichier : tests/test_coordinator.py (44 tests)
    Couvre : _parse_event (16), CameraState (3), _handle_mqtt_message (11),
    set_camera_enabled (6), async_start/stop (5), _async_update_data (2).
    Mock MQTT : object.__new__ + MagicMock(spec=HomeAssistant) pour async_start/stop.
    Tests avec fixture hass HA pour les chemins à chaud (_handle_mqtt_message, set_camera_enabled).
    Coverage attendu ≥80% — valider avec : pytest tests/test_coordinator.py --cov=custom_components/frigate_event_manager/coordinator --cov-report=term-missing

### T-423 | Simplification T-420

- Status: DONE
- Owner: code-simplifier
- Scope: custom_components/frigate_event_manager/coordinator.py
- Locks: —
- Depends: T-421, T-422
- Blocks: T-430
- Notes: |
    1. _to_float() helper : conversion sécurisée float avec try/except ValueError/TypeError.
       Appliqué à score, start_time, end_time (end_time harmonisé avec start_time).
    2. _sync_data() supprimé : remplacé par _cameras_as_list() qui retourne la liste
       sans muter self.data. async_set_updated_data(_cameras_as_list()) en appel unique.
    3. mqtt.async_subscribe(hass, topic, cb) : migration API HA >= 2023.x.
       Tests async_start adaptés via patch() sur le symbole importé.

### T-430 | Filtres — ZoneFilter, LabelFilter, TimeFilter

- Status: DONE
- Owner: python-architect
- Scope: custom_components/frigate_event_manager/filter.py
- Locks: —
- Depends: T-423
- Blocks: T-431, T-432
- Notes: |
    filter.py créé avec : protocole Filter, ZoneFilter, LabelFilter, TimeFilter, FilterChain.
    Convention liste vide = tout accepter respectée sur les 3 filtres.
    ZoneFilter : zone_multi (toutes requises) + zone_order_enforced (sous-séquence via iter).
    LabelFilter : au moins un objet match (set intersection).
    TimeFilter : clock injectable (défaut datetime.now), disabled_hours list[int].
    FilterChain : all() avec court-circuit dès le premier refus.
    FrigateEvent importé depuis .coordinator.

### T-431 | Review T-430

- Status: TODO
- Owner: reviewer
- Scope: custom_components/frigate_event_manager/filter.py
- Locks: —
- Depends: T-430
- Blocks: T-433
- Notes: —

### T-432 | Tests T-430

- Status: TODO
- Owner: quality-guard
- Scope: tests/
- Locks: —
- Depends: T-430
- Blocks: T-433
- Notes: Reprendre les cas de tests Go (zone_multi, order_enforced, clock mock).

### T-433 | Simplification T-430

- Status: TODO
- Owner: code-simplifier
- Scope: custom_components/frigate_event_manager/filter.py
- Locks: —
- Depends: T-431, T-432
- Blocks: T-440
- Notes: —

### T-440 | Registry — état caméras en mémoire

- Status: TODO
- Owner: python-architect
- Scope: custom_components/frigate_event_manager/registry.py
- Locks: —
- Depends: T-433
- Blocks: T-441, T-442
- Notes: |
    Dict camera_name → CameraState (enabled, last_severity, last_objects,
    event_count_24h, last_event_time).
    Persistence dans hass.config.path("frigate_em_state.json") (pas /data/).
    Écriture atomique (tmp + rename).
    Auto-découverte des nouvelles caméras (enabled=True par défaut).

### T-441 | Review T-440

- Status: TODO
- Owner: reviewer
- Scope: custom_components/frigate_event_manager/registry.py
- Locks: —
- Depends: T-440
- Blocks: T-443
- Notes: —

### T-442 | Tests T-440

- Status: TODO
- Owner: quality-guard
- Scope: tests/
- Locks: —
- Depends: T-440
- Blocks: T-443
- Notes: —

### T-443 | Simplification T-440

- Status: TODO
- Owner: code-simplifier
- Scope: custom_components/frigate_event_manager/registry.py
- Locks: —
- Depends: T-441, T-442
- Blocks: T-450
- Notes: —

### T-450 | Event Store — ring buffer événements

- Status: TODO
- Owner: python-architect
- Scope: custom_components/frigate_event_manager/event_store.py
- Locks: —
- Depends: T-443
- Blocks: T-451, T-452
- Notes: |
    collections.deque(maxlen=200).
    EventRecord : camera, severity, objects, zones, timestamp, thumb_path.
    Méthodes : add(), list(limit, severity), stats() → events_24h, alerts_24h.

### T-451 | Review T-450

- Status: TODO
- Owner: reviewer
- Scope: custom_components/frigate_event_manager/event_store.py
- Locks: —
- Depends: T-450
- Blocks: T-453
- Notes: —

### T-452 | Tests T-450

- Status: TODO
- Owner: quality-guard
- Scope: tests/
- Locks: —
- Depends: T-450
- Blocks: T-453
- Notes: —

### T-453 | Simplification T-450

- Status: TODO
- Owner: code-simplifier
- Scope: custom_components/frigate_event_manager/event_store.py
- Locks: —
- Depends: T-451, T-452
- Blocks: T-460
- Notes: —

### T-460 | Throttler — anti-spam par caméra

- Status: TODO
- Owner: python-architect
- Scope: custom_components/frigate_event_manager/throttle.py
- Locks: —
- Depends: T-453
- Blocks: T-461, T-462
- Notes: |
    Cooldown configurable par caméra (défaut : 60s).
    Dict camera_name → last_notified_time.
    Méthode should_notify(camera, now) → bool.
    Clock injectable pour les tests.

### T-461 | Review T-460

- Status: TODO
- Owner: reviewer
- Scope: custom_components/frigate_event_manager/throttle.py
- Locks: —
- Depends: T-460
- Blocks: T-463
- Notes: —

### T-462 | Tests T-460

- Status: TODO
- Owner: quality-guard
- Scope: tests/
- Locks: —
- Depends: T-460
- Blocks: T-463
- Notes: —

### T-463 | Simplification T-460

- Status: TODO
- Owner: code-simplifier
- Scope: custom_components/frigate_event_manager/throttle.py
- Locks: —
- Depends: T-461, T-462
- Blocks: T-470
- Notes: —

### T-470 | Notifier — notifications HA Companion

- Status: TODO
- Owner: python-architect
- Scope: custom_components/frigate_event_manager/notifier.py
- Locks: —
- Depends: T-463
- Blocks: T-471, T-472
- Notes: |
    hass.services.async_call("notify", notify_target, {...}).
    Message : caméra, sévérité, objets détectés.
    Image : URL Frigate (snapshot ou clip).
    Support : tag (collapse), actions (boutons HA Companion), critical (bypass DND).
    html.escape() sur tous les champs dynamiques.

### T-471 | Review T-470

- Status: TODO
- Owner: reviewer
- Scope: custom_components/frigate_event_manager/notifier.py
- Locks: —
- Depends: T-470
- Blocks: T-473
- Notes: —

### T-472 | Tests T-470

- Status: TODO
- Owner: quality-guard
- Scope: tests/
- Locks: —
- Depends: T-470
- Blocks: T-473
- Notes: —

### T-473 | Simplification T-470

- Status: TODO
- Owner: code-simplifier
- Scope: custom_components/frigate_event_manager/notifier.py
- Locks: —
- Depends: T-471, T-472
- Blocks: T-480
- Notes: —

### T-480 | Entités HA — sensor, switch, binary_sensor

- Status: TODO
- Owner: python-architect
- Scope: custom_components/frigate_event_manager/
- Locks: —
- Depends: T-473
- Blocks: T-481, T-482
- Notes: |
    sensor.py : last_severity, last_object, event_count_24h par caméra.
    switch.py : notifications on/off par caméra (PATCH registry).
    binary_sensor.py : motion par caméra (on sur type:new, off sur type:end).
    Toutes les entités : CoordinatorEntity, unique_id fem_{cam}_{key}, has_entity_name=True.

### T-481 | Review T-480

- Status: TODO
- Owner: reviewer
- Scope: custom_components/frigate_event_manager/
- Locks: —
- Depends: T-480
- Blocks: T-483
- Notes: —

### T-482 | Tests T-480

- Status: TODO
- Owner: quality-guard
- Scope: tests/
- Locks: —
- Depends: T-480
- Blocks: T-483
- Notes: —

### T-483 | Simplification T-480

- Status: TODO
- Owner: code-simplifier
- Scope: custom_components/frigate_event_manager/
- Locks: —
- Depends: T-481, T-482
- Blocks: T-490
- Notes: —

### T-490 | Docs — README + architecture.md + tasks.md

- Status: TODO
- Owner: reviewer
- Scope: README.md, docs/architecture.md, docs/tasks.md
- Locks: —
- Depends: T-483
- Blocks: T-499
- Notes: |
    README.md : réécrire entièrement (installation HACS, configuration, entités disponibles).
    docs/architecture.md : réécrire (Python asyncio, flux MQTT → filtres → throttler → notifier → entités).
    docs/tasks.md : archiver les phases Go, repartir propre après migration.

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

### Phase 3 : Filtres (PARTIELLEMENT FAIT en Go — à traduire Python)

- [x] ZoneFilter, LabelFilter, TimeFilter (Go → T-430)
- [ ] ScoreFilter (abandonné)

### Phases 4–5 : Différenciation + HACS (REMPLACÉES par migration Python)

> Toutes les fonctionnalités prévues (multi-canal, présence, services HA, entités natives)
> seront implémentées directement dans l'intégration Python.
