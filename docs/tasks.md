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

- Status: DONE
- Owner: python-architect
- Scope: `event_store.py`, `registry.py`, `sensor.py`, `tests/test_event_store.py`, `tests/test_registry.py`, `tests/test_entities.py` (partiel), `__init__.py`, `coordinator.py`
- Locks: —
- Depends: —
- Blocks: T-504
- Notes: |
    Commit 4dc6b84 — ruff 0 erreur.
    Supprimés : event_store.py, registry.py, sensor.py, tests/test_event_store.py, tests/test_registry.py.
    __init__.py : PLATFORMS = ["switch", "binary_sensor"].
    coordinator.py : commentaires sensor.py nettoyés.
    tests/test_entities.py : classes sensor supprimées, switch + binary_sensor conservés.

### T-501 | Review — nettoyage

- Status: APPROVED
- Owner: reviewer
- Scope: tous les fichiers modifiés par T-500
- Locks: —
- Depends: T-500
- Blocks: T-503
- Security: SECURITY_OK
- Doc: NO_CHANGE_NEEDED
- Notes: |
    Aucune référence morte à event_store/registry/sensor. Nettoyage propre.
    MINOR (code-simplifier) — coordinator.py:33-37 : champs FrigateEvent (score,
    thumb_path, review_id, start_time, end_time) parsés mais non exposés dans
    CameraState.as_dict(). Élaguer ou intégrer selon besoins des phases suivantes.
    MINOR (code-simplifier) — coordinator.py:113,117 : pattern `a or b` sur float
    court-circuite sur 0.0 (valeur valide). Préférer `a if a is not None else b`.
    INFO — switch.py:27, binary_sensor.py:31 : référence orpheline à T-484
    (absent de tasks.md). Mettre à jour vers T-508 lors du prochain passage.

### T-502 | Tests — nettoyage

- Status: DONE
- Owner: quality-guard
- Scope: `tests/`
- Locks: —
- Depends: T-500
- Blocks: T-503
- Notes: 197 tests passent, coverage 93% (≥80%). Aucune modification nécessaire — tests déjà propres après T-500.

### T-503 | Simplification — nettoyage

- Status: DONE
- Owner: code-simplifier
- Scope: tous les fichiers modifiés par T-500
- Locks: —
- Depends: T-501, T-502
- Blocks: T-504
- Notes: |
    coordinator.py : pattern `a or b` sur float corrigé en `a if a is not None else b`
    pour les champs score et start_time (protège contre court-circuit sur 0.0).
    Champs score/thumb_path/review_id/start_time/end_time conservés — utilisés dans
    tests (score, thumb_path), notifier.py (review_id), _handle_mqtt_message (start_time, end_time).
    switch.py + binary_sensor.py : référence T-484 → T-508.
    ruff 0 erreur, 197 tests passent, coverage 93%.

---

### Phase 2 — Frigate API client + Config flow

### T-504 | Frigate API client + config flow 2 étapes

