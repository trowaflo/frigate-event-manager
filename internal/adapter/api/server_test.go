package api_test

import (
	"io"
	"log/slog"
	"net/http"
	"net/http/httptest"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"frigate-event-manager/internal/adapter/api"
	"frigate-event-manager/internal/adapter/config"
	"frigate-event-manager/internal/adapter/frigate"
	"frigate-event-manager/internal/core/eventstore"
	"frigate-event-manager/internal/core/registry"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func newTestLogger() *slog.Logger {
	return slog.New(slog.NewTextHandler(io.Discard, nil))
}

func newTestDeps(t *testing.T) (*registry.Registry, *eventstore.Store, *config.Config) {
	t.Helper()
	reg := registry.New(filepath.Join(t.TempDir(), "state.json"))
	store := eventstore.New(100)
	cfg := &config.Config{
		MQTTBrokerURL: "tcp://localhost:1883",
		MQTTTopic:     "frigate/reviews",
		APIPort:       5555,
	}
	return reg, store, cfg
}

// fakeFrigate simule l'API Frigate avec login + endpoints media
func fakeFrigate() *httptest.Server {
	return httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch {
		case r.URL.Path == "/api/login":
			http.SetCookie(w, &http.Cookie{Name: "frigate_token", Value: "jwt"})
			w.WriteHeader(http.StatusOK)

		case r.Header.Get("Authorization") != "Bearer jwt":
			w.WriteHeader(http.StatusUnauthorized)

		default:
			w.Header().Set("Content-Type", "application/octet-stream")
			_, _ = w.Write([]byte("media-content-for-" + r.URL.Path))
		}
	}))
}

func newTestSigner() *api.Signer {
	return api.NewSigner("http://localhost:5555", time.Hour, time.Hour, 3)
}

func presign(signer *api.Signer, path string) string {
	url := signer.SignURL(path)
	return url[len("http://localhost:5555"):]
}

// --- Tests proxy media (existants) ---

func TestServer_ProxyEvents_Clip(t *testing.T) {
	frig := fakeFrigate()
	defer frig.Close()
	signer := newTestSigner()
	defer signer.Stop()
	reg, store, cfg := newTestDeps(t)

	client := frigate.NewClient(frig.URL, "u", "p", newTestLogger())
	srv := api.NewServer(client, signer, reg, store, cfg, newTestLogger())

	req := httptest.NewRequest(http.MethodGet, presign(signer, "/api/events/abc123/clip.mp4"), nil)
	w := httptest.NewRecorder()
	srv.Handler().ServeHTTP(w, req)

	assert.Equal(t, http.StatusOK, w.Code)
	assert.Contains(t, w.Body.String(), "media-content-for-/api/events/abc123/clip.mp4")
}

func TestServer_ProxyEvents_Snapshot(t *testing.T) {
	frig := fakeFrigate()
	defer frig.Close()
	signer := newTestSigner()
	defer signer.Stop()
	reg, store, cfg := newTestDeps(t)

	client := frigate.NewClient(frig.URL, "u", "p", newTestLogger())
	srv := api.NewServer(client, signer, reg, store, cfg, newTestLogger())

	req := httptest.NewRequest(http.MethodGet, presign(signer, "/api/events/abc123/snapshot.jpg"), nil)
	w := httptest.NewRecorder()
	srv.Handler().ServeHTTP(w, req)

	assert.Equal(t, http.StatusOK, w.Code)
	assert.Contains(t, w.Body.String(), "/api/events/abc123/snapshot.jpg")
}

func TestServer_ProxyReview_List(t *testing.T) {
	frig := fakeFrigate()
	defer frig.Close()
	signer := newTestSigner()
	defer signer.Stop()
	reg, store, cfg := newTestDeps(t)

	client := frigate.NewClient(frig.URL, "u", "p", newTestLogger())
	srv := api.NewServer(client, signer, reg, store, cfg, newTestLogger())

	req := httptest.NewRequest(http.MethodGet, presign(signer, "/api/review"), nil)
	w := httptest.NewRecorder()
	srv.Handler().ServeHTTP(w, req)

	assert.Equal(t, http.StatusOK, w.Code)
}

func TestServer_ProxyReview_Preview(t *testing.T) {
	frig := fakeFrigate()
	defer frig.Close()
	signer := newTestSigner()
	defer signer.Stop()
	reg, store, cfg := newTestDeps(t)

	client := frigate.NewClient(frig.URL, "u", "p", newTestLogger())
	srv := api.NewServer(client, signer, reg, store, cfg, newTestLogger())

	req := httptest.NewRequest(http.MethodGet, presign(signer, "/api/review/rev123/preview"), nil)
	w := httptest.NewRecorder()
	srv.Handler().ServeHTTP(w, req)

	assert.Equal(t, http.StatusOK, w.Code)
	assert.Contains(t, w.Body.String(), "/api/review/rev123/preview")
}

