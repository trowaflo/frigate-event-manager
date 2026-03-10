package debughandler_test

import (
    "log/slog"
    "testing"

    "frigate-event-manager/internal/adapter/debughandler"
    "frigate-event-manager/internal/core/ports"
    "frigate-event-manager/internal/domain"
)

var _ ports.EventHandler = (*debughandler.Handler)(nil)

func TestHandler_HandleEvent_NoError(t *testing.T) {
    handler := debughandler.NewHandler(slog.Default(), "http://localhost:5555")

    err := handler.HandleEvent(domain.FrigatePayload{
        Type: "new",
        After: domain.EventState{
            ID:       "test-123",
            Camera:   "front_cam",
            Severity: "alert",
            Data: domain.EventData{
                Objects:    []string{"person"},
                Zones:      []string{"front_yard"},
                Detections: []string{"det-abc", "det-def"},
            },
        },
    })

    if err != nil {
        t.Fatalf("erreur inattendue: %v", err)
    }
}

func TestHandler_HandleEvent_NoBaseURL(t *testing.T) {
    handler := debughandler.NewHandler(slog.Default(), "")

    err := handler.HandleEvent(domain.FrigatePayload{
        Type: "new",
        After: domain.EventState{
            ID:       "test-456",
            Camera:   "back_cam",
            Severity: "detection",
        },
    })

    if err != nil {
        t.Fatalf("erreur inattendue: %v", err)
    }
}
