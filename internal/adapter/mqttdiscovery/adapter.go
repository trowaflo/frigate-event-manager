package mqttdiscovery

import (
	"context"
	"log/slog"
	"strings"

	"frigate-event-manager/internal/core/registry"

	"github.com/eclipse/paho.golang/autopaho"
	"github.com/eclipse/paho.golang/paho"
)

// AutopahoAdapter adapte autopaho.ConnectionManager en MQTTPublisher.
type AutopahoAdapter struct {
	cm *autopaho.ConnectionManager
}

// NewAutopahoAdapter crée un adapter MQTT à partir du ConnectionManager.
func NewAutopahoAdapter(cm *autopaho.ConnectionManager) *AutopahoAdapter {
	return &AutopahoAdapter{cm: cm}
}

// Publish envoie un message MQTT via autopaho.
func (a *AutopahoAdapter) Publish(ctx context.Context, topic string, qos byte, retain bool, payload []byte) error {
	_, err := a.cm.Publish(ctx, &paho.Publish{
		Topic:   topic,
		QoS:     qos,
		Retain:  retain,
		Payload: payload,
	})
	return err
}

// SwitchCommandHandler gère les commandes MQTT pour les switchs notifications.
// Il implémente mqtt.CommandHandler.
type SwitchCommandHandler struct {
	registry *registry.Registry
	logger   *slog.Logger
}

// NewSwitchCommandHandler crée un handler de commandes switch.
func NewSwitchCommandHandler(reg *registry.Registry, logger *slog.Logger) *SwitchCommandHandler {
	return &SwitchCommandHandler{registry: reg, logger: logger}
}

// HandleCommand traite un message reçu sur fem/fem/{camera}/notifications/set.
// Payload attendu : "ON" ou "OFF".
func (h *SwitchCommandHandler) HandleCommand(topic string, payload []byte) {
	// Extraire le nom de la caméra du topic : fem/fem/{camera}/notifications/set
	parts := strings.Split(topic, "/")
	if len(parts) < 5 {
		h.logger.Warn("topic de commande invalide", "topic", topic)
		return
	}
	camera := parts[2]
	value := strings.TrimSpace(strings.ToUpper(string(payload)))

	enabled := value == "ON"
	if err := h.registry.SetEnabled(camera, enabled); err != nil {
		h.logger.Warn("impossible de changer l'état notifications", "camera", camera, "error", err)
		return
	}
	h.logger.Info("notifications modifiées via MQTT", "camera", camera, "enabled", enabled)
}
