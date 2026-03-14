---
name: test
description: Lance les tests Go, verifie la couverture, et analyse les resultats.
user-invocable: true
argument-hint: "[package]"
---

# Tests

1. Si `$ARGUMENTS` contient un nom de package, lancer `go test ./internal/.../$ARGUMENTS/ -v -count=1`
2. Sinon lancer `go test ./... -count=1 -coverprofile=coverage.out` puis `go tool cover -func=coverage.out`
3. Lancer ensuite `golangci-lint run ./...` et signaler les erreurs lint
4. Si tests echouent : lire le fichier concerne, analyser, proposer un fix
5. Si couverture < 80% : identifier les fonctions non couvertes
6. Resume concis : passes/echoues + couverture globale + lint OK/KO
