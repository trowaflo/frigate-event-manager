package processor_test

import (
    "errors"
    "testing"

    "frigate-event-manager/internal/core/filter"
    "frigate-event-manager/internal/core/ports"
    "frigate-event-manager/internal/core/processor"
    "frigate-event-manager/internal/domain"
)

// ---------------------------------------------------------------------------
// VÉRIFICATION DE CONTRAT
// ---------------------------------------------------------------------------
// Cette ligne ne compile que si *processor.Processor implémente bien
// l'interface ports.EventProcessor. Si quelqu'un change la signature
// de ProcessEvent() → erreur de compilation immédiate, pas de surprise.
var _ ports.EventProcessor = (*processor.Processor)(nil)

// ---------------------------------------------------------------------------
// MOCK : un faux handler qui espionne les appels
// ---------------------------------------------------------------------------
// En test, on ne veut pas envoyer de vraies notifications.
// Ce mock enregistre tout : "on m'a appelé ?", "avec quoi ?", "je simule une erreur ?"
type mockHandler struct {
    called  bool                   // est-ce que HandleEvent a été appelé ?
    payload domain.FrigatePayload  // avec quel payload ?
    err     error                  // erreur à retourner (nil = succès)
}

func (m *mockHandler) HandleEvent(payload domain.FrigatePayload) error {
    m.called = true
    m.payload = payload
    return m.err
}

// ---------------------------------------------------------------------------
// HELPER : construit un FrigatePayload réaliste pour les tests
// ---------------------------------------------------------------------------
// On simule un vrai flux Frigate : caméra, ID, severity, objets...
func newTestPayload(eventType, severity string, objects []string) domain.FrigatePayload {
    return domain.FrigatePayload{
        Type: eventType,
        After: domain.EventState{
            ID:       "1718987129.308396-fqk5ka",
            Camera:   "front_cam",
            Severity: severity,
            Data: domain.EventData{
                Objects: objects,
                Zones:   []string{"front_yard"},
            },
        },
    }
}

// ---------------------------------------------------------------------------
// TEST 1 : Événement "new" + filtre OK → le handler est appelé avec le bon payload
// ---------------------------------------------------------------------------
// C'est le cas nominal : Frigate détecte une personne, severity = alert,
// notre filtre accepte les alerts → on doit notifier.
func TestProcessor_NewEvent_PassesFilter_CallsHandler(t *testing.T) {
    handler := &mockHandler{}
    chain := filter.NewFilterChain(
        filter.NewSeverityFilter([]string{"alert"}),
    )
    proc := processor.NewProcessor(chain, handler)

    payload := newTestPayload("new", "alert", []string{"person"})
    err := proc.ProcessEvent(payload)

    if err != nil {
        t.Fatalf("erreur inattendue: %v", err)
    }
    if !handler.called {
        t.Fatal("le handler aurait dû être appelé")
    }
    // On vérifie que le handler a reçu EXACTEMENT le bon payload
    if handler.payload.After.ID != "1718987129.308396-fqk5ka" {
        t.Errorf("ID attendu '1718987129.308396-fqk5ka', reçu '%s'", handler.payload.After.ID)
    }
    if handler.payload.After.Camera != "front_cam" {
        t.Errorf("camera attendue 'front_cam', reçue '%s'", handler.payload.After.Camera)
    }
}

// ---------------------------------------------------------------------------
// TEST 2 : Événement "new" + filtre KO → le handler n'est PAS appelé
// ---------------------------------------------------------------------------
// L'utilisateur ne veut que les "alert", mais Frigate envoie une "detection".
// Le processor doit bloquer l'événement SILENCIEUSEMENT (pas d'erreur).
func TestProcessor_NewEvent_FailsFilter_HandlerNotCalled(t *testing.T) {
    handler := &mockHandler{}
    chain := filter.NewFilterChain(
        filter.NewSeverityFilter([]string{"alert"}),
    )
    proc := processor.NewProcessor(chain, handler)

    err := proc.ProcessEvent(newTestPayload("new", "detection", []string{"person"}))

    if err != nil {
        t.Fatalf("erreur inattendue: %v", err)
    }
    if handler.called {
        t.Error("le handler ne devrait PAS être appelé quand le filtre bloque")
    }
}

