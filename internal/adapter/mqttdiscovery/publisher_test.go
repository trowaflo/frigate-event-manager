package mqttdiscovery

import (
	"context"
	"encoding/json"
	"fmt"
	"log/slog"
	"os"
	"strings"
	"sync"
	"testing"
	"time"

	"frigate-event-manager/internal/core/registry"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

type publishedMsg struct {
	Topic   string
	Payload string
	Retain  bool
}

type fakeMQTT struct {
	mu       sync.Mutex
	messages []publishedMsg
}

func (f *fakeMQTT) Publish(_ context.Context, topic string, _ byte, retain bool, payload []byte) error {
	f.mu.Lock()
	defer f.mu.Unlock()
	f.messages = append(f.messages, publishedMsg{Topic: topic, Payload: string(payload), Retain: retain})
	return nil
}

func (f *fakeMQTT) findByTopic(substr string) []publishedMsg {
	f.mu.Lock()
	defer f.mu.Unlock()
	var result []publishedMsg
	for _, m := range f.messages {
		if strings.Contains(m.Topic, substr) {
			result = append(result, m)
		}
	}
	return result
}

func TestPublisher_OnCameraAdded_PublishesConfigAndState(t *testing.T) {
	mqtt := &fakeMQTT{}
	logger := slog.New(slog.NewTextHandler(os.Stderr, nil))
	pub := NewPublisher(context.Background(), mqtt, logger)

	cam := registry.CameraState{
		Name:          "jardin_nord",
		Enabled:       true,
		FirstSeen:     time.Now(),
		LastEventTime: time.Date(2025, 1, 1, 14, 32, 0, 0, time.UTC),
		LastSeverity:  "alert",
		LastObjects:   []string{"person"},
		EventCount24h: 5,
	}

	pub.OnCameraAdded(cam)

	// Vérifier les configs Discovery (5 entités)
	configs := mqtt.findByTopic("/config")
	assert.Len(t, configs, 5, "5 configs Discovery attendues")

	// Vérifier que c'est du JSON valide avec les bons champs
	for _, cfg := range configs {
		assert.True(t, cfg.Retain, "configs doivent être retain")
		var payload map[string]any
		require.NoError(t, json.Unmarshal([]byte(cfg.Payload), &payload))
		assert.Contains(t, payload, "unique_id")
		assert.Contains(t, payload, "device")
	}

	// Vérifier les states
	lastAlert := mqtt.findByTopic("last_alert")
	// 1 config + 1 state
	assert.Len(t, lastAlert, 2)

	lastObject := mqtt.findByTopic("last_object")
	assert.Len(t, lastObject, 2)
	// Le state du dernier objet
	assert.Equal(t, "person", lastObject[1].Payload)

	eventCount := mqtt.findByTopic("event_count")
	assert.Len(t, eventCount, 2)
	assert.Equal(t, "5", eventCount[1].Payload)

	notifs := mqtt.findByTopic("notifications")
	// config notifications + state notifications (pas les /set)
	var stateNotifs []publishedMsg
	for _, m := range notifs {
		if !strings.Contains(m.Topic, "/set") && !strings.Contains(m.Topic, "/config") {
			stateNotifs = append(stateNotifs, m)
		}
	}
	assert.Len(t, stateNotifs, 1)
	assert.Equal(t, "ON", stateNotifs[0].Payload)
}

func TestPublisher_OnCameraUpdated_PublishesOnlyStates(t *testing.T) {
	mqtt := &fakeMQTT{}
	logger := slog.New(slog.NewTextHandler(os.Stderr, nil))
	pub := NewPublisher(context.Background(), mqtt, logger)

	cam := registry.CameraState{
		Name:          "garage",
		Enabled:       false,
		LastSeverity:  "detection",
		LastObjects:   []string{"car", "person"},
		EventCount24h: 12,
	}

	pub.OnCameraUpdated(cam)

	// Pas de configs (update, pas add)
	configs := mqtt.findByTopic("/config")
	assert.Empty(t, configs, "update ne doit pas republier les configs")

	// Vérifier les states
	severity := mqtt.findByTopic("severity")
	assert.Len(t, severity, 1)
	assert.Equal(t, "detection", severity[0].Payload)

	lastObject := mqtt.findByTopic("last_object")
	assert.Len(t, lastObject, 1)
	assert.Equal(t, "car, person", lastObject[0].Payload)

	var stateNotifs []publishedMsg
	for _, m := range mqtt.findByTopic("notifications") {
		if !strings.Contains(m.Topic, "/config") && !strings.Contains(m.Topic, "/set") {
			stateNotifs = append(stateNotifs, m)
		}
	}
	require.Len(t, stateNotifs, 1)
	assert.Equal(t, "OFF", stateNotifs[0].Payload, "disabled camera = OFF")
}

func TestPublisher_PublishAll_RestoresOnBoot(t *testing.T) {
	mqtt := &fakeMQTT{}
	logger := slog.New(slog.NewTextHandler(os.Stderr, nil))
	pub := NewPublisher(context.Background(), mqtt, logger)

	cameras := []registry.CameraState{
		{Name: "jardin", Enabled: true, LastSeverity: "alert"},
		{Name: "garage", Enabled: false, LastSeverity: "detection"},
	}

	pub.PublishAll(cameras)

	// 5 configs * 2 cameras = 10 configs
	configs := mqtt.findByTopic("/config")
	assert.Len(t, configs, 10)
}

// TestPublisher_Publish_EchecMQTT valide que l'erreur de publication est loguée sans paniquer.
func TestPublisher_Publish_EchecMQTT(t *testing.T) {
	mqttErr := &errorMQTT{}
	logger := slog.New(slog.NewTextHandler(os.Stderr, nil))
	pub := NewPublisher(context.Background(), mqttErr, logger)

	cam := registry.CameraState{
		Name:          "jardin",
		Enabled:       true,
		LastSeverity:  "alert",
		LastObjects:   []string{"person"},
		EventCount24h: 1,
	}

	// Ne doit pas paniquer même si MQTT retourne une erreur
	assert.NotPanics(t, func() {
		pub.OnCameraAdded(cam)
	})
}

// TestPublisher_NewAutopahoAdapter valide la construction via NewAutopahoAdapter.
// On ne peut pas tester Publish sans serveur MQTT réel, mais on vérifie la construction.
func TestPublisher_NewAutopahoAdapter_NonNil(t *testing.T) {
	// NewAutopahoAdapter attend un *autopaho.ConnectionManager qui peut être nil.
	// On vérifie simplement que la construction fonctionne.
	adapter := NewAutopahoAdapter(nil)
	assert.NotNil(t, adapter)
}

// --- mocks supplémentaires ---

// errorMQTT est un mock MQTT qui retourne toujours une erreur.
type errorMQTT struct{}

func (e *errorMQTT) Publish(_ context.Context, _ string, _ byte, _ bool, _ []byte) error {
	return fmt.Errorf("erreur MQTT simulée")
}
