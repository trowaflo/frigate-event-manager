---
name: lint
description: Lance ruff (Python) et markdownlint (Markdown), affiche les erreurs et les corrige automatiquement si possible.
user-invocable: true
argument-hint: "[--fix]"
---

# Lint

Verifie la qualite du code Python et des fichiers Markdown.

## Etapes

1. Lancer ruff sur le repo entier :
   - Si `$ARGUMENTS` contient `--fix` : `.venv/bin/ruff check --fix .`
   - Sinon : `.venv/bin/ruff check .`
2. Lancer markdownlint sur tous les Markdown : `markdownlint-cli2 '**/*.md' '!.venv/**'`
3. Pour chaque erreur ruff restante (non auto-corrigeable) : indiquer le fichier, la ligne, la regle, et proposer la correction minimale
4. Pour chaque erreur markdownlint : indiquer le fichier et la ligne, corriger directement si l'erreur est triviale (espaces, ligne vide manquante, etc.)
5. Resume : `X erreurs ruff, Y erreurs markdown` — ou `Lint OK` si zero erreur

## Regles

- ruff scanne le repo entier (`.`) pour être identique à la CI — ne jamais restreindre à `custom_components/`
- Ne pas supprimer des regles ruff avec `# noqa` sans explication — corriger le code
- Si une erreur ruff necessite un choix architectural (ex: refactor d'import circulaire) → expliquer et laisser la decision a l'utilisateur
