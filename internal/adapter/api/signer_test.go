package api

import (
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func newTestSigner(ttl time.Duration) *Signer {
	s := &Signer{
		baseURL:  "http://localhost:5555",
		ttl:      ttl,
		rotation: time.Hour,
		maxKeys:  3,
		stopCh:   make(chan struct{}),
		now:      time.Now,
	}
	s.rotate()
	return s
}

func TestSigner_SignURL_Format(t *testing.T) {
	s := newTestSigner(time.Hour)
	defer s.Stop()

	url := s.SignURL("/api/events/abc/clip.mp4")

	assert.Contains(t, url, "http://localhost:5555/api/events/abc/clip.mp4?exp=")
	assert.Contains(t, url, "&sig=")
}

func TestSigner_Verify_ValidSignature(t *testing.T) {
	s := newTestSigner(time.Hour)
	defer s.Stop()

	url := s.SignURL("/api/events/abc/clip.mp4")

	req := httptest.NewRequest(http.MethodGet, url, nil)
	assert.True(t, s.Verify(req), "valid presigned URL should pass verification")
}

func TestSigner_Verify_ExpiredURL(t *testing.T) {
	frozenTime := time.Now()
	s := newTestSigner(time.Minute)
	s.now = func() time.Time { return frozenTime }
	defer s.Stop()

	url := s.SignURL("/api/events/abc/clip.mp4")

	// Avancer le temps au-delà du TTL
	s.now = func() time.Time { return frozenTime.Add(2 * time.Minute) }

	req := httptest.NewRequest(http.MethodGet, url, nil)
	assert.False(t, s.Verify(req), "expired URL should fail verification")
}

func TestSigner_Verify_TamperedSignature(t *testing.T) {
	s := newTestSigner(time.Hour)
	defer s.Stop()

	url := s.SignURL("/api/events/abc/clip.mp4")
	// Altérer la signature
	url = url[:len(url)-4] + "dead"

	req := httptest.NewRequest(http.MethodGet, url, nil)
	assert.False(t, s.Verify(req), "tampered signature should fail")
}

func TestSigner_Verify_TamperedPath(t *testing.T) {
	s := newTestSigner(time.Hour)
	defer s.Stop()

	url := s.SignURL("/api/events/abc/clip.mp4")

	// Changer le path mais garder la même signature
	tampered := url
	tampered = "/api/events/OTHER/clip.mp4" + url[len("/api/events/abc/clip.mp4"):]

	req := httptest.NewRequest(http.MethodGet, "http://localhost:5555"+tampered, nil)
	assert.False(t, s.Verify(req), "tampered path should fail")
}

func TestSigner_Verify_MissingParams(t *testing.T) {
	s := newTestSigner(time.Hour)
	defer s.Stop()

	tests := []struct {
		name string
		url  string
	}{
		{"no params", "/api/events/abc/clip.mp4"},
		{"no sig", "/api/events/abc/clip.mp4?exp=9999999999"},
		{"no exp", "/api/events/abc/clip.mp4?sig=deadbeef"},
		{"invalid exp", "/api/events/abc/clip.mp4?exp=notanumber&sig=deadbeef"},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			req := httptest.NewRequest(http.MethodGet, tt.url, nil)
			assert.False(t, s.Verify(req))
		})
	}
}

func TestSigner_KeyRotation_RetroCompatibility(t *testing.T) {
	frozenTime := time.Now()
	s := &Signer{
		baseURL:  "http://localhost:5555",
		ttl:      time.Hour,
		rotation: time.Minute,
		maxKeys:  3,
		stopCh:   make(chan struct{}),
		now:      func() time.Time { return frozenTime },
	}
	s.rotate() // key 1
	defer s.Stop()

	// Signer avec la clé 1
	url := s.SignURL("/api/events/abc/snapshot.jpg")

	// Rotation : nouvelle clé 2
	s.rotate()
	// Rotation : nouvelle clé 3
	s.rotate()

	// L'URL signée avec la clé 1 doit encore être valide (3 clés rétro-actives)
	req := httptest.NewRequest(http.MethodGet, url, nil)
	assert.True(t, s.Verify(req), "URL signed with key 1 should still be valid with 3 retroactive keys")

	// 4e rotation : la clé 1 est éjectée
	s.rotate()

	req = httptest.NewRequest(http.MethodGet, url, nil)
	assert.False(t, s.Verify(req), "URL signed with key 1 should fail after 4th rotation (maxKeys=3)")
}

func TestSigner_DifferentPaths_DifferentSignatures(t *testing.T) {
	s := newTestSigner(time.Hour)
	defer s.Stop()

	url1 := s.SignURL("/api/events/abc/clip.mp4")
	url2 := s.SignURL("/api/events/xyz/clip.mp4")

	req1 := httptest.NewRequest(http.MethodGet, url1, nil)
	req2 := httptest.NewRequest(http.MethodGet, url2, nil)

	sig1 := req1.URL.Query().Get("sig")
	sig2 := req2.URL.Query().Get("sig")

	require.NotEqual(t, sig1, sig2, "different paths must produce different signatures")
}
