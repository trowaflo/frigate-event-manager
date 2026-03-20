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

### T-518 | Review — Store + binary_sensor silent + sensor timestamp + motion fix

- Status: APPROVED
- Owner: python-architect
- Reviewer: reviewer
- Security: SECURITY_OK
- Doc: DONE
- Severity: MINOR
- Depends: T-516
- Blocks: T-519
- Notes: |
    Toutes les MINORs corrigées en T-519 + commit `1b6cb4e`.
    MINOR Store cleanup → `__init__.py` : `async_remove()` sur subentries supprimées dans `async_unload_entry`.
    MINOR strings.json → "Silent active" (commit `8aa2b58`).
    MINOR `_silent_until` → property `silent_until` exposée ; entités conservent `_silent_until` (compromis tests).
    DOC → `docs/architecture.md` : `SilentUntilSensor` ajouté dans les 4 sections manquantes.

### T-518b | Tests — Store + silent sensors + motion fix

- Status: DONE
- Owner: quality-guard
- Scope: `tests/test_coordinator.py`, `tests/test_entities.py`
- Locks: —
- Depends: T-518
- Blocks: T-519
- Notes: |
    318 tests passent, coverage global 98% (≥80%). 2 tests ajoutés.
    Feature A (Store persistance) : tests existants couvrent restauration non expirée,
      restauration expirée, store vide, sauvegarde lors de activate_silent_mode().
    Feature B (SilentStateSensor + SilentUntilSensor) : tests existants couvrent
      is_on=True/False, native_value datetime UTC / None. Ajout :
      test_is_on_reflecte_mise_a_jour_silent_until — vérifie que is_on reflète
      le changement de coordinator._silent_until sans reload.
    Feature C (_active_reviews) : tests existants couvrent 2 reviews / premier end /
      deuxième end. Ajout : test_review_id_vide_pas_ajoute_a_active_reviews —
      vérifie qu'un review_id="" (falsy) n'est pas ajouté au set.

### T-519 | Simplification + doc — Store + silent sensors

- Status: DONE
- Owner: code-simplifier
- Scope: `coordinator.py`, `binary_sensor.py`, `sensor.py`, `strings.json`, `docs/architecture.md`, `__init__.py`
- Locks: —
- Depends: T-518
- Blocks: T-517
- Notes: |
    Commits : 8aa2b58 + 1b6cb4e — ruff 0 erreur, 318 tests passent, coverage 98%, markdownlint 0 erreur.
    1. coordinator.py : closures `_on_silent_expired` / `_on_silent_expired_restored` fusionnées → méthode de classe (-10 lignes).
    2. coordinator.py : property publique `silent_until: float` exposée.
    3. sensor.py : comparaison `== 0.0` redondante supprimée dans `native_value`.
    4. strings.json : "Silencieux actif" → "Silent active".
    5. `__init__.py` : `async_unload_entry` nettoie les stores des subentries supprimées via `async_remove()`.
    6. docs/architecture.md : `SilentUntilSensor` ajouté dans les 4 sections manquantes.

### T-517 | Notification features — PR

- Status: TODO
- Owner: orchestrator
- Scope: `feat/python-migration` → `main`
- Locks: —
- Depends: T-519, T-523c, T-525, T-524
- Blocks: —
- Notes: |
    Vérifier : pytest vert, coverage ≥80%, ruff 0 erreur, markdownlint 0 erreur.
    Validation humaine obligatoire avant merge.

### T-520 | Zones + labels + heures en multi-select depuis Frigate

- Status: DONE
- Owner: python-architect
- Reviewer: reviewer
- Security: SECURITY_OK
- Doc: UPDATE_NEEDED
- Severity: MINOR
- Locks: —
- Depends: T-519
- Blocks: —
- Notes: |
    frigate_client.py : `get_camera_config(camera)` → zones + labels depuis /api/config.
    config_flow.py : flow 2 étapes (user=caméra, configure=multi-selects).
      `_build_configure_schema()` centralise le schéma configure/reconfigure.
      `_parse_configure_input()` gère le fallback CSV si zones/labels vides.
      reconfigure : fetch Frigate + valeurs pré-sélectionnées.
    strings.json + fr.json + en.json : step "configure" ajoutée.
    325 tests passent, coverage 97%, ruff 0 erreur, markdownlint 0 erreur.
    Commits : 8a0a4b1, eaff1c9, 9b0ef40, 25ec9f9.

    --- SIMPLIFICATION (code-simplifier) — commit b91fd5c ---
    frigate_client.py : `_fetch_frigate_config()` extrait — `get_cameras` et
      `get_camera_config` délèguent au helper (bloc ClientSession dupliqué supprimé).
    config_flow.py : `_parse_csv_int` (fonction morte) supprimée.
    config_flow.py : `_frigate_unreachable` tracke l'échec réseau vs caméra sans zones.
      `async_step_configure` passe `description_placeholders={"warning": "..."}` uniquement
      si Frigate était inaccessible — le formulaire affiche le warning inline.
    strings.json + fr.json + en.json : `"description": "{warning}"` ajoutée au step configure.
    326 tests passent, coverage 98%, ruff 0 erreur.
    DOC UPDATE_NEEDED — docs/architecture.md:199 : section "saisis en CSV" → mettre à jour
      pour refléter le mode primaire multi-select (CSV = fallback). À corriger avant T-517.