func TestServer_Health(t *testing.T) {
	reg, store, cfg := newTestDeps(t)
	srv := api.NewServer(nil, nil, reg, store, cfg, newTestLogger())

	req := httptest.NewRequest(http.MethodGet, "/health", nil)
	w := httptest.NewRecorder()
	srv.Handler().ServeHTTP(w, req)

	assert.Equal(t, http.StatusOK, w.Code)
	body, err := io.ReadAll(w.Body)
	require.NoError(t, err)
	assert.JSONEq(t, `{"status":"ok"}`, string(body))
}

func TestServer_RejectsUnsignedRequest(t *testing.T) {
	frig := fakeFrigate()
	defer frig.Close()
	signer := newTestSigner()
	defer signer.Stop()
	reg, store, cfg := newTestDeps(t)

	client := frigate.NewClient(frig.URL, "u", "p", newTestLogger())
	srv := api.NewServer(client, signer, reg, store, cfg, newTestLogger())

	req := httptest.NewRequest(http.MethodGet, "/api/events/abc/clip.mp4", nil)
	w := httptest.NewRecorder()
	srv.Handler().ServeHTTP(w, req)

	assert.Equal(t, http.StatusUnauthorized, w.Code)
}

func TestServer_RejectsExpiredPresign(t *testing.T) {
	frig := fakeFrigate()
	defer frig.Close()

	frozenTime := time.Now()
	signer := api.NewSigner("http://localhost:5555", time.Minute, time.Hour, 3)
	signer.SetTimeFunc(func() time.Time { return frozenTime })
	defer signer.Stop()
	reg, store, cfg := newTestDeps(t)

	client := frigate.NewClient(frig.URL, "u", "p", newTestLogger())
	srv := api.NewServer(client, signer, reg, store, cfg, newTestLogger())

	url := presign(signer, "/api/events/abc/clip.mp4")
	signer.SetTimeFunc(func() time.Time { return frozenTime.Add(2 * time.Minute) })

	req := httptest.NewRequest(http.MethodGet, url, nil)
	w := httptest.NewRecorder()
	srv.Handler().ServeHTTP(w, req)

	assert.Equal(t, http.StatusUnauthorized, w.Code)
}

// --- Tests API Management ---

func TestServer_ListCameras(t *testing.T) {
	reg, store, cfg := newTestDeps(t)
	reg.RecordEvent("jardin", "alert", []string{"person"})
	reg.RecordEvent("garage", "detection", []string{"car"})

	srv := api.NewServer(nil, nil, reg, store, cfg, newTestLogger())

	req := httptest.NewRequest(http.MethodGet, "/api/cameras", nil)
	w := httptest.NewRecorder()
	srv.Handler().ServeHTTP(w, req)

	assert.Equal(t, http.StatusOK, w.Code)
	assert.Contains(t, w.Body.String(), "jardin")
	assert.Contains(t, w.Body.String(), "garage")
}

func TestServer_ToggleCamera(t *testing.T) {
	reg, store, cfg := newTestDeps(t)
	reg.RecordEvent("jardin", "alert", []string{"person"})

	srv := api.NewServer(nil, nil, reg, store, cfg, newTestLogger())

	req := httptest.NewRequest(http.MethodPatch, "/api/cameras/jardin", strings.NewReader(`{"enabled":false}`))
	w := httptest.NewRecorder()
	srv.Handler().ServeHTTP(w, req)

	assert.Equal(t, http.StatusOK, w.Code)
	assert.False(t, reg.IsEnabled("jardin"))
}

func TestServer_ToggleCamera_Unknown(t *testing.T) {
	reg, store, cfg := newTestDeps(t)
	srv := api.NewServer(nil, nil, reg, store, cfg, newTestLogger())

	req := httptest.NewRequest(http.MethodPatch, "/api/cameras/inconnu", strings.NewReader(`{"enabled":true}`))
	w := httptest.NewRecorder()
	srv.Handler().ServeHTTP(w, req)

	assert.Equal(t, http.StatusNotFound, w.Code)
}

func TestServer_GetConfig(t *testing.T) {
	reg, store, cfg := newTestDeps(t)
	cfg.FrigateURL = "http://frigate:5000"
	cfg.FrigatePassword = "secret"

	srv := api.NewServer(nil, nil, reg, store, cfg, newTestLogger())

	req := httptest.NewRequest(http.MethodGet, "/api/config", nil)
	w := httptest.NewRecorder()
	srv.Handler().ServeHTTP(w, req)

	assert.Equal(t, http.StatusOK, w.Code)
	assert.Contains(t, w.Body.String(), "http://frigate:5000")
	assert.Contains(t, w.Body.String(), "***")
	assert.NotContains(t, w.Body.String(), "secret")
}

