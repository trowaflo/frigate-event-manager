package supervisor

// Tests white-box du package supervisor.
// Ils ont accès aux symboles non-exportés comme fetchIngressPath et fetchExternalURL.

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

// TestFetchIngressPath_Success valide le parsing JSON et le trim du slash final.
func TestFetchIngressPath_Success(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		resp := addonInfoResponse{}
		resp.Data.IngressURL = "/api/hassio_ingress/TOKEN/"
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(resp)
	}))
	defer srv.Close()

	// fetchIngressPath utilise supervisorURL (constante). On ne peut pas la surcharger.
	// On appelle fetchIngressPath avec un client qui redirige vers srv.URL via un transport custom.
	// Méthode : utiliser un RoundTripper qui réécrit l'URL.
	client := &http.Client{
		Transport: rewriteURLTransport(srv.URL),
	}

	path, err := fetchIngressPath(client, "test-token")
	require.NoError(t, err)
	// Le slash final est tronqué par strings.TrimRight
	assert.Equal(t, "/api/hassio_ingress/TOKEN", path)
}

// TestFetchIngressPath_StatusNonOK retourne une chaîne vide sans erreur.
func TestFetchIngressPath_StatusNonOK(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusUnauthorized)
	}))
	defer srv.Close()

	client := &http.Client{Transport: rewriteURLTransport(srv.URL)}
	path, err := fetchIngressPath(client, "bad-token")
	require.NoError(t, err)
	assert.Empty(t, path, "status non-200 devrait retourner une chaîne vide")
}

// TestFetchIngressPath_JSONCorrompu retourne une erreur.
func TestFetchIngressPath_JSONCorrompu(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		_, _ = w.Write([]byte("not json"))
	}))
	defer srv.Close()

	client := &http.Client{Transport: rewriteURLTransport(srv.URL)}
	_, err := fetchIngressPath(client, "token")
	assert.Error(t, err, "JSON corrompu doit retourner une erreur")
}

// TestFetchExternalURL_Success valide le retour de l'URL externe.
func TestFetchExternalURL_Success(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		resp := coreConfigResponse{
			ExternalURL: "https://ha.example.com",
			InternalURL: "http://homeassistant.local:8123",
		}
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(resp)
	}))
	defer srv.Close()

	client := &http.Client{Transport: rewriteURLTransport(srv.URL)}
	url, err := fetchExternalURL(client, "test-token")
	require.NoError(t, err)
	assert.Equal(t, "https://ha.example.com", url)
}

// TestFetchExternalURL_FallbackInternal valide le fallback sur internal_url.
func TestFetchExternalURL_FallbackInternal(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		resp := coreConfigResponse{
			ExternalURL: "",
			InternalURL: "http://homeassistant.local:8123",
		}
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(resp)
	}))
	defer srv.Close()

	client := &http.Client{Transport: rewriteURLTransport(srv.URL)}
	url, err := fetchExternalURL(client, "test-token")
	require.NoError(t, err)
	assert.Equal(t, "http://homeassistant.local:8123", url)
}

// TestFetchExternalURL_StatusNonOK retourne une chaîne vide sans erreur.
func TestFetchExternalURL_StatusNonOK(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusForbidden)
	}))
	defer srv.Close()

	client := &http.Client{Transport: rewriteURLTransport(srv.URL)}
	url, err := fetchExternalURL(client, "bad-token")
	require.NoError(t, err)
	assert.Empty(t, url, "status non-200 devrait retourner une chaîne vide")
}

// TestFetchExternalURL_JSONCorrompu retourne une erreur.
func TestFetchExternalURL_JSONCorrompu(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		_, _ = w.Write([]byte("not json"))
	}))
	defer srv.Close()

	client := &http.Client{Transport: rewriteURLTransport(srv.URL)}
	_, err := fetchExternalURL(client, "token")
	assert.Error(t, err, "JSON corrompu doit retourner une erreur")
}

// rewriteURLTransport retourne un RoundTripper qui redirige toutes les requêtes
// vers baseURL, quel que soit l'hôte d'origine (supervisorURL = "http://supervisor").
func rewriteURLTransport(baseURL string) http.RoundTripper {
	return &urlRewriter{base: baseURL, inner: http.DefaultTransport}
}

type urlRewriter struct {
	base  string
	inner http.RoundTripper
}

func (r *urlRewriter) RoundTrip(req *http.Request) (*http.Response, error) {
	// Copier la requête pour ne pas la modifier directement
	clone := req.Clone(req.Context())
	// Remplacer l'hôte par le serveur de test, conserver le path
	clone.URL.Scheme = "http"
	clone.URL.Host = r.base[len("http://"):]
	clone.Host = clone.URL.Host
	return r.inner.RoundTrip(clone)
}
