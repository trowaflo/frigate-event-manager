---
name: dev-replay
description: Envoyer un evenement MQTT de test pour le dev local.
user-invocable: true
argument-hint: "[camera] [severity]"
---

# Dev Replay

Publie un event Frigate de test sur le broker MQTT local.

1. Lire `dev/options.json` pour recuperer broker URL, topic, credentials
2. Verifier que `mosquitto_pub` est installe
3. Publier un message `frigate/reviews` avec camera=$0 (defaut: "test_camera"), severity=$1 (defaut: "alert"), timestamp=now, objects=["person"]
4. Indiquer ce que l'utilisateur devrait voir dans les logs
