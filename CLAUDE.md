# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Pass phrase

A chaque debut de session (premier message), annoncer sur un ton d'IA iconique (Jarvis, KITT, C3PO, R2-D2, BB-8, WALL-E, HAL, GLaDOS...) une phrase confirmant que les instructions ont ete lues. Varier le personnage et le style a chaque session. L'humour et les clins d'oeil geek sont encourages.

Exemple : « Bip bwoop — BB-8 en ligne. Instructions CLAUDE.md chargees, systeme Home Assistant sous controle. »

Cette phrase doit preceder toute action, reponse ou modification, sans exception.

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

- `.venv/bin/pytest tests/ --cov=custom_components/frigate_event_manager -q` (tests passent)
- `.venv/bin/ruff check custom_components/` (lint)
- `markdownlint-cli2 '**/*.md' '!.venv/**'` (si markdown modifié)
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

**Format des regles en memoire :**

```text
[NL]   → langage naturel  : preferences, contexte, style, definitions de roles
[RULE] → pseudo-code      : guards, invariants, interdictions techniques
```

Lors de chaque learn cycle, convertir en `[RULE]` toute regle qui est une interdiction explicite (`NEVER`, `FORBIDDEN`), un invariant technique (`ALWAYS`, `REQUIRE`), ou un guard avec consequence mesurable (`IF violation → consequence`).

Conserver `[NL]` pour les preferences de communication et les regles de style.

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

### Agents specialises (`.claude/agents/`)

Agents avec scopes stricts pour les taches multi-composants :

| Agent | Role |
| --- | --- |
| `orchestrator` | Chef d'equipe — decompose, assigne, cree les PRs |
| `python-architect` | Integration HA HACS, entites, coordinators, config flows |
| `reviewer` | Review qualite + securite + sync doc |
| `quality-guard` | Tests et coverage ≥80% |
| `code-simplifier` | Refactoring DRY (apres reviewer + quality-guard) |
| `frontend-designer` | Maquettes HTML interactives `maquette/` |
| `sre-cloud` | CI/CD, Taskfile |

**Pipeline obligatoire** (toute feature) :

```text
[RULE] feature_pipeline:
    ORDER:  implement → review + quality-guard (PARALLEL) → simplify → commit → PR
    NEVER:  simplify avant quality-guard
    NEVER:  declarer DONE sans commit
    tasks.md: T-XXXb (review)   Depends T-XXX,  Blocks T-XXXc + T-XXXd
              T-XXXd (tests)    Depends T-XXXb, Blocks T-XXXc
              T-XXXc (simplify) Depends T-XXXb + T-XXXd
    VIOLATION → issues manquees, commits groupes illisibles
```

```text
[RULE] bulk_micro_fixes:
    IF:  reviewer identifie un fix <= 5 lignes (MINOR / INFO)
    THEN: noter dans T-XXXb notes sous "PENDING_FIXUP"
          orchestrateur route vers code-simplifier (T-XXXc), pas python-architect
          code-simplifier applique tous les PENDING_FIXUP en un seul passage
    NEVER: spawner python-architect pour un fix MINOR du reviewer
    NEVER: creer un nouveau cycle pipeline pour corriger 1 ligne
    WHY:   chaque cycle pipeline = ~20-30 appels API → cout x N pour rien
    APPLIES_TO: reviewer (emetteur), orchestrateur (routeur)
    NOT_APPLIES: quality-guard (scope tests uniquement, corrige dans son propre cycle)
    VIOLATION → cycles inutiles detectes (ex: T-521 fixup sur 1 ligne strings.json)
```

- **Lancer** : "Utilise l'agent orchestrator pour [tache]"
- **Blackboard** : `docs/tasks.md` (section Blackboard Actif) — memoire partagee entre agents
- **Agent Teams** : actives via `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` dans `.claude/settings.json`

**Skills != Agents** : skills = recettes invocables (`/skill`), agents = identites autonomes spawnables avec scope propre.

## Pieges connus

