package mqtt_test

import (
	"encoding/json"
	"testing"

	mqttadapter "frigate-event-manager/internal/adapter/mqtt"
	"frigate-event-manager/internal/domain"
)

// mockProcessor enregistre les appels à ProcessEvent.
type mockProcessor struct {
	called  bool
	payload domain.FrigatePayload
}

func (m *mockProcessor) ProcessEvent(payload domain.FrigatePayload) error {
	m.called = true
	m.payload = payload
	return nil
}

func TestHandleMessage_ValidNewEvent_CallsProcessor(t *testing.T) {
	// GIVEN : un message MQTT valide de type "new"
	proc := &mockProcessor{}
	handler := mqttadapter.NewMessageHandler(proc)

	payload := domain.FrigatePayload{
		Type: "new",
		After: domain.EventState{
			ID:       "1718987129.308396-fqk5ka",
			Camera:   "front_cam",
			Severity: "alert",
			Data: domain.EventData{
				Objects: []string{"person"},
				Zones:   []string{"front_yard"},
			},
		},
	}
	raw, _ := json.Marshal(payload)

	// WHEN : le message arrive
	err := handler.Handle(raw)

	// THEN : le processor est appelé avec le bon payload
	if err != nil {
		t.Fatalf("erreur inattendue: %v", err)
	}
	if !proc.called {
		t.Fatal("le processor aurait dû être appelé")
	}
	if proc.payload.After.Camera != "front_cam" {
		t.Errorf("camera attendue 'front_cam', reçue '%s'", proc.payload.After.Camera)
	}
	if proc.payload.Type != "new" {
		t.Errorf("type attendu 'new', reçu '%s'", proc.payload.Type)
	}
}

func TestHandleMessage_InvalidJSON_ReturnsError(t *testing.T) {
	// GIVEN : du JSON cassé (ça arrive : réseau coupé, message tronqué...)
	proc := &mockProcessor{}
	handler := mqttadapter.NewMessageHandler(proc)

	// WHEN
	err := handler.Handle([]byte(`{invalid json`))

	// THEN : erreur de parsing, processor PAS appelé
	if err == nil {
		t.Fatal("une erreur de parsing était attendue")
	}
	if proc.called {
		t.Error("le processor ne devrait PAS être appelé avec du JSON invalide")
	}
}

func TestHandleMessage_EmptyPayload_ReturnsError(t *testing.T) {
	// GIVEN : un message vide
	proc := &mockProcessor{}
	handler := mqttadapter.NewMessageHandler(proc)

	// WHEN
	err := handler.Handle([]byte{})

	// THEN
	if err == nil {
		t.Fatal("une erreur était attendue pour un payload vide")
	}
	if proc.called {
		t.Error("le processor ne devrait PAS être appelé avec un payload vide")
	}
}
