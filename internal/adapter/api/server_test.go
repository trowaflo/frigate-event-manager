package api_test

import (
	"io"
	"log/slog"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"frigate-event-manager/internal/adapter/api"
	"frigate-event-manager/internal/adapter/frigate"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func newTestLogger() *slog.Logger {
	return slog.New(slog.NewTextHandler(io.Discard, nil))
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
	// Strip the base URL to get the relative path+query for httptest
	return url[len("http://localhost:5555"):]
}

func TestServer_ProxyEvents_Clip(t *testing.T) {
	frig := fakeFrigate()
	defer frig.Close()
	signer := newTestSigner()
	defer signer.Stop()

	client := frigate.NewClient(frig.URL, "u", "p", newTestLogger())
	srv := api.NewServer(client, signer, newTestLogger())

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

	client := frigate.NewClient(frig.URL, "u", "p", newTestLogger())
	srv := api.NewServer(client, signer, newTestLogger())

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

	client := frigate.NewClient(frig.URL, "u", "p", newTestLogger())
	srv := api.NewServer(client, signer, newTestLogger())

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

	client := frigate.NewClient(frig.URL, "u", "p", newTestLogger())
	srv := api.NewServer(client, signer, newTestLogger())

	req := httptest.NewRequest(http.MethodGet, presign(signer, "/api/review/rev123/preview"), nil)
	w := httptest.NewRecorder()
	srv.Handler().ServeHTTP(w, req)

	assert.Equal(t, http.StatusOK, w.Code)
	assert.Contains(t, w.Body.String(), "/api/review/rev123/preview")
}

func TestServer_Health(t *testing.T) {
	frig := fakeFrigate()
	defer frig.Close()
	signer := newTestSigner()
	defer signer.Stop()

	client := frigate.NewClient(frig.URL, "u", "p", newTestLogger())
	srv := api.NewServer(client, signer, newTestLogger())

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

	client := frigate.NewClient(frig.URL, "u", "p", newTestLogger())
	srv := api.NewServer(client, signer, newTestLogger())

	// Requête sans presign
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

	client := frigate.NewClient(frig.URL, "u", "p", newTestLogger())
	srv := api.NewServer(client, signer, newTestLogger())

	url := presign(signer, "/api/events/abc/clip.mp4")

	// Avancer le temps au-delà du TTL
	signer.SetTimeFunc(func() time.Time { return frozenTime.Add(2 * time.Minute) })

	req := httptest.NewRequest(http.MethodGet, url, nil)
	w := httptest.NewRecorder()
	srv.Handler().ServeHTTP(w, req)

	assert.Equal(t, http.StatusUnauthorized, w.Code)
}
