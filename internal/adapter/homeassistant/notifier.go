package homeassistant

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"strings"

	"golang.org/x/text/cases"
	"golang.org/x/text/language"

	"frigate-event-manager/internal/domain"
)

// Notifier envoie des notifications via l'API REST de Home Assistant.
// Il implémente l'interface ports.EventHandler.
type Notifier struct {
	baseURL       string // ex: "http://homeassistant.local:8123"
	token         string // Supervisor token (SUPERVISOR_TOKEN)
	notifyService string // ex: "mobile_app_iphone"
	client        *http.Client
}

// NewNotifier crée un notifier HA.
func NewNotifier(baseURL, token, notifyService string) *Notifier {
	return &Notifier{
		baseURL:       strings.TrimRight(baseURL, "/"),
		token:         token,
		notifyService: notifyService,
		client:        &http.Client{},
	}
}

// notificationPayload est le format attendu par l'API notify de HA.
type notificationPayload struct {
	Title   string                 `json:"title"`
	Message string                 `json:"message"`
	Data    map[string]interface{} `json:"data,omitempty"`
}

// HandleEvent construit et envoie une notification pour un événement Frigate.
func (n *Notifier) HandleEvent(payload domain.FrigatePayload) error {
	notif := n.buildNotification(payload)

	body, err := json.Marshal(notif)
	if err != nil {
		return fmt.Errorf("impossible de sérialiser la notification: %w", err)
	}

	url := fmt.Sprintf("%s/api/services/notify/%s", n.baseURL, n.notifyService)

	req, err := http.NewRequest(http.MethodPost, url, bytes.NewReader(body))
	if err != nil {
		return fmt.Errorf("impossible de créer la requête: %w", err)
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Authorization", "Bearer "+n.token)

	resp, err := n.client.Do(req)
	if err != nil {
		return fmt.Errorf("impossible de contacter Home Assistant: %w", err)
	}
	defer func() { _ = resp.Body.Close() }()

	if resp.StatusCode >= 400 {
		respBody, _ := io.ReadAll(resp.Body)
		return fmt.Errorf("home assistant a retourné %d: %s", resp.StatusCode, string(respBody))
	}

	return nil
}

// buildNotification construit le payload de notification à partir de l'événement Frigate.
func (n *Notifier) buildNotification(payload domain.FrigatePayload) notificationPayload {
	after := payload.After

	// Construire le label (ex: "Person" ou "Person (Bob)")
	label := formatLabel(after.Data.Objects, after.Data.SubLabels)

	// Construire le message (ex: "Person dans front_yard")
	zones := strings.Join(after.Data.Zones, ", ")
	message := label
	if zones != "" {
		message = fmt.Sprintf("%s dans %s", label, zones)
	}

	// Camera en titre lisible (front_cam → Front Cam)
	cameraTitle := strings.ReplaceAll(after.Camera, "_", " ")
	cameraTitle = cases.Title(language.English).String(cameraTitle)

	return notificationPayload{
		Title:   fmt.Sprintf("%s — %s", cameraTitle, after.Severity),
		Message: message,
		Data: map[string]interface{}{
			"tag":   "frigate-" + after.ID,
			"group": "frigate-" + after.Camera,
			"image": fmt.Sprintf("/api/frigate/notifications/%s/thumbnail.jpg", after.ID),
		},
	}
}

// formatLabel construit un label lisible à partir des objets et sub_labels.
// Ex: ["person"] + ["Bob"] → "Person (Bob)"
// Ex: ["person", "car"] + [] → "Person, Car"
func formatLabel(objects, subLabels []string) string {
	if len(objects) == 0 {
		return "Détection"
	}

	// Mettre en majuscule le premier caractère de chaque objet
	titles := make([]string, len(objects))
	for i, o := range objects {
		if len(o) > 0 {
			titles[i] = strings.ToUpper(o[:1]) + o[1:]
		}
	}

	label := strings.Join(titles, ", ")

	if len(subLabels) > 0 {
		label = fmt.Sprintf("%s (%s)", label, strings.Join(subLabels, ", "))
	}

	return label
}
