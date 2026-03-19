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
    `__init__.py` : PLATFORMS = ["switch", "binary_sensor"].
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
    tests (score, thumb_path), notifier.py (review_id), `_handle_mqtt_message` (start_time, end_time).
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
      coordinator.py et `__init__.py` (à migrer en T-508).
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
    INFO — `__init__.py`:39 : log affiche None pour CONF_MQTT_TOPIC sur les entries
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

- Status: DONE
- Owner: python-architect
- Scope: `coordinator.py`, `switch.py`, `binary_sensor.py`, `__init__.py`, `notifier.py`, `filter.py`, `throttle.py`
- Locks: —
- Depends: T-507
- Blocks: T-512
- Notes: Coordinator par caméra unique, fallback notify_target, 2 entités par entry.

### T-509 | Review — coordinator + entités

- Status: APPROVED
- Owner: reviewer
- Scope: tous les fichiers modifiés par T-508
- Locks: —
- Depends: T-508
- Blocks: T-511
- Security: MINOR_ISSUES
- Doc: NO_CHANGE_NEEDED
- Severity: MAJOR
- Notes: Corrections appliquées en T-511. Review terminée.

### T-510 | Tests — coordinator + entités

- Status: DONE
- Owner: quality-guard
- Scope: `tests/test_coordinator.py`, `tests/test_entities.py`
- Locks: —
- Depends: T-508
- Blocks: T-511
- Notes: 225 tests, coverage 95%.

### T-511 | Simplification — coordinator + entités

- Status: DONE
- Owner: code-simplifier
- Scope: tous les fichiers modifiés par T-508
- Locks: —
- Depends: T-509, T-510
- Blocks: T-512
- Notes: Guard CONF_CAMERA, end_time via `_to_float`, ConfigEntryNotReady, warning notify_target. ruff 0 erreur.

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

---

## Phase 5 — Gestion avancée des notifications

### T-513 | Notification features — implémentation

- Status: DONE
- Owner: python-architect
- Scope: `const.py`, `coordinator.py`, `notifier.py`, `config_flow.py`, `__init__.py`, `button.py` (nouveau), `strings.json`, `translations/fr.json`, `translations/en.json`
- Locks: —
- Depends: —
- Blocks: T-514, T-515
- Notes: |
    7 features implémentées — ruff 0 erreur, 232 tests passent, coverage 82%.
    1. CONF_COOLDOWN + DEFAULT_THROTTLE_COOLDOWN dans subentry config flow (NumberSelector 0-3600s)
       coordinator : Throttler(cooldown=subentry.data.get(CONF_COOLDOWN, DEFAULT_THROTTLE_COOLDOWN))
    2. CONF_DEBOUNCE (0-60s) dans const.py + subentry flow
       coordinator : `_debounce_task`, `_pending_objects`, `_pending_event`
       _debounce_send() avec dataclasses.replace() pour event synthétique groupé
       Sur `end` : cancel task + throttler.release(camera)
    3. notifier.py : "group": f"frigate-{html.escape(event.camera)}" pour non-persistent_notification
    4. Condition élargie à type in ("new", "update") dans coordinator._handle_mqtt_message
    5. CONF_SILENT_DURATION (0-480 min) + DEFAULT_SILENT_DURATION=30 dans const.py + subentry flow.
       button.py : SilentButton, unique_id `fem_{cam}_silent`.
       coordinator : `activate_silent_mode()` + `async_call_later`, `_silent_until` check.
       "button" ajouté à PLATFORMS dans `__init__.py`.
    6. `async_step_notify` supprimé, VERSION=3 MINOR=1.
       `async_migrate_entry` v2 vers v3 : supprime `notify_target` de `entry.data`.
       `__init__.py` : fallback PERSISTENT_NOTIFICATION.
       strings.json + fr.json + en.json mis à jour : step notify supprimé, cooldown/debounce/silent_duration ajoutés.
    7. persistent_notification : liens markdown Clip, Snapshot, Preview dans message, pas de data enrichie.

### T-514 | Notification features — review (round 2 — commits 963da2d et suivants)

