---
name: dev-replay
description: Envoyer un evenement MQTT de test pour le dev local.
user-invocable: true
argument-hint: "[camera] [severity]"
---

# Dev Replay

Publie un event Frigate de test sur le broker MQTT local.

1. Lancer `task dev:replay` — recupere le dernier event Frigate reel et le republie sur MQTT
2. Les credentials viennent du Keychain macOS (ou `dev/.env` sur Linux) — geres automatiquement par le Taskfile
3. Si `$ARGUMENTS` contient camera ou severity, signaler que `task dev:replay` ne supporte pas ces arguments (il rejoue le dernier event reel tel quel)
4. Indiquer ce que l'utilisateur devrait voir dans les logs de `task dev`
