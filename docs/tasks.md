# Tasks — Frigate Event Manager

> Protocole complet : `.claude/agents/orchestrator.md`

---

## Blackboard Actif

_Aucune tâche en cours. Prêt pour la prochaine session._

<!--
### T-XXX | [Titre]
- Status: TODO
- Owner: —
- Scope: —
- Locks: —
- Depends: —
- Blocks: —
- Notes: —
-->

---

## Phase 2 : Web UI (ingress)

### Decisions d'architecture

- **Un seul serveur HTTP** : les nouvelles routes s'ajoutent au meme mux. Le presign reste applique par route (media proxy), pas globalement.
- **Events : ring buffer en memoire** (200 entries, perdu au reboot). Frigate est la source de verite pour l'historique complet.
- **Auth : trust ingress**. Les routes management (`/api/cameras`, `/api/config`...) sont protegees par l'auth HA ingress. Le presign reste pour les media (accessibles hors ingress via notifs).
- **Assets : `go:embed`** dans `internal/adapter/api/web/index.html`. Un seul fichier HTML avec CSS/JS inline (comme la maquette).
- **Le serveur demarre toujours**, meme sans Frigate configure. Les routes media proxy sont conditionnelles.

### Plan d'implementation

- [x] **2.1 Event Store** — `internal/core/eventstore/`
  - `store.go` : ring buffer (EventRecord, Add, List, Stats)
  - `handler.go` : impl EventHandler, alimente le store
  - `store_test.go` + `handler_test.go` (9 tests)
- [x] **2.2 Config.Sanitized()** — `internal/adapter/config/config.go`
  - Methode qui retourne la config sans secrets (passwords → `***`, tokens omis)
  - 2 tests
- [x] **2.3 Etendre Server** — `internal/adapter/api/server.go`
  - Ajouter registry, eventStore, config au struct Server
  - Rendre client/signer optionnels (nil si pas de Frigate)
  - Routes media conditionnelles
- [x] **2.4 API Management** — integre dans `server.go` (handlers inline)
  - `GET /api/cameras` → registry.Cameras()
  - `PATCH /api/cameras/{name}` → registry.SetEnabled()
  - `GET /api/config` → config.Sanitized()
  - `GET /api/stats` → eventStore.Stats() + registry
  - `GET /api/events-list` → eventStore.List(?severity=&limit=)
  - 7 tests dans `server_test.go`
- [x] **2.5 SPA Frontend** — `internal/adapter/api/web/index.html`
  - Basee sur la maquette, avec fetch() vers les API endpoints
  - URLs relatives (compatible ingress)
  - Base href dynamique via X-Ingress-Path
  - 4 pages : Dashboard, Events, Cameras, Settings
  - Auto-refresh dashboard toutes les 15s
- [x] **2.6 Embed + Serve** — `internal/adapter/api/server.go`
  - `//go:embed web/index.html`
  - Route `/` → serveIndex (injecte base href)
  - 2 tests (serve + ingress base path)
- [x] **2.7 Wiring main.go**
  - eventStore(200) cree et branche dans Multi
  - Serveur API demarre toujours
  - Passe registry, eventStore, config au NewServer
- [x] **2.8 Verify**
  - `go build ./...` OK
  - `go test ./... -count=1` OK (tous les tests passent)
  - Test manuel : ouvrir localhost:5555 dans le navigateur

### Ordre d'execution

```
2.1 (eventstore) + 2.2 (config sanitize) → en parallele
     ↓
2.3 (etendre Server)
     ↓
2.4 (API handlers) + 2.5 (SPA frontend) → en parallele
     ↓
2.6 (embed + serve)
     ↓
2.7 (wiring main.go)
     ↓
2.8 (verify)
```

## Backlog

- [x] **Persistence events** — Sauvegarder le ring buffer dans `/data/events.json`
  - Optionnel, activable via config (`persist_events: true`)
  - Ecriture atomique (tmp + rename) apres chaque event
  - Chargement au boot, respecte la capacite max du ring buffer
  - 5 tests (save/load, capacite, fichier absent, fichier corrompu, desactive par defaut)
  - Note : sur stockage flash/SD card (Raspberry Pi), les ecritures frequentes peuvent accelerer l'usure

## Phase 1 : MQTT Discovery (FAIT)

- [x] 1.1 Camera Registry — persistence + auto-decouverte
- [x] 1.2 MQTT Discovery Publisher — 5 entites par camera
- [x] 1.3 Subscriber enrichi — Connect/Wait, routing commandes
- [x] 1.4 Branchement main.go
