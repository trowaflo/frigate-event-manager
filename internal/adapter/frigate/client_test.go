package frigate_test

import (
	"io"
	"log/slog"
	"net/http"
	"net/http/httptest"
	"sync/atomic"
	"testing"

	"frigate-event-manager/internal/adapter/frigate"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func newTestLogger() *slog.Logger {
	return slog.New(slog.NewTextHandler(io.Discard, nil))
}

func TestClient_Get_AuthenticatesAndProxies(t *testing.T) {
	var loginCalls atomic.Int32

	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch r.URL.Path {
		case "/api/login":
			loginCalls.Add(1)
			http.SetCookie(w, &http.Cookie{Name: "frigate_token", Value: "test-jwt-token"})
			w.WriteHeader(http.StatusOK)
		case "/api/review":
			auth := r.Header.Get("Authorization")
			if auth != "Bearer test-jwt-token" {
				w.WriteHeader(http.StatusUnauthorized)
				return
			}
			w.Header().Set("Content-Type", "application/json")
			_, _ = w.Write([]byte(`[{"id":"review123"}]`))
		default:
			w.WriteHeader(http.StatusNotFound)
		}
	}))
	defer srv.Close()

	client := frigate.NewClient(srv.URL, "admin", "pass", newTestLogger())

	resp, err := client.Get("/api/review")
	require.NoError(t, err)
	defer func() { _ = resp.Body.Close() }()

	assert.Equal(t, http.StatusOK, resp.StatusCode)

	body, _ := io.ReadAll(resp.Body)
	assert.Contains(t, string(body), "review123")
	assert.Equal(t, int32(1), loginCalls.Load(), "should login exactly once")
}

func TestClient_Get_RetriesOnExpiredToken(t *testing.T) {
	var loginCalls atomic.Int32
	var getCalls atomic.Int32

	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch r.URL.Path {
		case "/api/login":
			count := loginCalls.Add(1)
			token := "token-v1"
			if count >= 2 {
				token = "token-v2"
			}
			http.SetCookie(w, &http.Cookie{Name: "frigate_token", Value: token})
			w.WriteHeader(http.StatusOK)
		case "/api/events":
			count := getCalls.Add(1)
			auth := r.Header.Get("Authorization")
			// Premier appel : token expiré
			if count == 1 && auth == "Bearer token-v1" {
				w.WriteHeader(http.StatusUnauthorized)
				return
			}
			if auth == "Bearer token-v2" {
				w.Header().Set("Content-Type", "application/json")
				_, _ = w.Write([]byte(`[{"id":"event456"}]`))
				return
			}
			w.WriteHeader(http.StatusUnauthorized)
		default:
			w.WriteHeader(http.StatusNotFound)
		}
	}))
	defer srv.Close()

	client := frigate.NewClient(srv.URL, "admin", "pass", newTestLogger())

	resp, err := client.Get("/api/events")
	require.NoError(t, err)
	defer func() { _ = resp.Body.Close() }()

	assert.Equal(t, http.StatusOK, resp.StatusCode)
	assert.Equal(t, int32(2), loginCalls.Load(), "should have logged in twice (initial + retry)")
}

func TestClient_Get_LoginFailure(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusUnauthorized)
		_, _ = w.Write([]byte(`{"message":"Login failed"}`))
	}))
	defer srv.Close()

	client := frigate.NewClient(srv.URL, "bad", "creds", newTestLogger())

	_, err := client.Get("/api/review")
	assert.Error(t, err)
	assert.Contains(t, err.Error(), "login Frigate échoué")
}

func TestClient_BaseURL(t *testing.T) {
	client := frigate.NewClient("http://frigate:5000/", "u", "p", newTestLogger())
	assert.Equal(t, "http://frigate:5000", client.BaseURL(), "trailing slash should be trimmed")
}
