package mqtt_test

import (
    "context"
    "log/slog"
    "testing"
    "time"

    mqttadapter "frigate-event-manager/internal/adapter/mqtt"
)

func TestNewSubscriber_ReturnsNonNil(t *testing.T) {
    proc := &mockProcessor{}
    handler := mqttadapter.NewMessageHandler(proc)
    logger := slog.Default()

    sub := mqttadapter.NewSubscriber(
        "tcp://localhost:1883", "frigate/reviews", "test-client",
        "user", "pass", handler, logger,
    )
    if sub == nil {
        t.Fatal("NewSubscriber returned nil")
    }
}

func TestSubscriber_Start_InvalidURL_ReturnsError(t *testing.T) {
    proc := &mockProcessor{}
    handler := mqttadapter.NewMessageHandler(proc)
    logger := slog.Default()

    sub := mqttadapter.NewSubscriber(
        "://invalid-url", "frigate/reviews", "test-client",
        "", "", handler, logger,
    )

    ctx, cancel := context.WithTimeout(context.Background(), 100*time.Millisecond)
    defer cancel()

    err := sub.Start(ctx)
    if err == nil {
        t.Fatal("expected error for invalid broker URL")
    }
}

func TestSubscriber_Start_UnreachableBroker_ReturnsError(t *testing.T) {
    proc := &mockProcessor{}
    handler := mqttadapter.NewMessageHandler(proc)
    logger := slog.Default()

    sub := mqttadapter.NewSubscriber(
        "tcp://127.0.0.1:19999", "frigate/reviews", "test-client",
        "", "", handler, logger,
    )

    ctx, cancel := context.WithTimeout(context.Background(), 500*time.Millisecond)
    defer cancel()

    err := sub.Start(ctx)
    if err == nil {
        t.Fatal("expected error for unreachable broker")
    }
}
