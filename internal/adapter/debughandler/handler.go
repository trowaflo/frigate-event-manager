package debughandler

import (
    "log/slog"

    "frigate-event-manager/internal/domain"
)

// Handler est un EventHandler qui affiche les événements dans les logs.
// C'est un handler temporaire pour tester la chaîne complète
// avant d'implémenter les vraies notifications.
type Handler struct {
    logger *slog.Logger
}

// NewHandler crée un handler de log.
func NewHandler(logger *slog.Logger) *Handler {
    return &Handler{logger: logger}
}

// HandleEvent affiche l'événement Frigate dans les logs.
func (h *Handler) HandleEvent(payload domain.FrigatePayload) error {
    h.logger.Info("événement Frigate accepté",
        "type", payload.Type,
        "camera", payload.After.Camera,
        "severity", payload.After.Severity,
        "objects", payload.After.Data.Objects,
        "zones", payload.After.Data.Zones,
        "review_id", payload.After.ID,
    )
    return nil
}
