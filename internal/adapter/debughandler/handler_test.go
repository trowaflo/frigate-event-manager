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
    handler := debughandler.NewHandler(slog.Default())

    err := handler.HandleEvent(domain.FrigatePayload{
        Type: "new",
        After: domain.EventState{
            ID:       "test-123",
            Camera:   "front_cam",
            Severity: "alert",
            Data: domain.EventData{
                Objects: []string{"person"},
                Zones:   []string{"front_yard"},
            },
        },
    })

    if err != nil {
        t.Fatalf("erreur inattendue: %v", err)
    }
}
