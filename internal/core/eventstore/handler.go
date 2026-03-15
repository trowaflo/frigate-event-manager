package eventstore

import (
	"time"

	"frigate-event-manager/internal/domain"
)

// Handler est un EventHandler qui alimente le Store à chaque événement.
type Handler struct {
	store *Store
}

// NewHandler crée un handler qui enregistre les événements dans le store.
func NewHandler(store *Store) *Handler {
	return &Handler{store: store}
}

// HandleEvent enregistre l'événement dans le store.
func (h *Handler) HandleEvent(payload domain.FrigatePayload) error {
	after := payload.After
	if after.Camera == "" || after.ID == "" {
		return nil
	}

	h.store.Add(EventRecord{
		ReviewID:  after.ID,
		Camera:    after.Camera,
		Severity:  after.Severity,
		Objects:   after.Data.Objects,
		Zones:     after.Data.Zones,
		Timestamp: time.Unix(int64(after.StartTime), 0),
	})
	return nil
}
