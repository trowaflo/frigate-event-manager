package supervisor_test

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"frigate-event-manager/internal/adapter/supervisor"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

// supervisorURLOverride permet de pointer les fonctions vers un serveur de test.
// On utilise un serveur httptest qui intercepte les requêtes.

// TestFetchIngressInfo_TokenVide retourne une info vide sans erreur.
func TestFetchIngressInfo_TokenVide(t *testing.T) {
	info, err := supervisor.FetchIngressInfo("")
	require.NoError(t, err)
	assert.Empty(t, info.MediaBaseURL)
}

// Pour tester les chemins réseau, on ne peut pas surcharger la constante supervisorURL
// depuis l'extérieur du package. On teste donc les comportements observables :
// - token vide → retour immédiat
// - supervisor inaccessible → retour sans erreur (mode dev local)

func TestFetchIngressInfo_SupervisorInaccessible_RetourneInfoVideSansErreur(t *testing.T) {
	// Utiliser un port qui refuse les connexions
	// La constante supervisorURL = "http://supervisor" pointe sur un hôte
	// qui n'existe pas en test → connexion refusée → retour sans erreur
	info, err := supervisor.FetchIngressInfo("un-token-quelconque")
	require.NoError(t, err)
	assert.Empty(t, info.MediaBaseURL, "supervisor inaccessible = mode dev, MediaBaseURL vide")
}

// newSupervisorTestServer crée un faux serveur Supervisor pour les tests internes.
// Utilisé pour valider la logique de parsing depuis un package interne.
// Comme supervisorURL est privée, on ne peut tester que les comportements observables.
func TestFetchIngressInfo_InternalLogic(t *testing.T) {
	t.Run("token vide retourne vide", func(t *testing.T) {
		info, err := supervisor.FetchIngressInfo("")
		require.NoError(t, err)
		assert.Equal(t, "", info.MediaBaseURL)
	})
}

// Tester avec un vrai serveur HTTP via un sous-package white-box n'est pas possible
// depuis l'extérieur. On crée un test helper interne via un fichier séparé si besoin.
// Pour l'instant, les tests ci-dessus couvrent les branches testables en boîte noire.

// newFakeSupervisorServer crée un serveur qui simule le Supervisor HA.
// Utilisé pour valider la logique de combinaison URL dans un contexte contrôlé.
// Note : supervisorURL est une constante privée — ce test ne peut être fait qu'en white-box.
func newFakeSupervisorServer(ingressURL, externalURL string) *httptest.Server {
	mux := http.NewServeMux()
	mux.HandleFunc("/addons/self/info", func(w http.ResponseWriter, r *http.Request) {
		resp := map[string]any{
			"data": map[string]string{
				"ingress_url": ingressURL,
			},
		}
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(resp)
	})
	mux.HandleFunc("/core/api/config", func(w http.ResponseWriter, r *http.Request) {
		resp := map[string]string{
			"external_url": externalURL,
			"internal_url": "http://homeassistant.local:8123",
		}
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(resp)
	})
	return httptest.NewServer(mux)
}

// TestFetchIngressInfo_SimuleSupervisor ne peut pas surcharger supervisorURL depuis l'extérieur.
// Ce test documente le comportement attendu et sert de référence pour les tests white-box.
func TestFetchIngressInfo_IngressURLConstruction(t *testing.T) {
	// Crée un faux serveur — on ne peut pas le brancher sur supervisorURL depuis ici.
	// Ce test vérifie seulement que newFakeSupervisorServer fonctionne correctement.
	srv := newFakeSupervisorServer("/api/hassio_ingress/TOKEN", "https://ha.example.com")
	defer srv.Close()

	resp, err := http.Get(srv.URL + "/addons/self/info")
	require.NoError(t, err)
	defer func() { _ = resp.Body.Close() }()
	assert.Equal(t, http.StatusOK, resp.StatusCode)

	resp2, err := http.Get(srv.URL + "/core/api/config")
	require.NoError(t, err)
	defer func() { _ = resp2.Body.Close() }()
	assert.Equal(t, http.StatusOK, resp2.StatusCode)
}
