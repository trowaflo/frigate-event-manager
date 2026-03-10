package api

import (
	"fmt"
	"io"
	"log/slog"
	"net/http"
	"strings"

	"frigate-event-manager/internal/adapter/frigate"
)

// Server expose un serveur HTTP qui proxy les requêtes media vers Frigate.
// Toutes les routes /api/* sont protégées par presigned URL.
type Server struct {
	client *frigate.Client
	signer *Signer
	logger *slog.Logger
	mux    *http.ServeMux
}

// NewServer crée le serveur API avec le proxy Frigate et la validation presigned URL.
func NewServer(client *frigate.Client, signer *Signer, logger *slog.Logger) *Server {
	s := &Server{
		client: client,
		signer: signer,
		logger: logger,
		mux:    http.NewServeMux(),
	}
	s.routes()
	return s
}

func (s *Server) routes() {
	// Proxy media Frigate (protégé par presigned URL)
	s.mux.HandleFunc("/api/events/", s.requirePresign(s.proxyFrigate))
	s.mux.HandleFunc("/api/review/", s.requirePresign(s.proxyFrigate))
	s.mux.HandleFunc("/api/review", s.requirePresign(s.proxyFrigate))

	// Health check (pas de presign)
	s.mux.HandleFunc("/health", s.health)
}

// requirePresign est un middleware qui valide la presigned URL.
func (s *Server) requirePresign(next http.HandlerFunc) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		if !s.signer.Verify(r) {
			s.logger.Warn("presigned URL invalide ou expirée",
				"path", r.URL.Path,
				"remote", r.RemoteAddr,
			)
			http.Error(w, "unauthorized", http.StatusUnauthorized)
			return
		}
		next(w, r)
	}
}

// Handler retourne le http.Handler du serveur.
func (s *Server) Handler() http.Handler {
	return s.mux
}

// proxyFrigate transmet la requête à Frigate avec authentification
// et renvoie la réponse telle quelle au client.
func (s *Server) proxyFrigate(w http.ResponseWriter, r *http.Request) {
	// Ne pas forwarder les query params de presign vers Frigate
	frigatePath := r.URL.Path

	s.logger.Debug("proxy vers Frigate", "method", r.Method, "path", frigatePath)

	resp, err := s.client.Get(frigatePath)
	if err != nil {
		s.logger.Error("erreur proxy Frigate", "path", frigatePath, "error", err)
		http.Error(w, "erreur de communication avec Frigate", http.StatusBadGateway)
		return
	}
	defer func() { _ = resp.Body.Close() }()

	// Copier les headers de réponse pertinents
	for _, h := range []string{"Content-Type", "Content-Length", "Content-Disposition", "Cache-Control"} {
		if v := resp.Header.Get(h); v != "" {
			w.Header().Set(h, v)
		}
	}

	w.WriteHeader(resp.StatusCode)
	if _, err := io.Copy(w, resp.Body); err != nil {
		s.logger.Error("erreur copie réponse", "path", frigatePath, "error", err)
	}
}

func (s *Server) health(w http.ResponseWriter, _ *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	_, _ = fmt.Fprint(w, `{"status":"ok"}`)
}

// ListenAndServe démarre le serveur HTTP.
func (s *Server) ListenAndServe(addr string) error {
	s.logger.Info("serveur API démarré", "addr", addr)

	routes := []string{
		"GET /api/events/{id}/clip.mp4?exp=X&sig=Y",
		"GET /api/events/{id}/snapshot.jpg?exp=X&sig=Y",
		"GET /api/events/{id}/thumbnail.jpg?exp=X&sig=Y",
		"GET /api/review/{id}/preview?exp=X&sig=Y",
		"GET /health",
	}
	s.logger.Info("routes disponibles", "routes", strings.Join(routes, ", "))

	return http.ListenAndServe(addr, s.mux)
}
