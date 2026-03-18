---
name: dev-replay
description: Envoyer un evenement MQTT de test pour le dev local.
user-invocable: true
argument-hint: "[camera] [label] [severity]"
---

# Dev Replay

Publie un evenement Frigate synthetique sur le broker MQTT local pour tester l'integration sans Frigate reel.

## Prerequis

Verifier que `mosquitto_pub` est disponible (`which mosquitto_pub`) et qu'un broker MQTT tourne localement.

## Payload Frigate standard

```bash
mosquitto_pub \
  -h localhost -p 1883 \
  -t "frigate/reviews" \
  -m '{
    "type": "new",
    "after": {
      "camera": "$ARGUMENTS_CAMERA",
      "severity": "alert",
      "objects": ["person"],
      "current_zones": ["jardin"],
      "score": 0.92,
      "id": "test-review-001",
      "start_time": 1700000000.0,
      "thumb_path": "/media/frigate/test.jpg"
    }
  }'
```

## Etapes

1. Si `$ARGUMENTS` contient un nom de camera, utiliser ce nom dans le champ `camera` du payload
2. Si `$ARGUMENTS` contient un label (ex: `car`, `dog`), l'utiliser dans `objects`
3. Si `$ARGUMENTS` contient une severity (`alert` ou `detection`), l'utiliser dans `severity`
4. Construire la commande `mosquitto_pub` avec le payload adapte et l'executer
5. Indiquer ce que l'utilisateur devrait voir : le coordinator doit logger la reception de l'evenement, le binary_sensor doit passer a `on`, le compteur d'evenements doit incrementer

## Valeurs par defaut

- `camera` : `jardin`
- `label` : `person`
- `severity` : `alert`
- `topic` : `frigate/reviews` (valeur de `DEFAULT_MQTT_TOPIC` dans `const.py`)

## Si mosquitto_pub absent

Proposer d'installer : `sudo apt install mosquitto-clients` (Linux) ou `brew install mosquitto` (macOS).
