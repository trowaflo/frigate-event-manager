---
name: add-handler
description: Ajouter un nouveau handler d'evenement (notification, integration, action...).
user-invocable: true
argument-hint: "[nom] [description]"
---

# Ajouter un Handler

Un handler Python recoit les evenements Frigate filtres et execute une action (notification, log, integration...).

## Etapes

1. **Creer** la classe handler dans `custom_components/frigate_event_manager/` — methode `handle(event: FrigateEvent)`. Modele : `notifier.py`
2. **Tester** dans `tests/test_$0.py` — cas nominal + erreur.
3. **Brancher** dans le coordinateur (`coordinator.py`) : enregistrer le handler dans la boucle de traitement. Wrapper avec `throttle.py` si besoin.
4. **Config** si necessaire : champs dans `config_flow.py` + constantes dans `const.py`
5. **Verifier** : `.venv/bin/pytest tests/ --cov=custom_components/frigate_event_manager -q`

## Regles

- Ne jamais lever d'exception non geree (logger l'erreur, ne pas bloquer les autres handlers)
- Imports : uniquement depuis `custom_components/frigate_event_manager/`, jamais d'imports circulaires
- Utiliser le coordinateur HA pour acceder aux donnees et aux services Home Assistant
