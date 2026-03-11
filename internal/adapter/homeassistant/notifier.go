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

	"frigate-event-manager/internal/core/ports"
	"frigate-event-manager/internal/domain"
)

// Notifier envoie des notifications via l'API REST de Home Assistant.
// Il implémente l'interface ports.EventHandler.
type Notifier struct {
	baseURL       string // ex: "http://homeassistant.local:8123"
	token         string // Supervisor token (SUPERVISOR_TOKEN)
	notifyService string // ex: "mobile_app_iphone"
	signer        ports.MediaSigner
	client        *http.Client
}

// NewNotifier crée un notifier HA.
// signer peut être nil si le proxy media n'est pas configuré.
func NewNotifier(baseURL, token, notifyService string, signer ports.MediaSigner) *Notifier {
	return &Notifier{
		baseURL:       strings.TrimRight(baseURL, "/"),
		token:         token,
		notifyService: notifyService,
		signer:        signer,
		client:        &http.Client{},
	}
}

// notificationPayload est le format attendu par l'API notify de HA.
type notificationPayload struct {
	Title   string         `json:"title"`
	Message string         `json:"message"`
	Data    map[string]any `json:"data,omitempty"`
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

	label := formatLabel(after.Data.Objects, after.Data.SubLabels)

	zones := strings.Join(after.Data.Zones, ", ")
	message := label
	if zones != "" {
		message = fmt.Sprintf("%s dans %s", label, zones)
	}

	cameraTitle := strings.ReplaceAll(after.Camera, "_", " ")
	cameraTitle = cases.Title(language.English).String(cameraTitle)

	data := map[string]any{
		"tag":   "frigate-" + after.ID,
		"group": "frigate-" + after.Camera,
	}

	// Media URLs presignées
	if n.signer != nil && len(after.Data.Detections) > 0 {
		detID := after.Data.Detections[0]
		snapshotURL := n.signer.SignURL("/api/events/" + detID + "/snapshot.jpg")
		clipURL := n.signer.SignURL("/api/events/" + detID + "/clip.mp4")

		data["image"] = snapshotURL
		data["clickAction"] = clipURL

		// Pour persistent_notification (et tout service texte) :
		// ajouter les liens media dans le message en markdown.
		message += fmt.Sprintf("\n\n[![Snapshot](%s)](%s)", snapshotURL, clipURL)
	}

	// Preview du review (si disponible)
	if n.signer != nil && after.ID != "" {
		previewURL := n.signer.SignURL("/api/review/" + after.ID + "/preview")
		message += fmt.Sprintf("\n\n[Voir le preview](%s)", previewURL)
	}

	return notificationPayload{
		Title:   fmt.Sprintf("%s — %s", cameraTitle, after.Severity),
		Message: message,
		Data:    data,
	}
}

// formatLabel construit un label lisible à partir des objets et sub_labels.
func formatLabel(objects, subLabels []string) string {
	var filtered []string
	for _, o := range objects {
		if o != "" {
			filtered = append(filtered, o)
		}
	}

	if len(filtered) == 0 {
		return "Détection"
	}

	titles := make([]string, len(filtered))
	for i, o := range filtered {
		titles[i] = strings.ToUpper(o[:1]) + o[1:]
	}

	label := strings.Join(titles, ", ")

	if len(subLabels) > 0 {
		label = fmt.Sprintf("%s (%s)", label, strings.Join(subLabels, ", "))
	}

	return label
}
