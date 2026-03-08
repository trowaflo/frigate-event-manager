package homeassistant_test

import (
    "encoding/json"
    "io"
    "net/http"
    "net/http/httptest"
    "testing"

    "frigate-event-manager/internal/adapter/homeassistant"
    "frigate-event-manager/internal/domain"
)

func newTestPayload() domain.FrigatePayload {
    return domain.FrigatePayload{
        Type: "new",
        After: domain.EventState{
            ID:       "1718987129.308396-fqk5ka",
            Camera:   "front_cam",
            Severity: "alert",
            Data: domain.EventData{
                Objects:   []string{"person"},
                SubLabels: []string{"Bob"},
                Zones:     []string{"front_yard"},
            },
        },
    }
}

func TestNotifier_SendsCorrectHTTPRequest(t *testing.T) {
    // GIVEN : un faux serveur HA qui enregistre la requête reçue
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

    notifier := homeassistant.NewNotifier(server.URL, "my-secret-token", "mobile_app_iphone")

    // WHEN : on envoie une notification
    err := notifier.HandleEvent(newTestPayload())

    // THEN : la requête est correcte
    if err != nil {
        t.Fatalf("erreur inattendue: %v", err)
    }

    // Vérifier le path
    expected := "/api/services/notify/mobile_app_iphone"
    if receivedPath != expected {
        t.Errorf("path attendu %q, reçu %q", expected, receivedPath)
    }

    // Vérifier l'authentification Bearer
    if receivedAuth != "Bearer my-secret-token" {
        t.Errorf("auth attendue 'Bearer my-secret-token', reçue %q", receivedAuth)
    }

    // Vérifier le body JSON
    var body map[string]interface{}
    if err := json.Unmarshal(receivedBody, &body); err != nil {
        t.Fatalf("body n'est pas du JSON valide: %v", err)
    }
    if body["title"] == nil || body["title"] == "" {
        t.Error("title ne devrait pas être vide")
    }
    if body["message"] == nil || body["message"] == "" {
        t.Error("message ne devrait pas être vide")
    }
}

func TestNotifier_IncludesImageAndTag(t *testing.T) {
    // GIVEN
    server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        body, _ := io.ReadAll(r.Body)
        var payload map[string]interface{}
        json.Unmarshal(body, &payload)

        data, ok := payload["data"].(map[string]interface{})
        if !ok {
            http.Error(w, "missing data", 400)
            return
        }

        // Le tag doit contenir le review_id pour permettre les updates
        tag, _ := data["tag"].(string)
        if tag == "" {
            http.Error(w, "missing tag", 400)
            return
        }

        w.WriteHeader(http.StatusOK)
    }))
    defer server.Close()

    notifier := homeassistant.NewNotifier(server.URL, "token", "mobile_app_iphone")

    // WHEN
    err := notifier.HandleEvent(newTestPayload())

    // THEN
    if err != nil {
        t.Fatalf("erreur inattendue: %v", err)
    }
}

func TestNotifier_HAReturnsError_ReturnsError(t *testing.T) {
    // GIVEN : HA retourne une erreur 500
    server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        w.WriteHeader(http.StatusInternalServerError)
        w.Write([]byte(`{"message": "internal error"}`))
    }))
    defer server.Close()

    notifier := homeassistant.NewNotifier(server.URL, "token", "mobile_app_iphone")

    // WHEN
    err := notifier.HandleEvent(newTestPayload())

    // THEN : l'erreur remonte
    if err == nil {
        t.Fatal("une erreur était attendue quand HA retourne 500")
    }
}

func TestNotifier_HAUnreachable_ReturnsError(t *testing.T) {
    // GIVEN : HA est injoignable (URL bidon)
    notifier := homeassistant.NewNotifier("http://localhost:1", "token", "mobile_app_iphone")

    // WHEN
    err := notifier.HandleEvent(newTestPayload())

    // THEN
    if err == nil {
        t.Fatal("une erreur était attendue quand HA est injoignable")
    }
}
