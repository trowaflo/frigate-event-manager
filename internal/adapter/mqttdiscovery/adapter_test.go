package mqttdiscovery

import (
	"log/slog"
	"os"
	"path/filepath"
	"testing"

	"frigate-event-manager/internal/core/registry"

	"github.com/stretchr/testify/assert"
)

func TestSwitchCommandHandler_ON(t *testing.T) {
	reg := registry.New(filepath.Join(t.TempDir(), "state.json"))
	reg.RecordEvent("jardin", "alert", []string{"person"})
	_ = reg.SetEnabled("jardin", false)

	handler := NewSwitchCommandHandler(reg, slog.New(slog.NewTextHandler(os.Stderr, nil)))
	handler.HandleCommand("fem/fem/jardin/notifications/set", []byte("ON"))

	assert.True(t, reg.IsEnabled("jardin"))
}

func TestSwitchCommandHandler_OFF(t *testing.T) {
	reg := registry.New(filepath.Join(t.TempDir(), "state.json"))
	reg.RecordEvent("garage", "detection", []string{"car"})

	handler := NewSwitchCommandHandler(reg, slog.New(slog.NewTextHandler(os.Stderr, nil)))
	handler.HandleCommand("fem/fem/garage/notifications/set", []byte("OFF"))

	assert.False(t, reg.IsEnabled("garage"))
}

func TestSwitchCommandHandler_InvalidTopic(t *testing.T) {
	reg := registry.New(filepath.Join(t.TempDir(), "state.json"))
	handler := NewSwitchCommandHandler(reg, slog.New(slog.NewTextHandler(os.Stderr, nil)))

	// Ne devrait pas paniquer
	handler.HandleCommand("invalid/topic", []byte("ON"))
}

func TestSwitchCommandHandler_UnknownCamera(t *testing.T) {
	reg := registry.New(filepath.Join(t.TempDir(), "state.json"))
	handler := NewSwitchCommandHandler(reg, slog.New(slog.NewTextHandler(os.Stderr, nil)))

	// Ne devrait pas paniquer, juste loguer un warning
	handler.HandleCommand("fem/fem/inconnu/notifications/set", []byte("ON"))
}
