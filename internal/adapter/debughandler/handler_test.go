package debughandler_test

import (
    "log/slog"
    "testing"

    "frigate-event-manager/internal/adapter/debughandler"
    "frigate-event-manager/internal/core/ports"
    "frigate-event-manager/internal/domain"
)

var _ ports.EventHandler = (*debughandler.Handler)(nil)

type fakeSigner struct{}

func (f *fakeSigner) SignURL(path string) string {
    return "http://localhost:5555" + path + "?exp=9999999999&sig=fakesig"
}

func TestHandler_HandleEvent_WithSigner(t *testing.T) {
    handler := debughandler.NewHandler(slog.Default(), &fakeSigner{})

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

func TestHandler_HandleEvent_NilSigner(t *testing.T) {
    handler := debughandler.NewHandler(slog.Default(), nil)

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