### T-520b | Tests — Zones + labels + heures multi-select (quality-guard)

- Status: DONE
- Owner: quality-guard
- Scope: `tests/test_frigate_client.py`, `tests/test_config_flow.py`
- Locks: —
- Depends: T-520
- Blocks: —
- Notes: |
    328 tests passent, coverage global 98% (≥80%). 3 tests ajoutés.
    `frigate_client.py` : 100% — ajouts :
      `test_get_camera_config_reponse_non_dict_retourne_vide` (branche ligne 85).
      `test_get_camera_config_avec_credentials_appelle_login` (branche login lignes 70-77).
    `config_flow.py` : 100% — ajout :
      `test_subentry_erreur_reseau_sur_step_configure_fallback` (fallback lignes 442-445
      de `async_step_configure` lors d'une erreur réseau sur `get_camera_config` en ajout caméra).
    Commit : 68c7e91.

---

## Phase 6 — Filtres & Notifications avancées

### T-521 | SelectSelector LIST + clarification zones vides

- Status: APPROVED
- Owner: python-architect
- Reviewer: reviewer
- Security: SECURITY_OK
- Doc: NO_CHANGE_NEEDED
- Severity: MINOR
- Locks: —
- Depends: T-520
- Blocks: —
- Notes: |
    `SelectSelectorMode.LIST` appliqué sur zones, labels, severity, tap_action,
    disabled_hours. Conforme.
    Fallback `str` (champ texte libre) sur zones/labels vides documenté et attendu.
    MINOR — `strings.json:144` : `"name": "Reprise des notifications"` est du français
      dans le fichier de référence anglais. Doit être `"Notifications resume"` pour
      cohérence avec `translations/en.json`. À corriger dans le prochain passage.

### T-522 | Filtre severity — Alert / Detection

- Status: APPROVED
- Owner: python-architect
- Reviewer: reviewer
- Security: SECURITY_OK
- Doc: NO_CHANGE_NEEDED
- Severity: MINOR
- Locks: —
- Depends: T-521
- Blocks: —
- Notes: |
    `SeverityFilter` respecte la convention liste vide = tout accepter (`filter.py:118`).
    `DEFAULT_SEVERITY = ["alert", "detection"]` : les deux par défaut, comportement
      plug & play cohérent.
    `coordinator.py:75` : fallback `DEFAULT_SEVERITY` si clé absente — correct.
    `strings.json` : entièrement en anglais, options selector bien formées. Conforme.
    `translations/en.json` : identique à `strings.json` en structure. Conforme.
    `translations/fr.json` : section `severity` traduite. Conforme.
    Reconfigure (`config_flow.py:507`) : valeur existante passée comme `default_severity`. Conforme.
    Tests `test_filter.py` : 12 cas `TestSeverityFilter` couvrent liste vide, alert, detection,
      severity inconnue, intégration dans `FilterChain`. Complets.
    Tests `test_config_flow.py` : cas severity présents dans les tests de création/reconfigure.
    MINOR — `strings.json:144` : `"name": "Reprise des notifications"` — français dans
      fichier de référence anglais (hérité T-519, hors scope T-522). À corriger au prochain passage.

### T-522b | Tests — filtre severity (quality-guard)

- Status: DONE
- Owner: quality-guard
- Scope: `tests/test_filter.py`, `tests/test_config_flow.py`
- Locks: —
- Depends: T-522
- Blocks: —
- Notes: |
    340 tests passent, coverage global 98% (≥80%). Aucun test ajouté — coverage déjà complète.
    `domain/filter.py` : 100% — `TestSeverityFilter` (10 cas) couvre liste vide = tout accepter,
      `alert` seul, `detection` seul, les deux, severity inconnue bloquée.
    `FilterChain` + `SeverityFilter` : couvert par `test_chaine_avec_severity_filter`.
    `config_flow.py` : 100% — `CONF_SEVERITY` stocké comme `list[str]` dans
      `test_subentry_cree_camera_avec_severity_alert` et valeur par défaut dans
      `test_subentry_cree_camera_severity_defaut`. Reconfigure pré-sélectionnée via
      `existing_severity` → `default_severity` dans `_build_configure_schema()` (ligne 507-519),
      chemin exercé par `test_subentry_reconfigure_met_a_jour_donnees`.

### T-521+T-522 | Simplification — SelectSelectorMode.LIST + SeverityFilter (code-simplifier)

- Status: DONE
- Owner: code-simplifier
- Scope: `domain/filter.py`
- Locks: —
- Depends: T-521, T-522, T-522b
- Blocks: —
- Notes: |
    `domain/filter.py` : `SeverityFilter._severities` → `SeverityFilter.severities` (attribut public)
      pour uniformiser avec `ZoneFilter.zone_multi`, `LabelFilter.labels`, `TimeFilter.disabled_hours`.
      Docstring enrichie sur le pattern liste vide = tout accepter.
    `config_flow.py` : aucune modification — code déjà propre, pas de duplication.
    `strings.json` : MINOR T-521/T-522 déjà corrigée (ligne 144 = "Notifications resume" en anglais).
    Commit : 514cd30 — ruff 0 erreur, 340 tests passent, coverage 98%.

---

### T-523 | Notifications critiques — template Jinja2 sur plage horaire

- Status: DONE
- Owner: python-architect
- Priority: P1
- Scope: `const.py`, `coordinator.py`, `notifier.py`, `config_flow.py`, `strings.json`, `translations/`
- Locks: —
- Depends: T-522
- Blocks: —
- Notes: |
    CONF_CRITICAL_TEMPLATE ajouté dans const.py.
    coordinator.py : import template_helper, `_is_critical()` évalue le template Jinja2
      avec variables camera/severity/objects/zones/start_time. Passe critical=True/False
      aux deux chemins notify (immédiat + debounce). Template invalide → False + warning log.
    notifier.py : `async_notify(*, critical=False)` — si critical=True et pas persistent_notification :
      push.sound.critical=1 + volume=1.0 (iOS) + channel="frigate_critical" (Android).
    config_flow.py : champ TemplateSelector dans `_build_configure_schema` + `_parse_configure_input`.
      default_critical_template pré-rempli dans `async_step_reconfigure`.
    strings.json + fr.json + en.json : data + data_description pour configure et reconfigure.
    347 tests passent, coverage 98%, ruff 0 erreur.

### T-523b | Review — notifications critiques

- Status: APPROVED
- Owner: reviewer
- Reviewer: reviewer
- Security: SECURITY_OK
- Doc: NO_CHANGE_NEEDED
- Severity: MINOR
- Depends: T-523
- Blocks: T-523c, T-523d
- Notes: |
    SECURITY_OK — évaluation template Jinja2 via `template_helper.Template.async_render(parse_result=False)`.
      Variables issues du payload MQTT interne, pas d'entrée utilisateur directe. Comparaison via
      `str(result).strip().lower() == "true"` — pas d'évaluation récursive. `html.escape()` appliqué
      sur tous les champs dynamiques dans `notifier.py:98-110`. Aucun secret loggé.
    MINOR — `coordinator.py:304` + `tests/test_coordinator.py` (TestDebounceSend) : le chemin debounce
      appelle `_is_critical(grouped_event)` mais aucun test ne vérifie que `critical=True/False` est
      correctement transmis à `async_notify` dans ce chemin. Les tests existants vérifient uniquement
      `assert_called_once()` sans inspecter le kwarg `critical`. À couvrir en T-523c ou T-523d (quality-guard).
    INFO — `coordinator.py:300-304` : `_debounce_send` évalue `_is_critical` sur l'événement synthétique
      dont `severity` est celle du dernier `update` reçu (pas nécessairement la plus haute). Comportement
      implicite, acceptable mais non documenté. Ajouter un commentaire en T-523c.
    Traductions : strings.json / en.json / fr.json cohérentes. Clés `critical_template` présentes dans
      `data` et `data_description` des steps configure et reconfigure. Aucune clé manquante.
    Config flow : `TemplateSelector()` conforme, pré-remplissage reconfigure correct (`None` → `""`).
      `_parse_configure_input:249` normalise correctement la valeur vide vers `None`.

### T-523c | Simplification — notifications critiques

- Status: DONE
- Owner: code-simplifier
- Scope: `coordinator.py`, `tests/test_coordinator.py`
- Locks: —
- Depends: T-523b, T-523d
- Blocks: —
- Notes: |
    coordinator.py : commentaire ajouté dans `_debounce_send` expliquant que `_is_critical`
      est évalué sur `grouped_event` dont la severity est celle du dernier update reçu
      (comportement intentionnel, cohérent avec le reste du debounce).
    tests/test_coordinator.py (TestDebounceSend) : test ajouté
      `test_debounce_send_transmet_critical_true_a_async_notify` — configure
      `_critical_template="true"`, déclenche `_debounce_send()`, vérifie que
      `notifier.async_notify` a été appelé avec `critical=True`.
    ruff 0 erreur, 348 tests passent, coverage 98%.

### T-523d | Tests — notifications critiques (quality-guard)

- Status: DONE
- Owner: quality-guard
- Scope: `tests/test_coordinator.py`, `tests/test_notifier.py`, `tests/test_config_flow.py`
- Locks: —
- Depends: T-523b
- Blocks: T-523c
- Notes: |
    351 tests passent, coverage global 98% (≥80%). 3 tests ajoutés, 2 corrections ruff.
    Cas couverts (tous les 8 demandés) :
    1-4. _is_critical (sans template, vrai, faux, invalide) — existaient déjà (TestIsCritical).
    5. Chemin immédiat debounce=0 + critical=True → async_notify(critical=True) — AJOUTÉ.
    6. Chemin debounce + critical=True → async_notify(critical=True) — existait (T-523c).
    7-9. notifier critical=True/False/persistent_notification — existaient déjà.
    10. config_flow CONF_CRITICAL_TEMPLATE sauvegardé en création subentry — AJOUTÉ.
    11. config_flow CONF_CRITICAL_TEMPLATE pré-rempli en reconfigure — AJOUTÉ.
    Corrections ruff (test_notifier.py) : import pytest inutilisé supprimé, variable calls inutilisée.

---

### T-525 | Exemples Jinja2 pour titre et message de notification

- Status: DONE
- Owner: python-architect
- Priority: P1
- Scope: `strings.json`, `translations/fr.json`, `translations/en.json`, `config_flow.py`
- Locks: —
- Depends: T-522
- Blocks: —
- Notes: |
    Variables disponibles dans les templates : `camera`, `severity`, `objects` (list),
    `zones` (list), `start_time` (timestamp).
    Exemples concrets à afficher comme `description_placeholders` ou placeholder dans le champ :
    Titre : `"🚨 {{ camera | title }} — {{ objects | join(', ') }}"`
    Message : `"{{ severity | upper }} à {{ start_time | timestamp_custom('%H:%M') }}{% if zones %} · {{ zones | join(', ') }}{% endif %}"`
    Présenter comme texte d'aide sous le champ (HA `description` dans translations).
    Documenter les variables dans `docs/architecture.md`.

### T-524 | Entités de réglage — number / select / text par caméra

- Status: TODO
- Owner: python-architect
- Priority: P2
- Scope: `number.py` (nouveau), `select.py` (nouveau), `text.py` (nouveau), `config_flow.py`, `coordinator.py`, `__init__.py`
- Locks: —
- Depends: T-523
- Blocks: —
- Notes: |
    Objectif : sortir les paramètres de réglage du config flow, les exposer comme entités HA.
    Entités par caméra (modifiables depuis le dashboard, utilisables en automatisation) :
    `number.cooldown` (0-3600s), `number.debounce` (0-60s),
    `select.severity_filter` (Alert/Detection/Les deux),
    `select.tap_action` (clip/snapshot/preview),
    `text.critical_template` (Jinja2),
    `text.notif_title` (template titre),
    `text.notif_message` (template message).
    Config flow ne garderait que : caméra, cible notification (notify_target).
    Migration : lire les valeurs existantes depuis subentry.data → initialiser les entités.
    Impact majeur : nécessite review architecture + migration subentry.
    PLATFORM : ajouter `"number"`, `"select"`, `"text"` à `PLATFORMS` dans `__init__.py`.

### T-526 | Logo de l'intégration

- Status: TODO (choix humain requis)
- Owner: —
- Priority: P2
- Scope: `custom_components/frigate_event_manager/icon.png`, `hacs.json`
- Locks: —
- Depends: —
- Blocks: —
- Notes: |
    HA affiche `custom_components/frigate_event_manager/icon.png` dans la page Intégrations.
    HACS affiche l'image référencée dans `hacs.json` ("icon": "...", optionnel).
    Taille recommandée : 256×256px ou 512×512px, fond transparent, format PNG.
    Deux options à présenter à l'utilisateur pour validation avant implémentation :
    Option 1 — Généré SVG→PNG : icône caméra stylisée + éclair/alerte, palette HA (bleu #03A9F4).
    Option 3 — Adapté Frigate : logo Frigate officiel (caméra verte) retravaillé aux couleurs FEM.
    Action requise : présenter les deux visuels à l'utilisateur → valider → placer le fichier.

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
