# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Workflow

L'utilisateur n'est pas developpeur. Il apprend en faisant.

### 1. CCOF — Cadrer la demande

Quand l'utilisateur fait une demande vague ou incomplete, reformule-la en CCOF avant d'agir :

- **C**ontexte : etat actuel, ou on en est
- **C**ontraintes : limites techniques, regles a respecter
- **O**bjectif : ce qu'on veut obtenir concretement
- **F**ormat : forme du livrable attendu (code, doc, schema...)

Propose la reformulation a l'utilisateur pour validation. S'il valide ou ajuste, passe a l'etape suivante. Ecrire des specs detaillees en amont pour reduire l'ambiguite.

### 2. Plan — Planifier si non-trivial

Si la tache fait plus de 2 etapes ou implique des choix d'architecture : planifier avant de coder. Presenter le plan a l'utilisateur pour validation. Planifier aussi les etapes de verification, pas uniquement le code.

### 3. Execute — Coder

Simplicite d'abord. Changements minimaux. Pas d'over-engineering. Si ca deraille (erreurs inattendues, approche qui ne fonctionne pas) : **STOP, re-planifier immediatement**. Ne pas insister sur une approche qui coince.

Si la solution est complexe pour rien : trouver plus simple. Si la solution est simple mais tricky : trouver plus fiable. Eviter le bricolage.

### 4. Verify — Prouver que ca marche

Avant de declarer une tache terminee :

- `go build ./...` (compile)
- `go test ./... -count=1` (tests passent)
- Diff comportement entre avant/apres si pertinent
- Montrer le resultat concret (log, output, diff)

Ne jamais declarer "termine" sans preuve que ca fonctionne. Se challenger : est-ce qu'on aurait pu faire plus optimal, sans over-engineering ?

### 5. Fix — Autonome sur les bugs

Si un test echoue ou un build casse : corriger sans demander a l'utilisateur comment faire. Lire les logs, trouver la cause racine, fixer, re-verifier. Zero context-switching pour l'utilisateur. Fixer les tests CI qui echouent sans qu'on te le demande.

### 6. Learn — Capitaliser

Apres **toute** correction de l'utilisateur :

- Mettre a jour les fichiers memory avec le pattern identifie
- Ecrire une regle concrete qui empeche la meme erreur
- Iterer sur ces regles jusqu'a ce que le taux d'erreur baisse
- Relire les fichiers memory au demarrage de chaque session

### Suivi inter-sessions

Le contexte est perdu entre les sessions et entre les subagents. Utiliser `docs/tasks.md` comme memoire persistante partagee :

- Avant de commencer : lire `docs/tasks.md` pour reprendre ou on en etait
- Pendant : marquer les items termines, ajouter les items decouverts
- A la fin : mettre a jour avec l'etat actuel et les prochaines etapes
- Les subagents doivent lire `docs/tasks.md` avant d'agir si le contexte est necessaire

### Subagents

Utiliser les subagents generalement pour garder le contexte principal propre :

- Deleguer la recherche, l'exploration, et l'analyse parallele aux subagents
- Pour les problemes complexes, lancer plusieurs subagents en parallele
- Un sujet par subagent pour une execution focalisee

## Project

Home Assistant addon en Go. Ecoute les events Frigate via MQTT, filtre, et dispatch vers N handlers (notifications HA, MQTT Discovery, debug). Container Docker `scratch` avec un seul binaire.

## Commands

```bash
task test                  # tests + coverage ≥80%
task build                 # docker build
task dev                   # run local (creds macOS Keychain via task dev:init)
task dev:replay            # republier dernier event Frigate sur MQTT
```

```bash
go test ./internal/core/registry/ -v -count=1  # un seul package
go build ./...                                  # compile check
golangci-lint run ./...                         # lint
```

## Architecture

Hexagonal : `domain` → `core` (ports/interfaces) → `adapters` (systemes externes).

Diagrammes complets : `docs/architecture.md` (Mermaid, lisible sur GitHub).
Maquettes interactives : `maquette/architecture.html` (ouvrir dans un navigateur).

```text
MQTT Broker → Subscriber → MessageHandler → Processor → FilterChain → Multi Handler
                                                          ├→ Registry.Handler → Registry → MQTT Discovery Publisher
                                                          ├→ Debug Handler
                                                          └→ Throttler → HA Notifier → Home Assistant
```

### Concepts cles

- **Ports** (`core/ports/`) : `EventProcessor` (entree), `EventHandler` (sortie), `MediaSigner`. Tout passe par ces interfaces.
- **Multi Handler** : dispatch independant — un handler qui echoue ne bloque pas les autres.
- **Throttler** : decorateur anti-spam wrappant un `EventHandler` (cooldown/debounce/ttl).
- **Registry** : cameras decouvertes en memoire + persistence `/data/state.json`. Notifie les `Listener` (MQTT Discovery Publisher).
- **Subscriber** : `Connect()` non-bloquant + `Wait()` bloquant. Route les messages `/set` vers `CommandHandler`.
- **Presigned URLs** : HMAC-SHA256, rotation de 3 cles. Le Signer genere, le Server valide avant proxy vers Frigate.

## Conventions

- Code, commentaires, logs en **francais** (il est prévu de tout traduire en anglais pour la publication du repo)
- Persistence dans `/data/` uniquement
- Config : `/data/options.json` + env overrides (`SUPERVISOR_TOKEN`, `MQTT_PASSWORD`, `FRIGATE_PASSWORD`)
- Filtres : liste vide = tout accepter
- Nouvelles cameras activees par defaut (plug & play)
- Tests : `testify/assert` + `testify/require`
- Ecriture fichiers : atomique (tmp + rename)

## MQTT Discovery

Entites HA par camera : `sensor.fem_{cam}_last_alert`, `_last_object`, `_event_count`, `_severity`, `switch.fem_{cam}_notifications`.

- Config : `homeassistant/sensor/fem_{cam}_*/config` (retain)
- State : `fem/fem/{cam}/*` (retain)
- Commande switch : `fem/fem/{cam}/notifications/set` (ON/OFF)
