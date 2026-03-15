package main

import (
	"context"
	"fmt"
	"log/slog"
	"os"
	"os/signal"
	"path/filepath"
	"syscall"
	"time"

	"frigate-event-manager/internal/adapter/api"
	"frigate-event-manager/internal/adapter/config"
	"frigate-event-manager/internal/adapter/debughandler"
	"frigate-event-manager/internal/adapter/frigate"
	"frigate-event-manager/internal/adapter/homeassistant"
	mqttadapter "frigate-event-manager/internal/adapter/mqtt"
	"frigate-event-manager/internal/adapter/mqttdiscovery"
	"frigate-event-manager/internal/adapter/supervisor"
	"frigate-event-manager/internal/core/eventstore"
	"frigate-event-manager/internal/core/filter"
	"frigate-event-manager/internal/core/handler"
	"frigate-event-manager/internal/core/ports"
	"frigate-event-manager/internal/core/processor"
	"frigate-event-manager/internal/core/registry"
	"frigate-event-manager/internal/core/throttle"
)

func main() {
	log := slog.New(slog.NewTextHandler(os.Stdout, &slog.HandlerOptions{
		Level: slog.LevelDebug,
	}))

	configPath := getEnv("CONFIG_PATH", "/data/options.json")
	cfg, err := config.Load(configPath)
	if err != nil {
		log.Error("impossible de charger la configuration", "path", configPath, "error", err)
		os.Exit(1)
	}

	log.Info("configuration chargée",
		"broker", cfg.MQTTBrokerURL,
		"topic", cfg.MQTTTopic,
		"mqtt_user", cfg.MQTTUsername,
		"notify_service", cfg.NotifyService,
	)

	// --- Camera Registry (persistence dans /data/state.json) ---
	dataDir := filepath.Dir(configPath)
	statePath := filepath.Join(dataDir, "state.json")
	reg := registry.New(statePath)
	if err := reg.Load(); err != nil {
		log.Warn("impossible de charger l'état précédent", "path", statePath, "error", err)
	} else {
		cams := reg.Cameras()
		if len(cams) > 0 {
			log.Info("état restauré", "cameras", len(cams))
		}
	}

	// --- Résolution de l'URL ingress via le Supervisor HA ---
	ingressInfo, err := supervisor.FetchIngressInfo(cfg.HAToken)
	if err != nil {
		log.Warn("impossible de contacter le Supervisor HA", "error", err)
	}
	cfg.SetMediaBaseURL(ingressInfo.MediaBaseURL)

	// --- Frigate client + Signer (optionnel) ---
	var frigateClient *frigate.Client
	var signer *api.Signer
	var mediaSigner ports.MediaSigner

	if cfg.HasFrigate() {
		frigateClient = frigate.NewClient(cfg.FrigateURL, cfg.FrigateUser, cfg.FrigatePassword, log)
		log.Info("client Frigate configuré", "url", cfg.FrigateURL)

		presignTTL := time.Duration(cfg.PresignTTL) * time.Minute
		signer = api.NewSigner(cfg.MediaBaseURL, presignTTL, presignTTL, 3)
		mediaSigner = signer
		log.Info("presigned URLs activées", "ttl", presignTTL, "base_url", cfg.MediaBaseURL)
	}

	// --- Event Store (ring buffer pour la timeline Web UI) ---
	evStore := eventstore.New(200)
	if cfg.PersistEvents {
		eventsPath := filepath.Join(dataDir, "events.json")
		if err := evStore.Load(eventsPath); err != nil {
			log.Warn("impossible de charger les événements", "path", eventsPath, "error", err)
		} else if evStore.Len() > 0 {
			log.Info("événements restaurés", "count", evStore.Len())
		}
		evStore.EnablePersistence(eventsPath)
		log.Info("persistence des événements activée", "path", eventsPath)
	}

	// --- Event Handlers (indépendants, un échec ne bloque pas les autres) ---
	multi := handler.NewMulti(log)

	// Registry handler : alimente le registry à chaque événement (toujours actif)
	multi.Add("registry", registry.NewHandler(reg))

	// Event store handler : alimente la timeline (toujours actif)
	multi.Add("eventstore", eventstore.NewHandler(evStore))

	// Debug handler : toujours actif (log + presigned URLs media)
	multi.Add("debug", debughandler.NewHandler(log, mediaSigner))

	// Notifier HA : ajouté si configuré
	if cfg.HasNotifier() {
		log.Info("notifications HA actives", "ha_url", cfg.HABaseURL, "service", cfg.NotifyService)
		notifier := homeassistant.NewNotifier(cfg.HABaseURL, cfg.HAToken, cfg.NotifyService, mediaSigner)
		multi.Add("notifier", throttle.New(notifier,
			time.Duration(cfg.Cooldown)*time.Second,
			time.Duration(cfg.Debounce)*time.Second,
			time.Duration(cfg.TTL)*time.Minute,
		))
		log.Info("throttle activé", "cooldown", cfg.Cooldown, "debounce", cfg.Debounce)
	}

	// --- Processor + MQTT subscriber ---
	chain := filter.NewFilterChain(
		filter.NewSeverityFilter(cfg.SeverityFilter),
		filter.NewZoneFilter(cfg.Zones, cfg.ZoneMulti, cfg.ZoneOrderEnforced),
		filter.NewLabelFilter(cfg.Labels),
		filter.NewTimeFilter(cfg.DisableTimes, nil),
	)
	proc := processor.NewProcessor(chain, multi)
	msgHandler := mqttadapter.NewMessageHandler(proc)
	subscriber := mqttadapter.NewSubscriber(cfg.MQTTBrokerURL, cfg.MQTTTopic, cfg.MQTTClientID, cfg.MQTTUsername, cfg.MQTTPassword, msgHandler, log)

	// Command handler pour les switchs MQTT Discovery
	switchHandler := mqttdiscovery.NewSwitchCommandHandler(reg, log)
	subscriber.SetCommandHandler(switchHandler)

	ctx, cancel := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
	defer cancel()

	// --- Serveur API (Web UI + management + proxy media si Frigate configuré) ---
	srv := api.NewServer(frigateClient, signer, reg, evStore, cfg, log)
	addr := fmt.Sprintf(":%d", cfg.APIPort)
	go func() {
		if err := srv.ListenAndServe(addr); err != nil {
			log.Error("erreur serveur API", "error", err)
		}
	}()

	// --- Connexion MQTT ---
	log.Info("connexion au broker MQTT...")
	if err := subscriber.Connect(ctx); err != nil {
		log.Error("erreur fatale", "error", err)
		os.Exit(1)
	}

	// --- MQTT Discovery : publier les entités après connexion ---
	if !cfg.MQTTDiscoveryEnabled() {
		log.Info("MQTT Discovery désactivé (intégration HACS)")
	} else if cm := subscriber.ConnectionManager(); cm != nil {
		mqttPub := mqttdiscovery.NewAutopahoAdapter(cm)
		discoveryPub := mqttdiscovery.NewPublisher(ctx, mqttPub, log)

		// Enregistrer le publisher comme listener du registry
		reg.AddListener(discoveryPub)

		// Publier les entités des caméras déjà connues (restaurées depuis state.json)
		discoveryPub.PublishAll(reg.Cameras())
		log.Info("MQTT Discovery initialisé")
	}

	// --- Attente du signal d'arrêt ---
	if err := subscriber.Wait(ctx); err != nil {
		log.Error("erreur fatale", "error", err)
		os.Exit(1)
	}

	if signer != nil {
		signer.Stop()
	}

	log.Info("arrêt propre terminé")
}

func getEnv(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}
