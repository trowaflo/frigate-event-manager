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

func TestSubscriber_SetCommandHandler(t *testing.T) {
	proc := &mockProcessor{}
	handler := mqttadapter.NewMessageHandler(proc)
	logger := slog.Default()

	sub := mqttadapter.NewSubscriber(
		"tcp://localhost:1883", "frigate/reviews", "test-client",
		"", "", handler, logger,
	)

	// SetCommandHandler ne doit pas paniquer
	cmdHandler := &mockCommandHandler{}
	sub.SetCommandHandler(cmdHandler)
	// Pas de moyen direct de vérifier l'état sans exposer le champ,
	// mais on vérifie que l'appel ne panique pas et que ConnectionManager est nil avant Connect
	if sub.ConnectionManager() != nil {
		t.Error("ConnectionManager devrait être nil avant Connect()")
	}
}

func TestSubscriber_Wait_ReturnsOnContextCancel(t *testing.T) {
	proc := &mockProcessor{}
	handler := mqttadapter.NewMessageHandler(proc)
	logger := slog.Default()

	sub := mqttadapter.NewSubscriber(
		"tcp://localhost:1883", "frigate/reviews", "test-client",
		"", "", handler, logger,
	)

	ctx, cancel := context.WithCancel(context.Background())

	done := make(chan error, 1)
	go func() {
		done <- sub.Wait(ctx)
	}()

	// Annuler le contexte après un court délai
	time.AfterFunc(50*time.Millisecond, cancel)

	select {
	case err := <-done:
		if err != nil {
			t.Fatalf("Wait() ne devrait pas retourner d'erreur, reçu: %v", err)
		}
	case <-time.After(500 * time.Millisecond):
		t.Fatal("Wait() n'a pas retourné après l'annulation du contexte")
	}
}

func TestSubscriber_Connect_InvalidURL(t *testing.T) {
	proc := &mockProcessor{}
	handler := mqttadapter.NewMessageHandler(proc)
	logger := slog.Default()

	sub := mqttadapter.NewSubscriber(
		"://invalid", "frigate/reviews", "test-client",
		"", "", handler, logger,
	)

	ctx, cancel := context.WithTimeout(context.Background(), 100*time.Millisecond)
	defer cancel()

	err := sub.Connect(ctx)
	if err == nil {
		t.Fatal("Connect() devrait retourner une erreur pour une URL invalide")
	}
}

// --- mock CommandHandler ---

type mockCommandHandler struct {
	called bool
	topic  string
}

func (m *mockCommandHandler) HandleCommand(topic string, payload []byte) {
	m.called = true
	m.topic = topic
}
