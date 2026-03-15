---
name: add-filter
description: Ajouter un nouveau filtre d'evenement (camera, objet, zone...).
user-invocable: true
argument-hint: "[nom] [description]"
---

# Ajouter un Filtre

Un filtre herite du protocole `Filter` de `custom_components/frigate_event_manager/filter.py` (methode `apply(event: FrigateEvent) -> bool`). Chaine AND : tous doivent passer.

## Etapes

1. **Creer** la classe dans `custom_components/frigate_event_manager/filter.py` (etendre le fichier existant). Modele : `ZoneFilter` ou `LabelFilter`. Regle : liste vide = tout passe.
2. **Tester** dans `tests/test_filter.py` — cas vide, match, no-match.
3. **Brancher** dans le coordinateur ou le point d'entree adequat : ajouter dans la `FilterChain(...)`.
4. **Config** si necessaire : champ dans `config_flow.py` + option dans `custom_components/frigate_event_manager/const.py`.
5. **Verifier** : `.venv/bin/pytest tests/test_filter.py -v`

## Champs filtrables (FrigateEvent)

`camera`, `label`, `zones`, `objects`, `score`, `top_score`, `after`, `before`
