package api

import (
	"crypto/hmac"
	"crypto/rand"
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"net/http"
	"strconv"
	"strings"
	"sync"
	"time"
)

// Signer gère la génération et la validation de presigned URLs.
// Les clés tournent automatiquement ; les N dernières restent valides
// pour éviter les race conditions entre deux rotations.
type Signer struct {
	mu       sync.RWMutex
	keys     []signingKey
	baseURL  string
	ttl      time.Duration
	rotation time.Duration
	maxKeys  int
	stopCh   chan struct{}
	now      func() time.Time // pour les tests
}

type signingKey struct {
	secret    []byte
	createdAt time.Time
}

// NewSigner crée un Signer avec rotation automatique des clés.
// baseURL est l'URL de base du proxy (ex: "http://localhost:5555").
// ttl est la durée de validité d'une presigned URL.
// rotation est l'intervalle de rotation des clés.
// maxKeys est le nombre de clés rétro-actives conservées.
func NewSigner(baseURL string, ttl, rotation time.Duration, maxKeys int) *Signer {
	if maxKeys < 1 {
		maxKeys = 1
	}
	s := &Signer{
		baseURL:  strings.TrimRight(baseURL, "/"),
		ttl:      ttl,
		rotation: rotation,
		maxKeys:  maxKeys,
		stopCh:   make(chan struct{}),
		now:      time.Now,
	}
	s.rotate()
	go s.rotationLoop()
	return s
}

func (s *Signer) rotate() {
	secret := make([]byte, 32)
	if _, err := rand.Read(secret); err != nil {
		panic("crypto/rand failed: " + err.Error())
	}
	s.mu.Lock()
	defer s.mu.Unlock()
	s.keys = append([]signingKey{{secret: secret, createdAt: s.now()}}, s.keys...)
	if len(s.keys) > s.maxKeys {
		s.keys = s.keys[:s.maxKeys]
	}
}

func (s *Signer) rotationLoop() {
	ticker := time.NewTicker(s.rotation)
	defer ticker.Stop()
	for {
		select {
		case <-ticker.C:
			s.rotate()
		case <-s.stopCh:
			return
		}
	}
}

// Stop arrête la goroutine de rotation.
func (s *Signer) Stop() {
	close(s.stopCh)
}

// SetTimeFunc remplace la fonction de temps (pour les tests).
func (s *Signer) SetTimeFunc(fn func() time.Time) {
	s.now = fn
}

// SignURL génère une presigned URL complète pour un path donné.
// Ex: "http://localhost:5555/api/events/abc/clip.mp4?exp=1710000000&sig=deadbeef..."
func (s *Signer) SignURL(path string) string {
	exp := s.now().Add(s.ttl).Unix()

	s.mu.RLock()
	key := s.keys[0].secret
	s.mu.RUnlock()

	sig := computeHMAC(key, path, exp)
	return fmt.Sprintf("%s%s?exp=%d&sig=%s", s.baseURL, path, exp, sig)
}

// Verify valide la signature et l'expiration d'une requête presignée.
func (s *Signer) Verify(r *http.Request) bool {
	expStr := r.URL.Query().Get("exp")
	sig := r.URL.Query().Get("sig")
	if expStr == "" || sig == "" {
		return false
	}

	exp, err := strconv.ParseInt(expStr, 10, 64)
	if err != nil {
		return false
	}

	if s.now().Unix() > exp {
		return false
	}

	path := r.URL.Path

	s.mu.RLock()
	defer s.mu.RUnlock()

	for _, k := range s.keys {
		expected := computeHMAC(k.secret, path, exp)
		if hmac.Equal([]byte(sig), []byte(expected)) {
			return true
		}
	}
	return false
}

func computeHMAC(key []byte, path string, exp int64) string {
	mac := hmac.New(sha256.New, key)
	// Payload signé : path + expiration, séparés par un newline
	_, _ = fmt.Fprintf(mac, "%s\n%d", path, exp)
	return hex.EncodeToString(mac.Sum(nil))
}
