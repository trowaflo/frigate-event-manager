package registry

import (
	"frigate-event-manager/internal/domain"
)

// Handler est un EventHandler qui alimente le Registry à chaque événement.
// Il s'intègre dans le MultiHandler comme n'importe quel autre handler.
type Handler struct {
	registry *Registry
}

// NewHandler crée un handler qui enregistre les événements dans le registry.
func NewHandler(reg *Registry) *Handler {
	return &Handler{registry: reg}
}

// HandleEvent enregistre la caméra et met à jour son état.
func (h *Handler) HandleEvent(payload domain.FrigatePayload) error {
	after := payload.After
	if after.Camera == "" {
		return nil
	}
	h.registry.RecordEvent(after.Camera, after.Severity, after.Data.Objects)
	return nil
}
