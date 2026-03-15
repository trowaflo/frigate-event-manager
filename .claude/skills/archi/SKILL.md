---
name: archi
description: Explique l'architecture du projet frigate-event-manager, le flux de donnees MQTT/Frigate, ou le role d'un composant. Utiliser quand on demande "comment ca marche", "c'est quoi X", "explique-moi Y", "comment fonctionne Z", ou avant d'implementer pour comprendre le contexte.
user-invocable: true
argument-hint: "[composant]"
---

# Architecture

L'architecture est documentee dans CLAUDE.md (section Architecture) et `docs/architecture.md`.

## Comment repondre

1. Lis `docs/architecture.md` pour les diagrammes Mermaid complets
2. Si $ARGUMENTS mentionne un composant, lis le code source correspondant dans `internal/`
3. Explique avec des termes simples — l'utilisateur n'est pas developpeur
4. Utilise des analogies du quotidien quand c'est utile