func TestServer_GetStats(t *testing.T) {
	reg, store, cfg := newTestDeps(t)
	reg.RecordEvent("jardin", "alert", []string{"person"})
	reg.RecordEvent("garage", "detection", []string{"car"})

	store.Add(eventstore.EventRecord{Severity: "alert", Timestamp: time.Now()})
	store.Add(eventstore.EventRecord{Severity: "detection", Timestamp: time.Now()})

	srv := api.NewServer(nil, nil, reg, store, cfg, newTestLogger())

	req := httptest.NewRequest(http.MethodGet, "/api/stats", nil)
	w := httptest.NewRecorder()
	srv.Handler().ServeHTTP(w, req)

	assert.Equal(t, http.StatusOK, w.Code)
	assert.Contains(t, w.Body.String(), `"events_24h":2`)
	assert.Contains(t, w.Body.String(), `"active_cameras":2`)
}

func TestServer_ListEvents(t *testing.T) {
	reg, store, cfg := newTestDeps(t)
	store.Add(eventstore.EventRecord{ReviewID: "r1", Camera: "jardin", Severity: "alert", Timestamp: time.Now()})
	store.Add(eventstore.EventRecord{ReviewID: "r2", Camera: "garage", Severity: "detection", Timestamp: time.Now()})

	srv := api.NewServer(nil, nil, reg, store, cfg, newTestLogger())

	req := httptest.NewRequest(http.MethodGet, "/api/events-list", nil)
	w := httptest.NewRecorder()
	srv.Handler().ServeHTTP(w, req)

	assert.Equal(t, http.StatusOK, w.Code)
	assert.Contains(t, w.Body.String(), "jardin")
	assert.Contains(t, w.Body.String(), "garage")
}

func TestServer_ListEvents_FilterSeverity(t *testing.T) {
	reg, store, cfg := newTestDeps(t)
	store.Add(eventstore.EventRecord{ReviewID: "r1", Severity: "alert", Timestamp: time.Now()})
	store.Add(eventstore.EventRecord{ReviewID: "r2", Severity: "detection", Timestamp: time.Now()})

	srv := api.NewServer(nil, nil, reg, store, cfg, newTestLogger())

	req := httptest.NewRequest(http.MethodGet, "/api/events-list?severity=alert", nil)
	w := httptest.NewRecorder()
	srv.Handler().ServeHTTP(w, req)

	assert.Equal(t, http.StatusOK, w.Code)
	assert.Contains(t, w.Body.String(), "r1")
	assert.NotContains(t, w.Body.String(), "r2")
}

func TestServer_ServeIndex(t *testing.T) {
	reg, store, cfg := newTestDeps(t)
	srv := api.NewServer(nil, nil, reg, store, cfg, newTestLogger())

	req := httptest.NewRequest(http.MethodGet, "/", nil)
	w := httptest.NewRecorder()
	srv.Handler().ServeHTTP(w, req)

	assert.Equal(t, http.StatusOK, w.Code)
	assert.Contains(t, w.Header().Get("Content-Type"), "text/html")
	assert.Contains(t, w.Body.String(), "FRIGATE EVENT")
}

func TestServer_ServeIndex_IngressBasePath(t *testing.T) {
	reg, store, cfg := newTestDeps(t)
	srv := api.NewServer(nil, nil, reg, store, cfg, newTestLogger())

	req := httptest.NewRequest(http.MethodGet, "/", nil)
	req.Header.Set("X-Ingress-Path", "/api/hassio_ingress/TOKEN123")
	w := httptest.NewRecorder()
	srv.Handler().ServeHTTP(w, req)

	assert.Equal(t, http.StatusOK, w.Code)
	assert.Contains(t, w.Body.String(), `<base href="/api/hassio_ingress/TOKEN123/">`)
}

// --- Test serveur sans Frigate (nil client/signer) ---

func TestServer_NilFrigate_HealthWorks(t *testing.T) {
	reg, store, cfg := newTestDeps(t)
	srv := api.NewServer(nil, nil, reg, store, cfg, newTestLogger())

	req := httptest.NewRequest(http.MethodGet, "/health", nil)
	w := httptest.NewRecorder()
	srv.Handler().ServeHTTP(w, req)

	assert.Equal(t, http.StatusOK, w.Code)
}

func TestServer_NilFrigate_ManagementAPIWorks(t *testing.T) {
	reg, store, cfg := newTestDeps(t)
	srv := api.NewServer(nil, nil, reg, store, cfg, newTestLogger())

	req := httptest.NewRequest(http.MethodGet, "/api/cameras", nil)
	w := httptest.NewRecorder()
	srv.Handler().ServeHTTP(w, req)

	assert.Equal(t, http.StatusOK, w.Code)
}
