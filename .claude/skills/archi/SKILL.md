---
name: archi
description: Explique l'architecture du projet frigate-event-manager, le flux de donnees MQTT/Frigate, ou le role d'un composant. Utiliser quand on demande "comment ca marche", "c'est quoi X", "explique-moi Y", "comment fonctionne Z", ou avant d'implementer pour comprendre le contexte.
user-invocable: true
argument-hint: "[composant]"
---

# Architecture

L'architecture complete est documentee dans `docs/architecture.md` (diagrammes Mermaid).

## Comment repondre

1. Lire `docs/architecture.md` pour le flux global et les diagrammes
2. Si `$ARGUMENTS` mentionne un composant specifique, lire aussi le fichier source correspondant dans `custom_components/frigate_event_manager/`
3. Si aucun argument, presenter le flux principal :
   - Frigate detecte un objet → publie sur MQTT → coordinator HA recoit le message → FilterChain → Throttler → HANotifier → notification Companion
   - Chaque camera = une ConfigEntry separee avec son propre coordinator et ses 2 entites (switch + binary_sensor)
4. Expliquer avec des termes simples — l'utilisateur apprend en faisant
5. Utiliser des analogies concrets si utile (ex: "le FilterChain c'est comme une liste de conditions IF")
6. Si la question touche un choix d'implementation, citer le fichier et le numero de ligne concerne

## Composants cles

| Composant | Fichier | Role |
| --- | --- | --- |
| Coordinator | `coordinator.py` | Souscrit MQTT, parse payload, maintient CameraState |
| FilterChain | `filter.py` | ZoneFilter + LabelFilter + TimeFilter en sequence ET |
| Throttler | `throttle.py` | Anti-spam cooldown par camera |
| HANotifier | `notifier.py` | Envoie notification HA Companion |
| Config flow | `config_flow.py` | 2 etapes : URL Frigate → selection camera |
| Switch | `switch.py` | Activer/desactiver le traitement par camera |
| BinarySensor | `binary_sensor.py` | Detecte si un evenement est en cours |
