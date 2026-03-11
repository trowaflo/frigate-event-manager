package mqttdiscovery

import (
	"context"
	"encoding/json"
	"fmt"
	"log/slog"
	"strings"

	"frigate-event-manager/internal/core/registry"
)

const discoveryPrefix = "homeassistant"
const nodeName = "fem" // Frigate Event Manager

// MQTTPublisher est l'interface pour publier des messages MQTT.
// Implémentée par autopaho.ConnectionManager.
type MQTTPublisher interface {
	Publish(ctx context.Context, topic string, qos byte, retain bool, payload []byte) error
}

// Publisher publie les entités MQTT Discovery pour chaque caméra.
// Il implémente registry.Listener pour être notifié automatiquement.
type Publisher struct {
	mqtt   MQTTPublisher
	logger *slog.Logger
	ctx    context.Context
}

// NewPublisher crée un publisher MQTT Discovery.
func NewPublisher(ctx context.Context, mqtt MQTTPublisher, logger *slog.Logger) *Publisher {
	return &Publisher{
		mqtt:   mqtt,
		logger: logger,
		ctx:    ctx,
	}
}

// OnCameraAdded publie toutes les entités Discovery pour une nouvelle caméra.
func (p *Publisher) OnCameraAdded(cam registry.CameraState) {
	p.publishAll(cam)
}

// OnCameraUpdated met à jour les states des entités existantes.
func (p *Publisher) OnCameraUpdated(cam registry.CameraState) {
	p.publishStates(cam)
}

// PublishAll publie toutes les configs et states pour toutes les caméras.
// Appelé au démarrage pour restaurer les entités après un reboot.
func (p *Publisher) PublishAll(cameras []registry.CameraState) {
	for _, cam := range cameras {
		p.publishAll(cam)
	}
}

func (p *Publisher) publishAll(cam registry.CameraState) {
	p.publishConfig(cam)
	p.publishStates(cam)
}

// publishConfig publie les topics de configuration MQTT Discovery (retain=true).
// Crée les entités dans HA.
func (p *Publisher) publishConfig(cam registry.CameraState) {
	safeName := sanitize(cam.Name)
	device := devicePayload(cam.Name)

	// sensor: last_alert
	p.publishJSON(
		fmt.Sprintf("%s/sensor/%s_%s_last_alert/config", discoveryPrefix, nodeName, safeName),
		map[string]any{
			"name":                "Derniere alerte",
			"unique_id":           fmt.Sprintf("%s_%s_last_alert", nodeName, safeName),
			"state_topic":        fmt.Sprintf("%s/%s/%s/last_alert", nodeName, nodeName, safeName),
			"device":              device,
			"icon":                "mdi:alert-circle",
			"device_class":        "timestamp",
			"entity_category":     "diagnostic",
		},
		true,
	)

	// sensor: last_object
	p.publishJSON(
		fmt.Sprintf("%s/sensor/%s_%s_last_object/config", discoveryPrefix, nodeName, safeName),
		map[string]any{
			"name":               "Dernier objet detecte",
			"unique_id":          fmt.Sprintf("%s_%s_last_object", nodeName, safeName),
			"state_topic":       fmt.Sprintf("%s/%s/%s/last_object", nodeName, nodeName, safeName),
			"device":             device,
			"icon":               "mdi:eye",
		},
		true,
	)

	// sensor: event_count
	p.publishJSON(
		fmt.Sprintf("%s/sensor/%s_%s_event_count/config", discoveryPrefix, nodeName, safeName),
		map[string]any{
			"name":               "Evenements (24h)",
			"unique_id":          fmt.Sprintf("%s_%s_event_count", nodeName, safeName),
			"state_topic":       fmt.Sprintf("%s/%s/%s/event_count", nodeName, nodeName, safeName),
			"device":             device,
			"icon":               "mdi:counter",
			"state_class":        "measurement",
		},
		true,
	)

	// sensor: severity
	p.publishJSON(
		fmt.Sprintf("%s/sensor/%s_%s_severity/config", discoveryPrefix, nodeName, safeName),
		map[string]any{
			"name":               "Severite",
			"unique_id":          fmt.Sprintf("%s_%s_severity", nodeName, safeName),
			"state_topic":       fmt.Sprintf("%s/%s/%s/severity", nodeName, nodeName, safeName),
			"device":             device,
			"icon":               "mdi:shield-alert",
		},
		true,
	)

	// switch: notifications
	p.publishJSON(
		fmt.Sprintf("%s/switch/%s_%s_notifications/config", discoveryPrefix, nodeName, safeName),
		map[string]any{
			"name":               "Notifications",
			"unique_id":          fmt.Sprintf("%s_%s_notifications", nodeName, safeName),
			"state_topic":       fmt.Sprintf("%s/%s/%s/notifications", nodeName, nodeName, safeName),
			"command_topic":      fmt.Sprintf("%s/%s/%s/notifications/set", nodeName, nodeName, safeName),
			"payload_on":         "ON",
			"payload_off":        "OFF",
			"device":             device,
			"icon":               "mdi:bell",
		},
		true,
	)

	p.logger.Info("MQTT Discovery configs publiées", "camera", cam.Name)
}

// publishStates publie les valeurs actuelles des entités.
func (p *Publisher) publishStates(cam registry.CameraState) {
	safeName := sanitize(cam.Name)
	prefix := fmt.Sprintf("%s/%s/%s", nodeName, nodeName, safeName)

	// last_alert : timestamp ISO8601
	if !cam.LastEventTime.IsZero() {
		p.publish(prefix+"/last_alert", cam.LastEventTime.UTC().Format("2006-01-02T15:04:05+00:00"), true)
	}

	// last_object
	objects := "idle"
	if len(cam.LastObjects) > 0 {
		objects = strings.Join(cam.LastObjects, ", ")
	}
	p.publish(prefix+"/last_object", objects, true)

	// event_count
	p.publish(prefix+"/event_count", fmt.Sprintf("%d", cam.EventCount24h), true)

	// severity
	severity := "idle"
	if cam.LastSeverity != "" {
		severity = cam.LastSeverity
	}
	p.publish(prefix+"/severity", severity, true)

	// notifications switch
	notifState := "ON"
	if !cam.Enabled {
		notifState = "OFF"
	}
	p.publish(prefix+"/notifications", notifState, true)
}

func (p *Publisher) publishJSON(topic string, payload map[string]any, retain bool) {
	data, err := json.Marshal(payload)
	if err != nil {
		p.logger.Error("impossible de sérialiser le payload MQTT Discovery", "topic", topic, "error", err)
		return
	}
	p.publish(topic, string(data), retain)
}

func (p *Publisher) publish(topic string, payload string, retain bool) {
	if err := p.mqtt.Publish(p.ctx, topic, 1, retain, []byte(payload)); err != nil {
		p.logger.Error("impossible de publier MQTT Discovery", "topic", topic, "error", err)
	}
}

func devicePayload(cameraName string) map[string]any {
	return map[string]any{
		"identifiers":  []string{fmt.Sprintf("%s_%s", nodeName, sanitize(cameraName))},
		"name":         fmt.Sprintf("FEM %s", cameraName),
		"manufacturer": "Frigate Event Manager",
		"model":        "Camera",
	}
}

func sanitize(name string) string {
	return strings.ReplaceAll(strings.ToLower(name), " ", "_")
}
