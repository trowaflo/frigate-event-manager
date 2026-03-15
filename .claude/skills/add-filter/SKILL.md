---
name: add-filter
description: Ajouter un nouveau filtre d'evenement (camera, objet, zone...).
user-invocable: true
argument-hint: "[nom] [description]"
---

# Ajouter un Filtre

Un filtre impl `filter.Filter` (methode `IsSatisfied`). Chaine AND : tous doivent passer.

## Etapes

1. **Creer** `internal/core/filter/$0.go`. Modele : `severity.go`. Regle : liste vide = tout passe.
2. **Tester** `internal/core/filter/$0_test.go` — vide, match, no-match.
3. **Brancher** dans `cmd/addon/main.go` : ajouter dans `NewFilterChain(...)`.
4. **Config** : champ dans `config.go` + option dans `config.yaml`.
5. **Verifier** : `go test ./internal/core/filter/ -v` && `go test ./... -count=1`

## Champs filtrables (EventState)

`Camera`, `Severity`, `Data.Objects[]`, `Data.Zones[]`, `Data.SubLabels[]`, `Data.Audio[]`