```text
[RULE] mock_hass:
    ALWAYS: MagicMock()                   # sans spec=
    NEVER:  MagicMock(spec=HomeAssistant)
    VIOLATION → AttributeError sur hass.config / hass.components

[RULE] markdownlint:
    ALWAYS: markdownlint-cli2 '**/*.md' '!.venv/**'
    NEVER:  npx markdownlint-cli2 / omettre '!.venv/**'

[RULE] plan_vs_execute:
    IF: demande contient "planifier" / "ajouter a la liste" / "noter"
    THEN: modifier ONLY docs/tasks.md
    NEVER: modifier les fichiers concernes par la demande
    VIOLATION → edition non sollicitee

[RULE] tasks_md_identifiers:
    ALWAYS: entourer les identifiants Python de backticks dans les Notes tasks.md
    EXAMPLES: `_cancel_silent`, `__init__.py`, `async_step_user`
    NEVER:  underscores en texte brut dans les Notes YAML
    VIOLATION → MD037 markdownlint

[RULE] translations_en_required:
    ALWAYS: creer translations/en.json en meme temps que fr.json
    NEVER:  fr.json sans en.json
    VIOLATION → config flow invisible dans l'UI HA

[RULE] config_flow_list_fields:
    ALWAYS: str + _parse_csv() pour les champs liste dans le config flow
    NEVER:  vol.Coerce(list) sur une string UI
    VIOLATION → chaque caractere devient un element de liste

[RULE] agents_no_bash:
    INVARIANT: agents specialises ne peuvent pas executer pytest/ruff (permission default)
    ALWAYS: orchestrateur principal verifie tests + lint apres chaque livraison d'agent
    BEFORE: tout commit

[RULE] ha_icon_png:
    ALWAYS: icon.png dans custom_components/{domain}/ en mode RGB 256x256
    NEVER:  RGBA (transparence) — non affiche dans certaines versions HA
    DEPLOY: task deploy copie custom_components/ entier, images/ n'est PAS deploye
```

- **`skill-creator` → `run_loop.py`** : ~300 appels API (5 iter × 20 requetes × 3 repetitions). Estimer et confirmer le cout avant de lancer. Requiert `ANTHROPIC_API_KEY` separe de Claude Code.
- **Skills != Agents** : creer un skill qui duplique un agent existant est une erreur — spawner l'agent directement.

## Project

Integration Home Assistant HACS (Python). Ecoute les events Frigate via MQTT natif HA, filtre, throttle, et envoie des notifications HA Companion. Publiee via HACS custom repository.

## Commits

```text
[RULE] commit_format:
    ALWAYS: git commit -m "type: titre court"
    NEVER:  identifiant de tache (T-XXX), corps de commit, Co-Authored-By

[RULE] commit_granularity:
    ALWAYS: un commit par etape logique (implementation, tests, simplification)
    NEVER:  grouper toutes les etapes d'un pipeline en un seul commit de fin
    VIOLATION → git log illisible, bisect impossible

[RULE] no_auto_push:
    NEVER:  git push sans demande explicite de l'utilisateur
    ALWAYS: s'arreter apres le commit
```

## Commands

```bash
task test   # pytest + coverage ≥80%
task lint   # ruff + markdownlint
```

```bash
.venv/bin/pytest tests/ --cov=custom_components/frigate_event_manager --cov-report=term-missing -q
.venv/bin/pytest tests/test_coordinator.py -v   # un seul module
.venv/bin/ruff check custom_components/
markdownlint-cli2 '**/*.md' '!.venv/**'
```

## Architecture

Python asyncio, integration native HA (DataUpdateCoordinator + CoordinatorEntity).

Diagrammes complets : `docs/architecture.md` (Mermaid, lisible sur GitHub).

```text
MQTT Broker → FrigateEventManagerCoordinator → FilterChain → Throttler → HANotifier
                        ↓                                                      ↓
                  CameraRegistry                                    HA Companion notification
                  EventStore
                        ↓
              Entités HA (sensor × 3, switch × 1, binary_sensor × 1 par caméra)
```

### Composants cles

- **`coordinator.py`** : souscrit MQTT, parse payload Frigate → `FrigateEvent`, maintient `CameraState` par caméra
- **`filter.py`** : `ZoneFilter`, `LabelFilter`, `TimeFilter`, `FilterChain` — liste vide = tout accepter
- **`registry.py`** : persistence état caméras dans `hass.config.path("frigate_em_state.json")`
- **`event_store.py`** : ring buffer 200 events, stats 24h
- **`throttle.py`** : anti-spam cooldown par caméra, clock injectable
- **`notifier.py`** : notifications HA Companion via `hass.services.async_call`

## Conventions

- Code, commentaires, logs en **francais** (prevu anglais pour publication)
- Filtres : liste vide = tout accepter
- Nouvelles cameras activees par defaut (plug & play)
- Tests : pytest + `AsyncMock` — `MagicMock()` sans `spec=HomeAssistant`
- Ecriture fichiers : atomique (tmp + rename)
- Persistence : `hass.config.path(...)` (pas `/data/`)
- `unique_id` entites : `fem_{cam_name}_{key}`
- `html.escape()` sur tous les champs dynamiques dans `notifier.py`
