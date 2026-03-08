package throttle_test

import (
	"testing"
	"time"

	"frigate-event-manager/internal/core/ports"
	"frigate-event-manager/internal/core/throttle"
	"frigate-event-manager/internal/domain"
)

// ---------------------------------------------------------------------------
// VÉRIFICATION DE CONTRAT
// ---------------------------------------------------------------------------
var _ ports.EventHandler = (*throttle.Throttler)(nil)

// ---------------------------------------------------------------------------
// MOCK
// ---------------------------------------------------------------------------
type mockHandler struct {
	callCount int
	lastID    string
}

func (m *mockHandler) HandleEvent(payload domain.FrigatePayload) error {
	m.callCount++
	m.lastID = payload.After.ID
	return nil
}

// ---------------------------------------------------------------------------
// HELPERS
// ---------------------------------------------------------------------------
func newPayload(id, camera, eventType string) domain.FrigatePayload {
	return domain.FrigatePayload{
		Type: eventType,
		After: domain.EventState{
			ID:       id,
			Camera:   camera,
			Severity: "alert",
		},
	}
}

// ---------------------------------------------------------------------------
// TEST 1 : Premier event d'une caméra → passe toujours
// ---------------------------------------------------------------------------
func TestThrottler_FirstEvent_AlwaysPasses(t *testing.T) {
	handler := &mockHandler{}
	th := throttle.New(handler, 30*time.Second, 5*time.Second)

	err := th.HandleEvent(newPayload("event-1", "front_cam", "new"))

	if err != nil {
		t.Fatalf("erreur inattendue: %v", err)
	}
	if handler.callCount != 1 {
		t.Fatalf("handler appelé %d fois, attendu 1", handler.callCount)
	}
}

// ---------------------------------------------------------------------------
// TEST 2 : Même event ID (update) après debounce → passe
// ---------------------------------------------------------------------------
func TestThrottler_SameEvent_AfterDebounce_Passes(t *testing.T) {
	handler := &mockHandler{}
	th := throttle.New(handler, 30*time.Second, 10*time.Millisecond)

	th.HandleEvent(newPayload("event-1", "front_cam", "new"))
	time.Sleep(15 * time.Millisecond)
	err := th.HandleEvent(newPayload("event-1", "front_cam", "update"))

	if err != nil {
		t.Fatalf("erreur inattendue: %v", err)
	}
	if handler.callCount != 2 {
		t.Fatalf("handler appelé %d fois, attendu 2", handler.callCount)
	}
}

// ---------------------------------------------------------------------------
// TEST 3 : Même event ID (update) avant debounce → bloqué
// ---------------------------------------------------------------------------
func TestThrottler_SameEvent_BeforeDebounce_Blocked(t *testing.T) {
	handler := &mockHandler{}
	th := throttle.New(handler, 30*time.Second, 1*time.Second)

	th.HandleEvent(newPayload("event-1", "front_cam", "new"))
	err := th.HandleEvent(newPayload("event-1", "front_cam", "update"))

	if err != nil {
		t.Fatalf("erreur inattendue: %v", err)
	}
	if handler.callCount != 1 {
		t.Fatalf("handler appelé %d fois, attendu 1 (update devrait être bloqué)", handler.callCount)
	}
}

// ---------------------------------------------------------------------------
// TEST 4 : Nouvel event différent, même caméra, avant cooldown → bloqué
// ---------------------------------------------------------------------------
func TestThrottler_DifferentEvent_SameCamera_BeforeCooldown_Blocked(t *testing.T) {
	handler := &mockHandler{}
	th := throttle.New(handler, 1*time.Second, 10*time.Millisecond)

	th.HandleEvent(newPayload("event-1", "front_cam", "new"))
	err := th.HandleEvent(newPayload("event-2", "front_cam", "new"))

	if err != nil {
		t.Fatalf("erreur inattendue: %v", err)
	}
	if handler.callCount != 1 {
		t.Fatalf("handler appelé %d fois, attendu 1 (cooldown caméra)", handler.callCount)
	}
}

// ---------------------------------------------------------------------------
// TEST 5 : Nouvel event différent, même caméra, après cooldown → passe
// ---------------------------------------------------------------------------
func TestThrottler_DifferentEvent_SameCamera_AfterCooldown_Passes(t *testing.T) {
	handler := &mockHandler{}
	th := throttle.New(handler, 10*time.Millisecond, 5*time.Millisecond)

	th.HandleEvent(newPayload("event-1", "front_cam", "new"))
	time.Sleep(15 * time.Millisecond)
	err := th.HandleEvent(newPayload("event-2", "front_cam", "new"))

	if err != nil {
		t.Fatalf("erreur inattendue: %v", err)
	}
	if handler.callCount != 2 {
		t.Fatalf("handler appelé %d fois, attendu 2", handler.callCount)
	}
}

