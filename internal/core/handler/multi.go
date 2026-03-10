package handler

import (
	"log/slog"

	"frigate-event-manager/internal/core/ports"
	"frigate-event-manager/internal/domain"
)

// Multi dispatche un événement à plusieurs handlers indépendants.
// Chaque handler est exécuté même si un autre échoue.
// Les erreurs sont loguées mais ne bloquent pas les autres handlers.
type Multi struct {
	handlers []named
	logger   *slog.Logger
}

type named struct {
	name    string
	handler ports.EventHandler
}

func NewMulti(logger *slog.Logger) *Multi {
	return &Multi{logger: logger}
}

// Add enregistre un handler avec un nom (pour les logs).
func (m *Multi) Add(name string, h ports.EventHandler) {
	m.handlers = append(m.handlers, named{name: name, handler: h})
}

// HandleEvent dispatch l'événement à tous les handlers.
// Retourne nil : les erreurs individuelles sont loguées, pas propagées.
func (m *Multi) HandleEvent(payload domain.FrigatePayload) error {
	for _, h := range m.handlers {
		if err := h.handler.HandleEvent(payload); err != nil {
			m.logger.Error("handler en erreur",
				"handler", h.name,
				"review_id", payload.After.ID,
				"error", err,
			)
		}
	}
	return nil
}
