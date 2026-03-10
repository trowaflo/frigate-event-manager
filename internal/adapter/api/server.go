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
// En dev, il est accessible sans auth.
// En prod (addon HA), il sera derrière l'ingress HA.
type Server struct {
	client *frigate.Client
	logger *slog.Logger
	mux    *http.ServeMux
}

// NewServer crée le serveur API avec le proxy Frigate.
func NewServer(client *frigate.Client, logger *slog.Logger) *Server {
	s := &Server{
		client: client,
		logger: logger,
		mux:    http.NewServeMux(),
	}
	s.routes()
	return s
}

func (s *Server) routes() {
	// Proxy media Frigate
	s.mux.HandleFunc("/api/events/", s.proxyFrigate)
	s.mux.HandleFunc("/api/review/", s.proxyFrigate)
	s.mux.HandleFunc("/api/review", s.proxyFrigate)

	// Health check
	s.mux.HandleFunc("/health", s.health)
}

// Handler retourne le http.Handler du serveur.
func (s *Server) Handler() http.Handler {
	return s.mux
}

// proxyFrigate transmet la requête à Frigate avec authentification
// et renvoie la réponse telle quelle au client.
func (s *Server) proxyFrigate(w http.ResponseWriter, r *http.Request) {
	// Construire le path Frigate (on garde le path tel quel)
	frigatePath := r.URL.Path
	if r.URL.RawQuery != "" {
		frigatePath += "?" + r.URL.RawQuery
	}

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

	// CORS pour le dev
	w.Header().Set("Access-Control-Allow-Origin", "*")

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

	// Log des routes enregistrées
	routes := []string{
		"GET /api/events/{id}/clip.mp4",
		"GET /api/events/{id}/snapshot.jpg",
		"GET /api/events/{id}/thumbnail.jpg",
		"GET /api/review/{id}/preview",
		"GET /api/review?limit=N",
		"GET /health",
	}
	s.logger.Info("routes disponibles", "routes", strings.Join(routes, ", "))

	return http.ListenAndServe(addr, s.mux)
}
