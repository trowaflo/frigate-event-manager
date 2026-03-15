package homeassistant_test

import (
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"testing"

	"frigate-event-manager/internal/adapter/homeassistant"
	"frigate-event-manager/internal/core/ports"
	"frigate-event-manager/internal/domain"
)

type fakeSigner struct{}

func (f *fakeSigner) SignURL(path string) string {
	return "http://localhost:5555" + path + "?exp=9999999999&sig=fakesig"
}

var _ ports.MediaSigner = (*fakeSigner)(nil)

func newTestPayload() domain.FrigatePayload {
	return domain.FrigatePayload{
		Type: "new",
		After: domain.EventState{
			ID:       "1718987129.308396-fqk5ka",
			Camera:   "front_cam",
			Severity: "alert",
			Data: domain.EventData{
				Objects:    []string{"person"},
				SubLabels:  []string{"Bob"},
				Zones:      []string{"front_yard"},
				Detections: []string{"1718987127.123456-abc123"},
			},
		},
	}
}

func TestNotifier_SendsCorrectHTTPRequest(t *testing.T) {
	var receivedBody []byte
	var receivedAuth string
	var receivedPath string

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		receivedPath = r.URL.Path
		receivedAuth = r.Header.Get("Authorization")
		receivedBody, _ = io.ReadAll(r.Body)
		w.WriteHeader(http.StatusOK)
	}))
	defer server.Close()

	notifier := homeassistant.NewNotifier(server.URL, "my-secret-token", "mobile_app_iphone", &fakeSigner{})

	err := notifier.HandleEvent(newTestPayload())
	if err != nil {
		t.Fatalf("erreur inattendue: %v", err)
	}

	expected := "/api/services/notify/mobile_app_iphone"
	if receivedPath != expected {
		t.Errorf("path attendu %q, reçu %q", expected, receivedPath)
	}
	if receivedAuth != "Bearer my-secret-token" {
		t.Errorf("auth attendue 'Bearer my-secret-token', reçue %q", receivedAuth)
	}

	var body map[string]any
	if err := json.Unmarshal(receivedBody, &body); err != nil {
		t.Fatalf("body n'est pas du JSON valide: %v", err)
	}
	if body["title"] == nil || body["title"] == "" {
		t.Error("title ne devrait pas être vide")
	}
	if body["message"] == nil || body["message"] == "" {
		t.Error("message ne devrait pas être vide")
	}

	// Vérifier que les presigned URLs sont dans le payload
	data, _ := body["data"].(map[string]any)
	image, _ := data["image"].(string)
	if image == "" {
		t.Error("image devrait contenir une presigned URL")
	}
}

func TestNotifier_IncludesPresignedURLs(t *testing.T) {
	var receivedBody []byte
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		receivedBody, _ = io.ReadAll(r.Body)
		w.WriteHeader(http.StatusOK)
	}))
	defer server.Close()

	notifier := homeassistant.NewNotifier(server.URL, "token", "mobile_app_iphone", &fakeSigner{})

	err := notifier.HandleEvent(newTestPayload())
	if err != nil {
		t.Fatalf("erreur inattendue: %v", err)
	}

	var body map[string]any
	if err := json.Unmarshal(receivedBody, &body); err != nil {
		t.Fatalf("body invalide: %v", err)
	}

	data, _ := body["data"].(map[string]any)
	tag, _ := data["tag"].(string)
	if tag == "" {
		t.Error("tag ne devrait pas être vide")
	}
	image, _ := data["image"].(string)
	if image == "" {
		t.Error("image presigned URL manquante")
	}
	clickAction, _ := data["clickAction"].(string)
	if clickAction == "" {
		t.Error("clickAction presigned URL manquante")
	}
}

func TestNotifier_HAReturnsError_ReturnsError(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusInternalServerError)
		_, _ = w.Write([]byte(`{"message": "internal error"}`))
	}))
	defer server.Close()

	notifier := homeassistant.NewNotifier(server.URL, "token", "mobile_app_iphone", &fakeSigner{})
	err := notifier.HandleEvent(newTestPayload())
	if err == nil {
		t.Fatal("une erreur était attendue quand HA retourne 500")
	}
}

func TestNotifier_HAUnreachable_ReturnsError(t *testing.T) {
	notifier := homeassistant.NewNotifier("http://localhost:1", "token", "mobile_app_iphone", &fakeSigner{})
	err := notifier.HandleEvent(newTestPayload())
	if err == nil {
		t.Fatal("une erreur était attendue quand HA est injoignable")
	}
}

func TestNotifier_EmptyObjectString_HandledGracefully(t *testing.T) {
	var receivedBody []byte
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		receivedBody, _ = io.ReadAll(r.Body)
		w.WriteHeader(http.StatusOK)
	}))
	defer server.Close()

	notifier := homeassistant.NewNotifier(server.URL, "token", "mobile_app_iphone", nil)

	payload := domain.FrigatePayload{
		Type: "new",
		After: domain.EventState{
			ID:       "test-123",
			Camera:   "front_cam",
			Severity: "alert",
			Data: domain.EventData{
				Objects: []string{""},
			},
		},
	}

	err := notifier.HandleEvent(payload)
	if err != nil {
		t.Fatalf("erreur inattendue: %v", err)
	}

	var body map[string]any
	if err := json.Unmarshal(receivedBody, &body); err != nil {
		t.Fatalf("body invalide: %v", err)
	}
	if body["message"] == nil || body["message"] == "" {
		t.Error("message ne devrait pas être vide même avec un objet vide")
	}
}

func TestNotifier_NilSigner_NoMediaURLs(t *testing.T) {
	var receivedBody []byte
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		receivedBody, _ = io.ReadAll(r.Body)
		w.WriteHeader(http.StatusOK)
	}))
	defer server.Close()

	notifier := homeassistant.NewNotifier(server.URL, "token", "mobile_app_iphone", nil)
	err := notifier.HandleEvent(newTestPayload())
	if err != nil {
		t.Fatalf("erreur inattendue: %v", err)
	}

	var body map[string]any
	if err := json.Unmarshal(receivedBody, &body); err != nil {
		t.Fatalf("body invalide: %v", err)
	}
	data, _ := body["data"].(map[string]any)
	if data["image"] != nil {
		t.Error("image ne devrait pas être présent sans signer")
	}
}

func TestNotifier_InvalidURL_ReturnsError(t *testing.T) {
	notifier := homeassistant.NewNotifier("://invalid", "token", "mobile_app_iphone", nil)
	err := notifier.HandleEvent(newTestPayload())
	if err == nil {
		t.Fatal("une erreur était attendue avec une URL invalide")
	}
}
