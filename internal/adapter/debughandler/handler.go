package debughandler

import (
    "log/slog"

    "frigate-event-manager/internal/core/ports"
    "frigate-event-manager/internal/domain"
)

// Handler est un EventHandler qui affiche les événements dans les logs.
type Handler struct {
    logger *slog.Logger
    signer ports.MediaSigner
}

// NewHandler crée un handler de log.
// signer peut être nil si le proxy media n'est pas configuré.
func NewHandler(logger *slog.Logger, signer ports.MediaSigner) *Handler {
    return &Handler{logger: logger, signer: signer}
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

    if h.signer != nil {
        // Review preview (gif animé du review complet)
        h.logger.Info("review media",
            "preview", h.signer.SignURL("/api/review/"+after.ID+"/preview"),
        )

        // URLs par detection (clip/snapshot/thumbnail)
        for _, detID := range after.Data.Detections {
            h.logger.Info("detection media",
                "detection_id", detID,
                "clip", h.signer.SignURL("/api/events/"+detID+"/clip.mp4"),
                "snapshot", h.signer.SignURL("/api/events/"+detID+"/snapshot.jpg"),
                "thumbnail", h.signer.SignURL("/api/events/"+detID+"/thumbnail.jpg"),
            )
        }
    }

    return nil
}
