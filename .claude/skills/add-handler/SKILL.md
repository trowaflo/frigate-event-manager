---
name: add-handler
description: Ajouter un nouveau handler d'evenement (notification, integration, action...).
user-invocable: true
argument-hint: "[nom] [description]"
---

# Ajouter un Handler

Un handler impl `ports.EventHandler` et recoit les events Frigate filtres.

## Etapes

1. **Creer** `internal/adapter/$0/handler.go` — struct + `HandleEvent()`. Modele : `debughandler/handler.go`
2. **Tester** `internal/adapter/$0/handler_test.go` — cas nominal + erreur. Modele : `debughandler/handler_test.go`
3. **Brancher** dans `cmd/addon/main.go` : `multi.Add("$0", ...)`. Wrapper avec `throttle.New()` si besoin.
4. **Config** si necessaire : champs dans `config.go` + options dans `config.yaml`
5. **Verifier** : `go build ./...` && `go test ./... -count=1`

## Regles

- Ne jamais bloquer les autres handlers (retourner erreur, pas panic)
- Imports : uniquement `domain` et `core/ports`, jamais d'autres adapters
- Utiliser `ports.MediaSigner` pour les URLs media