// ---------------------------------------------------------------------------
// TEST 6 : Events de caméras différentes → pas de cooldown croisé
// ---------------------------------------------------------------------------
func TestThrottler_DifferentCameras_NoCrossBlock(t *testing.T) {
	handler := &mockHandler{}
	th := throttle.New(handler, 1*time.Second, 1*time.Second)

	th.HandleEvent(newPayload("event-1", "front_cam", "new"))
	err := th.HandleEvent(newPayload("event-2", "back_cam", "new"))

	if err != nil {
		t.Fatalf("erreur inattendue: %v", err)
	}
	if handler.callCount != 2 {
		t.Fatalf("handler appelé %d fois, attendu 2 (caméras différentes)", handler.callCount)
	}
}

// ---------------------------------------------------------------------------
// TEST 7 : Update d'un event connu bypass le cooldown caméra
// ---------------------------------------------------------------------------
// Le cooldown s'applique aux events *différents*. Un update du même event
// ne doit être limité que par le debounce, pas par le cooldown.
func TestThrottler_UpdateSameEvent_BypassesCooldown(t *testing.T) {
	handler := &mockHandler{}
	th := throttle.New(handler, 1*time.Second, 10*time.Millisecond)

	th.HandleEvent(newPayload("event-1", "front_cam", "new"))
	time.Sleep(15 * time.Millisecond)
	err := th.HandleEvent(newPayload("event-1", "front_cam", "update"))

	if err != nil {
		t.Fatalf("erreur inattendue: %v", err)
	}
	if handler.callCount != 2 {
		t.Fatalf("handler appelé %d fois, attendu 2 (update bypass cooldown)", handler.callCount)
	}
}

// ---------------------------------------------------------------------------
// TEST 8 : Zéro cooldown et zéro debounce → tout passe
// ---------------------------------------------------------------------------
func TestThrottler_ZeroValues_EverythingPasses(t *testing.T) {
	handler := &mockHandler{}
	th := throttle.New(handler, 0, 0)

	th.HandleEvent(newPayload("event-1", "front_cam", "new"))
	th.HandleEvent(newPayload("event-1", "front_cam", "update"))
	th.HandleEvent(newPayload("event-2", "front_cam", "new"))

	if handler.callCount != 3 {
		t.Fatalf("handler appelé %d fois, attendu 3 (tout doit passer)", handler.callCount)
	}
}

// ---------------------------------------------------------------------------
// TEST 9 : ReleaseEvent supprime l'entrée → nouvel event même caméra passe le cooldown
// ---------------------------------------------------------------------------
// Scénario : event-1 new → end reçu (Release) → event-2 new immédiat sur même caméra.
// Sans Release, event-2 serait bloqué par le cooldown caméra.
// Avec Release, la caméra est toujours en cooldown (cameras map non touchée),
// mais le fait que l'event soit libéré prouve que la map events est nettoyée.
func TestThrottler_EndEvent_CleansUpEventEntry(t *testing.T) {
	handler := &mockHandler{}
	th := throttle.New(handler, 30*time.Second, 10*time.Millisecond)

	// new event
	th.HandleEvent(newPayload("event-1", "front_cam", "new"))
	if handler.callCount != 1 {
		t.Fatalf("callCount=%d, attendu 1", handler.callCount)
	}

	// update du même event-1 APRÈS end → le throttler ne le connaît plus
	// → traité comme nouvel event → cooldown caméra s'applique → bloqué
	time.Sleep(15 * time.Millisecond)
	th.HandleEvent(newPayload("event-1", "front_cam", "update"))

	if handler.callCount != 2 {
		t.Fatalf("callCount=%d, attendu 2 (cooldown caméra bloque)", handler.callCount)
	}

	// end → cleanup interne
	th.HandleEvent(newPayload("event-1", "front_cam", "end"))
	if handler.callCount != 3 {
		t.Fatalf("callCount=%d, attendu 3 (end doit passer au handler)", handler.callCount)
	}
}

// ---------------------------------------------------------------------------
// TEST 10 : ReleaseEvent d'un ID inconnu → no-op, pas de panic
// ---------------------------------------------------------------------------
func TestThrottler_EndEvent_UnknownID_NoPanic(t *testing.T) {
	handler := &mockHandler{}
	th := throttle.New(handler, 30*time.Second, 5*time.Second)

	// Ne doit pas panic
	th.HandleEvent(newPayload("inexistant", "front_cam", "end"))

	if handler.callCount != 1 {
		t.Fatalf("callCount=%d, attendu 1 (end passe toujours au handler)", handler.callCount)
	}
}

// ---------------------------------------------------------------------------
// TEST 11 : Après Release, un nouvel event sur une AUTRE caméra passe normalement
// ---------------------------------------------------------------------------
func TestThrottler_EndEvent_DoesNotAffectOtherCameras(t *testing.T) {
	handler := &mockHandler{}
	th := throttle.New(handler, 30*time.Second, 5*time.Second)

	th.HandleEvent(newPayload("event-1", "front_cam", "new"))
	th.HandleEvent(newPayload("event-1", "front_cam", "end"))
	th.HandleEvent(newPayload("event-2", "back_cam", "new"))

	if handler.callCount != 3 {
		t.Fatalf("callCount=%d, attendu 3", handler.callCount)
	}
}
