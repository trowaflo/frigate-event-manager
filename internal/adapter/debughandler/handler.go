package debughandler

import (
    "fmt"
    "log/slog"
    "strings"

    "frigate-event-manager/internal/domain"
)

// Handler est un EventHandler qui affiche les événements dans les logs.
// C'est un handler temporaire pour tester la chaîne complète
// avant d'implémenter les vraies notifications.
type Handler struct {
    logger  *slog.Logger
    baseURL string // ex: "http://localhost:5555"
}

// NewHandler crée un handler de log.
// baseURL est l'URL du proxy API (vide = pas de liens media).
func NewHandler(logger *slog.Logger, baseURL string) *Handler {
    return &Handler{logger: logger, baseURL: strings.TrimRight(baseURL, "/")}
}

// HandleEvent affiche l'événement Frigate dans les logs.
func (h *Handler) HandleEvent(payload domain.FrigatePayload) error {
    after := payload.After

    h.logger.Info("événement Frigate accepté",
        "type", payload.Type,
        "camera", after.Camera,
        "severity", after.Severity,
        "objects", after.Data.Objects,
        "zones", after.Data.Zones,
        "review_id", after.ID,
        "detections", after.Data.Detections,
    )

    if h.baseURL != "" {
        // Review preview (gif animé du review complet)
        h.logger.Info("review media",
            "preview", fmt.Sprintf("%s/api/review/%s/preview", h.baseURL, after.ID),
        )

        // URLs par detection (clip/snapshot)
        for _, detID := range after.Data.Detections {
            h.logger.Info("detection media",
                "detection_id", detID,
                "clip", fmt.Sprintf("%s/api/events/%s/clip.mp4", h.baseURL, detID),
                "snapshot", fmt.Sprintf("%s/api/events/%s/snapshot.jpg", h.baseURL, detID),
                "thumbnail", fmt.Sprintf("%s/api/events/%s/thumbnail.jpg", h.baseURL, detID),
            )
        }
    }

    return nil
}
