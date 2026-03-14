package mqtt

import (
	"encoding/json"
	"fmt"

	"frigate-event-manager/internal/core/ports"
	"frigate-event-manager/internal/domain"
)

// MessageHandler est la couche intermédiaire entre les bytes MQTT bruts
// et le Core (Processor). Il connaît le format JSON de Frigate
// et le transforme en objet domain propre.
//
//	[bytes MQTT] → MessageHandler → [domain.FrigatePayload] → Processor
type MessageHandler struct {
	processor ports.EventProcessor
}

// NewMessageHandler crée un handler qui transmettra les événements au processor.
func NewMessageHandler(processor ports.EventProcessor) *MessageHandler {
	return &MessageHandler{processor: processor}
}

// Handle parse un message MQTT brut et le transmet au processor.
// Si le JSON est invalide, il retourne une erreur (le message est ignoré).
func (h *MessageHandler) Handle(raw []byte) error {
	if len(raw) == 0 {
		return fmt.Errorf("payload MQTT vide")
	}

	var payload domain.FrigatePayload
	if err := json.Unmarshal(raw, &payload); err != nil {
		return fmt.Errorf("impossible de parser le payload MQTT: %w", err)
	}

	return h.processor.ProcessEvent(payload)
}
