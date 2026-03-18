---
name: add-handler
description: Ajouter un nouveau handler d'evenement (notification, integration, action...).
user-invocable: true
argument-hint: "[nom] [description]"
---

# Ajouter un Handler

Un handler Python recoit les evenements Frigate filtres et execute une action (notification, log, integration...).

## Etapes

1. **Port d'abord** : declarer l'interface dans `custom_components/frigate_event_manager/domain/ports.py` avant d'ecrire l'adaptateur. Modele : `NotifierPort` (async), `EventSourcePort` (retourne callable).
2. **Creer** la classe adaptateur dans `custom_components/frigate_event_manager/` — methode correspondant au port declare. Modele : `notifier.py`, `ha_mqtt.py`
3. **Tester** dans `tests/test_$ARGUMENTS.py` — cas nominal + erreur + event None.
4. **Brancher** dans le coordinator (`coordinator.py`) : injecter via le port dans `__init__`, appeler dans la boucle de traitement. Wrapper avec `throttle.py` si anti-spam necessaire.
5. **Config** si necessaire : champs dans `config_flow.py` + constantes dans `const.py`. Champs liste : `str` UI → `_parse_csv()` → `list` dans `async_create_entry`.
6. **Verifier** : `.venv/bin/pytest tests/ --cov=custom_components/frigate_event_manager -q`

## Regles

- Ne jamais lever d'exception non geree — logger l'erreur et continuer (`_LOGGER.exception(...)`)
- `html.escape()` sur tous les champs dynamiques affiches ou envoyes
- Imports : uniquement depuis `custom_components/frigate_event_manager/`, jamais d'imports circulaires
- Tout I/O async : `await hass.services.async_call(...)` — jamais d'appels bloquants