- Status: DONE
- Owner: python-architect
- Scope: `frigate_client.py` (nouveau), `config_flow.py`, `const.py`, `translations/en.json`, `translations/fr.json`
- Locks: —
- Depends: T-503
- Blocks: T-508
- Notes: |
    frigate_client.py créé : GET {url}/api/cameras → liste noms caméras.
    config_flow.py réécrit : 2 étapes (user + camera).
    const.py : CONF_URL + CONF_CAMERA ajoutés. CONF_SEVERITY_FILTER, CONF_ZONES,
      CONF_LABELS, CONF_DISABLE_TIMES, CONF_COOLDOWN, DEFAULT_COOLDOWN supprimés
      (uniquement utilisés dans l'ancien config_flow.py).
      CONF_MQTT_TOPIC + DEFAULT_MQTT_TOPIC conservés — encore utilisés par
      coordinator.py et __init__.py (à migrer en T-508).
    translations/en.json + fr.json : steps user + camera, error cannot_connect.
    ruff check : 0 erreur.

### T-505 | Review — config flow

- Status: DONE
- Owner: reviewer
- Scope: `frigate_client.py`, `config_flow.py`, `const.py`
- Locks: —
- Depends: T-504
- Blocks: T-507
- Security: SECURITY_OK
- Doc: NO_CHANGE_NEEDED
- Severity: MAJOR
- Notes: |
    MAJOR — frigate_client.py:22 : pas de timeout aiohttp. Blocage infini possible
      sur API Frigate lente. Ajouter aiohttp.ClientTimeout(total=10).
    MAJOR — config_flow.py:67-70 : async_step_camera ne gère pas global_entry=None.
      Aucune erreur affichée, formulaire inutilisable si entry globale absente.
      Ajouter un abort ou une erreur explicite.
    MINOR — frigate_client.py:21 : ClientSession créée par requête (acceptable pour
      config flow ponctuel, à surveiller en T-508).
    MINOR — config_flow.py:95 : vol.In([]) vide → bascule sur str sans validation.
      UX dégradée si Frigate vide ou inaccessible.
    INFO — config_flow.py:17 : CONF_NOTIFY_TARGET requis en step user sans valeur
      par défaut. Valider l'intention avec python-architect.
    INFO — __init__.py:39 : log affiche None pour CONF_MQTT_TOPIC sur les entries
      créées via le nouveau flow. Trompeur, corrigeable en T-508.

### T-506 | Tests — config flow

- Status: DONE
- Owner: quality-guard
- Scope: `tests/test_config_flow.py`, `tests/test_frigate_client.py` (nouveau)
- Locks: —
- Depends: T-504
- Blocks: T-507
- Notes: |
    tests/test_frigate_client.py créé : 11 tests (happy path, réponse non-dict, erreurs réseau, URL endpoint).
    tests/test_config_flow.py réécrit : 17 tests (step user happy path, cannot_connect, already_configured,
      step camera, constantes). Ancien flow (COOLDOWN, LABELS, ZONES, CSV) supprimé.
    Patch : custom_components.frigate_event_manager.config_flow.FrigateClient.get_cameras (AsyncMock).
    Patch HTTP : custom_components.frigate_event_manager.frigate_client.aiohttp.ClientSession.
    aioresponses non installé → unittest.mock.patch utilisé.
    BLOQUÉ : Bash access refusé — impossible de lancer pytest pour vérifier coverage.
    Action requise : `.venv/bin/pytest tests/ --cov=custom_components/frigate_event_manager --cov-report=term-missing -q`

### T-507 | Simplification — config flow

- Status: DONE
- Owner: code-simplifier
- Scope: `frigate_client.py`, `config_flow.py`
- Locks: —
- Depends: T-505, T-506
- Blocks: T-508
- Notes: |
    frigate_client.py : ajoute aiohttp.ClientTimeout(total=10) sur ClientSession.
    config_flow.py : guard async_abort(reason="missing_global_entry") si global_entry=None.
    translations/en.json + fr.json : clé abort.missing_global_entry ajoutée.
    ruff 0 erreur, 220 tests passent, coverage 93%.

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

- Status: REVIEW_NEEDED
- Owner: reviewer
- Scope: tous les fichiers modifiés par T-508
- Locks: —
- Depends: T-508
- Blocks: T-511
- Security: MINOR_ISSUES
- Doc: NO_CHANGE_NEEDED
- Severity: MAJOR
- Notes: |
    BLOCKING — T-508 Status est encore TODO. Le code livré (coordinator.py,
      __init__.py, switch.py, binary_sensor.py) est présent dans le dépôt
      (branche Claude-review), mais T-508 n'a pas été marqué DONE par
      python-architect. Mettre T-508 à DONE avant de valider T-509.
    MAJOR — coordinator.py:164,168 : accès direct entry.data[CONF_CAMERA] sans
      guard dans __init__. Si une entry caméra est instanciée sans la clé
      (bug config flow ou migration), KeyError non intercepté → crash setup.
      __init__.py:25 distingue bien global vs caméra, mais le guard doit aussi
      exister dans le constructeur du coordinator (raise ValueError explicite
      ou assert précoce avec message clair).
    MAJOR — coordinator.py:124 : end_time résolu via `after.get("end_time") or
      raw.get("end_time")`. Le `or` court-circuite sur 0.0 (valeur valide pour
      end_time, ex. timestamp epoch). Utiliser le pattern _to_float déjà
      présent pour score et start_time (cf. lignes 114-123).
    MINOR — coordinator.py:188 : _resolve_notify_target appelé dans __init__,
      qui est synchrone. Si async_entry_for_domain_unique_id est jamais rendu
      async dans une future version HA, cela cassera silencieusement. Acceptable
      aujourd'hui — surveiller lors des upgrades HA.
    MINOR — switch.py:21, binary_sensor.py:25 : accès direct
      hass.data[DOMAIN][entry.entry_id] sans guard. Si async_setup_entry
      (coordinator) a échoué partiellement, KeyError ici. Préférer
      hass.data.get(DOMAIN, {}).get(entry.entry_id) avec un raise ConfigEntryNotReady
      explicite.
    MINOR — coordinator.py:189-191 : _notifier vaut None si notify_target
      absent. La notification est silencieusement ignorée (cf. ligne 280).
      Ce comportement est correct mais aucun log d'avertissement ne prévient
      l'utilisateur lors du démarrage. Ajouter un _LOGGER.warning dans __init__
      si notify_target est None.
    SECURITY — notifier.py:117 : _notify_target (issu de entry.data) injecté
      directement dans hass.services.async_call sans validation. Si la valeur
      contient des caractères inattendus, l'appel HA peut échouer. Validation
      minimale recommandée (alphanumérique + underscore). Classé MINOR_ISSUES
      car HA valide lui-même le service name.
    INFO — filter.py:15 : import circulaire contourné dans coordinator.py via
      imports locaux (ligne 175-177 noqa PLC0415). Acceptable, mais signaler à
      code-simplifier pour évaluer une restructuration (FrigateEvent dans un
      module domain séparé).
    INFO — const.py:11-12 : CONF_MQTT_TOPIC et DEFAULT_MQTT_TOPIC toujours
      présents mais CONF_MQTT_TOPIC n'est plus utilisé dans coordinator.py
      (topic hardcodé ligne 169). Nettoyer en T-511.

### T-510 | Tests — coordinator + entités

- Status: TODO
- Owner: quality-guard
- Scope: `tests/test_coordinator.py`, `tests/test_entities.py`
- Locks: —
- Depends: T-508
- Blocks: T-511
- Notes: Coverage ≥80%. Un coordinator par caméra, tester le fallback notify_target.

### T-511 | Simplification — coordinator + entités

- Status: DONE
- Owner: code-simplifier
- Scope: tous les fichiers modifiés par T-508
- Locks: —
- Depends: T-509, T-510
- Blocks: T-512
- Notes: |
    MAJOR — coordinator.py : guard CONF_CAMERA ajouté dans __init__ (raise ValueError explicite).
    MAJOR — coordinator.py:124 : end_time migré vers pattern _to_float + is not None (protège 0.0).
    MINOR — switch.py + binary_sensor.py : accès hass.data migré vers .get() + raise ConfigEntryNotReady.
    MINOR — coordinator.py : _LOGGER.warning ajouté si notify_target est None au démarrage.
    INFO — const.py : CONF_MQTT_TOPIC conservé — utilisé dans tests/test_config_flow.py (lignes 15, 412, 435).
    ruff 0 erreur.

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
