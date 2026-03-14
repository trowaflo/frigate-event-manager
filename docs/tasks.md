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

```text
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

> Analyse de référence : [SgtBatten/HA_blueprints](https://github.com/SgtBatten/HA_blueprints) — blueprint Frigate Camera Notifications

### Fait

- [x] **Persistence events** — Ring buffer `/data/events.json` ✅

### Refactoring

- [ ] **Magic strings severity** — Extraire `"alert"` et `"detection"` en constantes dans `internal/domain/`
  - Hardcodées dans `store.go`, `event_test.go` et plusieurs adapters
  - Refactoring transversal, non bloquant

---

### Phase 3 : Parité fonctionnelle blueprint (court terme)

#### 3.1 Filtres manquants

Le `FilterChain` est prêt architecturalement — il suffit d'implémenter les filtres et de les brancher dans `main.go`.

- [ ] **ZoneFilter** — filtrer par zone(s) Frigate
  - Config : `zones: [jardin, entree]`, `zone_multi: true` (toutes requises), `zone_order_enforced: true`
  - Source : `after.CurrentZones` + `after.EnteredZones` dans le payload
  - Liste vide = tout accepter (convention existante)

- [ ] **LabelFilter** — filtrer par objet détecté
  - Config : `labels: [person, car, dog]`
  - Source : `after.Data.Objects`
  - Liste vide = tout accepter

- [ ] **TimeFilter** — plages horaires de silence
  - Config : `disable_times: [0,1,2,3,4,5,22,23]` (heures UTC)
  - Évalué à chaque événement, pas au boot

- [ ] **ScoreFilter** — filtre par score de confiance Frigate
  - Config : `min_score: 0.75`
  - Source : `after.TopScore` (à ajouter dans le domaine si absent)
  - Différenciant vs blueprint (pas natif, souvent fait en Jinja2)

#### 3.2 Cycle de vie de l'événement

- [ ] **Mise à jour de notification existante** — exploiter le `tag` Frigate pour mettre à jour la notif en cours
  - Actuellement : chaque update MQTT peut déclencher une notif dupliquée (bloquée par Throttler)
  - Cible : détecter les updates du même `review_id`, envoyer un `replace_id` / même `tag`
  - Scope : `internal/adapter/homeassistant/notifier.go` + état en mémoire par `review_id`

- [ ] **Notification de fin d'événement** — envoyer une notif finale quand `type: end`
  - Config : `final_update: true`, `final_delay: 2s`
  - Contenu : image finale + durée de l'événement
  - Nécessite de tracker l'état `review_id → {notifié: bool, tag: string}`

- [ ] **Sub_label → mise à jour notif** — re-notifier quand Double Take identifie un visage
  - Source : `after.SubLabels`
  - Déclenche un update de la notif existante avec le nom reconnu

#### 3.3 Enrichissement des notifications

- [ ] **Boutons d'action natifs HA Companion** — remplacer les liens HTML dans le message
  - 3 boutons configurables : label, URL, icône
  - Exemples : "Voir clip", "Silence 30min", "Ouvrir Frigate"
  - Format HA : `actions: [{action: URI, title: "...", uri: "..."}]`

- [ ] **Notification critique** (bypass DND iOS)
  - Config : `critical: true` + condition Jinja2 optionnelle (ex: hors heures ouvrées)
  - Format HA : `push: {sound: {critical: 1, volume: 1.0}}`

- [ ] **Alert once** — son uniquement sur la première notification, updates silencieuses
  - Format HA : `apns_headers: {"apns-collapse-id": tag}`

- [ ] **Initial delay** — attendre N secondes avant la première notif pour laisser Frigate générer une image
  - Config : `initial_delay: 5` (secondes)
  - Implémenté dans le Throttler ou comme délai dans le notifier

- [ ] **Tap action configurable**
  - Config : `url_type: clip | snapshot | stream | frigate | app`
  - Actuellement fixé sur le clip de la première détection

- [ ] **GIFs animés** — ajouter `event_preview.gif` et `review_preview.gif` au proxy media
  - Pas de logique nouvelle : simple proxy vers `GET /api/events/{id}/preview.gif`
  - Nécessite d'ajouter les routes dans `server.go`

#### 3.4 Déduplication cross-caméras

- [ ] **Déduplication cross-caméras** — une seule notif si 2 caméras détectent le même objet simultanément
  - Basé sur : même label + timestamp proche + zones adjacentes (configurable)
  - État en mémoire dans le Processor ou un nouveau composant `Deduplicator`
  - Impossible dans le blueprint (pas d'état partagé entre automations)

---

### Phase 4 : Différenciation (moyen terme)

- [ ] **Multi-canal de notification**
  - `TelegramHandler` — API Telegram Bot (token + chat_id)
  - `WebhookHandler` — POST générique vers n'importe quelle URL
  - Architecture `EventHandler` déjà prête, pas de changement au core

- [ ] **Webhook entrant depuis HA**
  - `POST /api/silence?camera=jardin&duration=30m` — silencer depuis une automation HA
  - Complémentaire au switch MQTT existant, plus expressif

- [ ] **Filtre de présence via état HA**
  - `GET /api/states/person.john` via l'API Supervisor
  - N'alerte pas si la personne est "home"
  - Nécessite un client HA API dans `internal/adapter/supervisor/`

---

### Phase 5 : Intégration HACS (long terme)

> Objectif : publier comme intégration HA native, configuration via UI HA, entités via API HA (pas MQTT).

- [ ] **Config via `config_entries`** — remplacer `options.json` par le config flow HA
  - Chaque filtre = un champ de formulaire dans l'UI HA
  - Hot-reload sans redémarrage addon

- [ ] **Entités via API HA entity registry** — remplacer MQTT Discovery
  - Plus de dépendance MQTT pour les entités (découplage complet)
  - Support natif device classes, icônes, catégories dans l'UI HA
  - `registry.Listener` → ajouter un `HAEntityPublisher` à côté du `MQTTDiscoveryPublisher`

- [ ] **`binary_sensor.fem_{cam}_motion`** — nouvelle entité par caméra
  - `on` sur `type: new`, `off` sur `type: end`
  - Permet les automations HA classiques sans MQTT

- [ ] **Services HA (actions)**
  - `frigate_event_manager.silence_camera(camera, duration)`
  - `frigate_event_manager.replay_last_event(camera)`
  - Remplacent le switch MQTT, surface d'intégration propre pour les scripts HA

## Phase 1 : MQTT Discovery (FAIT)

- [x] 1.1 Camera Registry — persistence + auto-decouverte
- [x] 1.2 MQTT Discovery Publisher — 5 entites par camera
- [x] 1.3 Subscriber enrichi — Connect/Wait, routing commandes
- [x] 1.4 Branchement main.go