- Status: APPROVED
- Owner: reviewer
- Reviewer: reviewer
- Security: SECURITY_OK
- Doc: UPDATE_NEEDED
- Severity: MINOR
- Depends: T-513
- Blocks: T-516
- Notes: |
    Round 1 (T-513 initial) :
    MINOR — coordinator.py:106-110 : async_call_later retourne un callable d'annulation
      non stocké. Si async_stop() est appelé avant l'expiration du timer silent mode
      (jusqu'à 480 min), la référence self dans la lambda maintient le coordinator en mémoire.
      Stocker le cancel callback et l'appeler dans async_stop().
      → CORRIGÉ : _cancel_silent stocké et appelé dans async_stop() (coordinator.py:133-135).
    MINOR — notifier.py:122-126 : les URLs dans les liens markdown persistent_notification
      ne sont pas protégées contre les caractères spéciaux Markdown. Angle bracket syntax
      recommandée.
      → CORRIGÉ : syntax [Clip](<url>) appliquée.
    INFO — docs/architecture.md désynchronisé : button.py (SilentButton) absent du
      diagramme entités, de la table adaptateurs entrants et de la séquence démarrage.
      PLATFORMS dans la séquence affiche encore ["switch", "binary_sensor"].
      → NON CORRIGÉ : toujours absent. Correction requise avant T-517.
    INFO — manifest.json version="2.0.0" non incrémentée.
      → CORRIGÉ : version="2.1.0" dans manifest.json.

    Round 2 (review commits feat/cooldown-debounce-silent) :
    MINOR — coordinator.py:176-179 : sur le chemin sans debounce (debounce=0),
      throttler.record() est appelé via async_create_task avant que async_notify() soit
      résolu. Si la notification échoue (exception), le cooldown est quand même enregistré
      et les events suivants sont droppés silencieusement pendant toute la durée du cooldown.
      Le chemin debounce (_debounce_send) est correct (record() après await).
      A corriger en T-516 : déplacer record() dans une coroutine englobant async_notify().
    MINOR — coordinator.py:112 : après expiration naturelle du timer silent, _cancel_silent
      n'est pas remis à None dans la lambda. Le callable expired reste référencé. Un appel
      ultérieur à activate_silent_mode() appellera _cancel_silent() sur un callable inopérant
      (sans effet fonctionnel, mais état incohérent). A corriger en T-516 : la lambda doit
      aussi remettre _cancel_silent à None.
    MINOR — `__init__.py`:55-58 : async_migrate_entry retourne True pour les versions non
      gérées (>3). Convention HA : retourner False pour signaler échec de migration sur
      version inconnue, afin d'éviter le chargement avec données incompatibles (downgrade).
      A corriger en T-516.
    INFO — `__init__.py`:57 : "Migration v2 -> v3 terminee" — accent manquant sur "terminée".
    DOC — docs/architecture.md : button.py (SilentButton) toujours absent du diagramme
      entités (ligne 165-170), de la table adaptateurs entrants (ligne 60), et de la
      séquence démarrage (ligne 184, affiche "switch / binary_sensor" au lieu de
      "switch / binary_sensor / button"). A corriger avant T-517.

### T-515 | Notification features — tests

- Status: DONE
- Owner: quality-guard
- Scope: `tests/test_coordinator.py`, `tests/test_config_flow.py`, `tests/test_init.py` (nouveau), `tests/test_ha_mqtt.py` (nouveau)
- Locks: —
- Depends: T-513
- Blocks: T-516
- Notes: |
    289 tests passent, coverage global 99% (≥80%). 0 erreur ruff.
    Ajouts : test_coordinator.py (TestSilentModeAvance 4 tests, `_cancel_silent` stocké,
    double activation, async_stop). tests/test_init.py nouveau 12 tests (migrate v2→v3,
    setup_entry, unload_entry). tests/test_ha_mqtt.py nouveau 3 tests. tests/test_config_flow.py
    17 tests (csv, reconfigure, invalid_auth).
    Lignes résiduelles : `__init__.py`:135 (_async_reload_entry — reload HA complet non
    testable unitairement), binary_sensor/button/switch:22-23 (platform async_setup_entry).

### T-516 | Notification features — simplification

- Status: DONE
- Owner: code-simplifier
- Scope: `coordinator.py`, `__init__.py`, `docs/architecture.md`
- Locks: —
- Depends: T-514, T-515
- Blocks: T-517
- Notes: |
    coordinator.py : _notify_and_record() — record() déplacé après await async_notify()
      pour éviter le cooldown en cas d'échec de notification (chemin debounce=0).
    coordinator.py : _on_silent_expired() — _cancel_silent remis à None après expiration
      naturelle du timer silent mode (état cohérent + libération de référence).
    `__init__.py` : async_migrate_entry — return False sur version inconnue (>3),
      convention HA pour bloquer le chargement avec données incompatibles.
    `__init__.py` : accent corrigé "terminée".
    docs/architecture.md : button.py / SilentButton ajouté dans le diagramme entités,
      la table adaptateurs entrants, le diagramme entités par caméra (unique_id fem_{cam}_silent),
      et la séquence de démarrage (PLATFORMS = switch / binary_sensor / button).
    ruff 0 erreur, 289 tests passent, coverage 98% (≥80%). markdownlint architecture.md 0 erreur.

### T-517 | Notification features — PR

- Status: TODO
- Owner: orchestrator
- Scope: `feat/python-migration` → `main`
- Locks: —
- Depends: T-516
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