// ---------------------------------------------------------------------------
// TEST 3 : Événement "update" + filtre OK → le handler est appelé
// ---------------------------------------------------------------------------
// Frigate envoie un update quand l'événement évolue (ex: severity passe
// de detection → alert, zones/sub_labels ajoutés). On doit le traiter
// exactement comme un "new" : filtre sur After, handler si ça passe.
// Le tag dans la notification garantit que c'est une mise à jour, pas un doublon.
func TestProcessor_UpdateEvent_PassesFilter_CallsHandler(t *testing.T) {
    handler := &mockHandler{}
    chain := filter.NewFilterChain(
        filter.NewSeverityFilter([]string{"alert"}),
    )
    proc := processor.NewProcessor(chain, handler)

    payload := newTestPayload("update", "alert", []string{"person"})
    err := proc.ProcessEvent(payload)

    if err != nil {
        t.Fatalf("erreur inattendue: %v", err)
    }
    if !handler.called {
        t.Fatal("le handler aurait dû être appelé pour un update qui passe le filtre")
    }
}

// ---------------------------------------------------------------------------
// TEST 4 : Événement "update" + filtre KO → le handler n'est PAS appelé
// ---------------------------------------------------------------------------
// L'update est à severity "detection" mais le filtre n'accepte que "alert".
// Pas de notification. Quand un prochain update arrivera avec "alert", ça passera.
func TestProcessor_UpdateEvent_FailsFilter_HandlerNotCalled(t *testing.T) {
    handler := &mockHandler{}
    chain := filter.NewFilterChain(
        filter.NewSeverityFilter([]string{"alert"}),
    )
    proc := processor.NewProcessor(chain, handler)

    err := proc.ProcessEvent(newTestPayload("update", "detection", []string{"person"}))

    if err != nil {
        t.Fatalf("erreur inattendue: %v", err)
    }
    if handler.called {
        t.Error("le handler ne devrait PAS être appelé quand le filtre bloque un update")
    }
}

// ---------------------------------------------------------------------------
// TEST 5 : Les événements "end" sont ignorés (pour l'instant)
// ---------------------------------------------------------------------------
func TestProcessor_IgnoresEndEvents(t *testing.T) {
    handler := &mockHandler{}
    chain := filter.NewFilterChain()
    proc := processor.NewProcessor(chain, handler)

    err := proc.ProcessEvent(newTestPayload("end", "alert", []string{"person"}))

    if err != nil {
        t.Fatalf("erreur inattendue: %v", err)
    }
    if handler.called {
        t.Error("les événements 'end' doivent être ignorés")
    }
}

// ---------------------------------------------------------------------------
// TEST 6 : Si le handler retourne une erreur, le processor la remonte
// ---------------------------------------------------------------------------
// Exemple : la notification iOS échoue. Le processor ne doit pas avaler
// l'erreur silencieusement — il la remonte pour que l'appelant puisse réagir.
func TestProcessor_HandlerError_IsReturned(t *testing.T) {
    handler := &mockHandler{err: errors.New("notification failed")}
    chain := filter.NewFilterChain()
    proc := processor.NewProcessor(chain, handler)

    err := proc.ProcessEvent(newTestPayload("new", "alert", []string{"person"}))

    if err == nil {
        t.Fatal("une erreur était attendue")
    }
    if err.Error() != "notification failed" {
        t.Errorf("erreur attendue 'notification failed', reçue '%v'", err)
    }
}

// ---------------------------------------------------------------------------
// TEST 7 : Sans filtre, tout passe
// ---------------------------------------------------------------------------
// Cas où l'utilisateur n'a configuré aucun filtre → pas de blocage.
func TestProcessor_NoFilters_AcceptsAll(t *testing.T) {
    handler := &mockHandler{}
    chain := filter.NewFilterChain() // chaîne vide = tout passe
    proc := processor.NewProcessor(chain, handler)

    err := proc.ProcessEvent(newTestPayload("new", "detection", []string{"car"}))

    if err != nil {
        t.Fatalf("erreur inattendue: %v", err)
    }
    if !handler.called {
        t.Error("sans filtre, tout événement 'new' devrait passer")
    }
}
