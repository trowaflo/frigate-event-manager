---
name: add-filter
description: Ajouter un nouveau filtre d'evenement (camera, objet, zone...).
user-invocable: true
argument-hint: "[nom] [description]"
---

# Ajouter un Filtre

Un filtre implemente le protocole `Filter` de `custom_components/frigate_event_manager/filter.py` — methode `apply(self, event: FrigateEvent) -> bool`. Chaine AND via `FilterChain` : tous les filtres doivent accepter pour que l'evenement soit traite.

## Etapes

1. **Creer** la classe dans `custom_components/frigate_event_manager/filter.py` (etendre le fichier existant). Modeles : `ZoneFilter` (multi-valeurs + ordre), `LabelFilter` (ensemble), `TimeFilter` (clock injectable). Regle absolue : **liste vide = tout passe**.
2. **Tester** dans `tests/test_filter.py` — cas vide, match, no-match, edge case (valeur 0.0, None, liste vide).
3. **Brancher** dans le coordinator (`coordinator.py`) : ajouter le filtre dans la `FilterChain(...)` construite a partir de la config.
4. **Config** si necessaire : champ dans `config_flow.py` + constante dans `const.py`. Champs liste : `str` UI → `_parse_csv()` → `list` dans `async_create_entry`.
5. **Verifier** : `.venv/bin/pytest tests/test_filter.py -v`

## Champs filtrables — FrigateEvent (verifie contre coordinator.py)

| Champ | Type | Description |
| --- | --- | --- |
| `type` | `str` | `"new"` \| `"update"` \| `"end"` |
| `camera` | `str` | Nom de la camera |
| `severity` | `str` | `"alert"` \| `"detection"` |
| `objects` | `list[str]` | Objets detectes (ex: `["person", "car"]`) |
| `zones` | `list[str]` | Zones actives (ex: `["jardin", "entree"]`) |
| `score` | `float` | Score de confiance (0.0–1.0) |
| `start_time` | `float` | Timestamp Unix debut |
| `end_time` | `float \| None` | Timestamp Unix fin (None si en cours) |
| `review_id` | `str` | ID Frigate de la review |
| `thumb_path` | `str` | Chemin miniature (peut etre vide) |
