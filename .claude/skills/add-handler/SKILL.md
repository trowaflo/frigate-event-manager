---
name: add-handler
description: Ajouter un nouveau handler d'evenement (notification, integration, action...).
user-invocable: true
argument-hint: "[nom] [description]"
---

# Ajouter un Handler

Un handler Python recoit les evenements Frigate filtres et execute une action (notification, log, integration...).

## Etapes

1. **Creer** la classe handler dans `custom_components/frigate_event_manager/` — methode `handle(event: FrigateEvent) -> None`. Modele : `notifier.py`
2. **Tester** dans `tests/test_$ARGUMENTS.py` — cas nominal + erreur + event None.
3. **Brancher** dans le coordinator (`coordinator.py`) : instancier le handler dans `__init__` et appeler `handle(event)` dans la boucle de traitement. Wrapper avec `throttle.py` si anti-spam necessaire.
4. **Config** si necessaire : champs dans `config_flow.py` + constantes dans `const.py`. Champs liste : `str` UI → `_parse_csv()` → `list` dans `async_create_entry`.
5. **Verifier** : `.venv/bin/pytest tests/ --cov=custom_components/frigate_event_manager -q`

## Regles

- Ne jamais lever d'exception non geree — logger l'erreur et continuer (`_LOGGER.exception(...)`)
- `html.escape()` sur tous les champs dynamiques affiches ou envoyes
- Imports : uniquement depuis `custom_components/frigate_event_manager/`, jamais d'imports circulaires
- Tout I/O async : `await hass.services.async_call(...)` — jamais d'appels bloquants
