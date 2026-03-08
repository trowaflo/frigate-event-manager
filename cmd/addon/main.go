package main

import (
	"context"
	"log/slog"
	"os"
	"os/signal"
	"syscall"

	"frigate-event-manager/internal/adapter/config"
	"frigate-event-manager/internal/adapter/debughandler"
	"frigate-event-manager/internal/adapter/homeassistant"
	mqttadapter "frigate-event-manager/internal/adapter/mqtt"
	"frigate-event-manager/internal/core/filter"
	"frigate-event-manager/internal/core/ports"
	"frigate-event-manager/internal/core/processor"
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
		"ha_url", cfg.HABaseURL,
		"notify_service", cfg.NotifyService,
	)

	// --- Event Handler : dépend de ce qui est configuré ---
	var eventHandler ports.EventHandler

	if cfg.HasNotifier() {
		log.Info("notifications HA actives", "ha_url", cfg.HABaseURL, "service", cfg.NotifyService)
		eventHandler = homeassistant.NewNotifier(cfg.HABaseURL, cfg.HAToken, cfg.NotifyService)
	} else {
		log.Info("pas de config HA — événements loggés uniquement")
		eventHandler = debughandler.NewHandler(log)
	}

	// --- Le reste est identique quel que soit le mode ---
	chain := filter.NewFilterChain(
		filter.NewSeverityFilter(cfg.SeverityFilter),
	)
	proc := processor.NewProcessor(chain, eventHandler)
	msgHandler := mqttadapter.NewMessageHandler(proc)
	subscriber := mqttadapter.NewSubscriber(cfg.MQTTBrokerURL, cfg.MQTTTopic, cfg.MQTTClientID, cfg.MQTTUsername, cfg.MQTTPassword, msgHandler, log)

	ctx, cancel := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
	defer cancel()

	log.Info("connexion au broker MQTT...")
	if err := subscriber.Start(ctx); err != nil {
		log.Error("erreur fatale", "error", err)
		os.Exit(1)
	}

	log.Info("arrêt propre terminé")
}

func getEnv(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}
