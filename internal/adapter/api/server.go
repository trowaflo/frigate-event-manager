package api

import (
	"embed"
	"encoding/json"
	"fmt"
	"io"
	"log/slog"
	"net/http"
	"strings"

	"frigate-event-manager/internal/adapter/config"
	"frigate-event-manager/internal/adapter/frigate"
	"frigate-event-manager/internal/core/eventstore"
	"frigate-event-manager/internal/core/registry"
)

//go:embed web/index.html
var webFS embed.FS

// Server expose un serveur HTTP pour la Web UI, l'API management,
// et le proxy media vers Frigate (avec presigned URLs).
type Server struct {
	client     *frigate.Client    // nil si Frigate non configuré
	signer     *Signer            // nil si Frigate non configuré
	registry   *registry.Registry
	eventStore *eventstore.Store
	config     *config.Config
	logger     *slog.Logger
	mux        *http.ServeMux
}

// NewServer crée le serveur API.
// client et signer peuvent être nil (pas de Frigate configuré).
func NewServer(client *frigate.Client, signer *Signer, reg *registry.Registry, store *eventstore.Store, cfg *config.Config, logger *slog.Logger) *Server {
	s := &Server{
		client:     client,
		signer:     signer,
		registry:   reg,
		eventStore: store,
		config:     cfg,
		logger:     logger,
		mux:        http.NewServeMux(),
	}
	s.routes()
	return s
}

func (s *Server) routes() {
	// Proxy media Frigate (protégé par presigned URL, uniquement si Frigate configuré)
	if s.client != nil && s.signer != nil {
		s.mux.HandleFunc("/api/events/", s.requirePresign(s.proxyFrigate))
		s.mux.HandleFunc("/api/review/", s.requirePresign(s.proxyFrigate))
		s.mux.HandleFunc("/api/review", s.requirePresign(s.proxyFrigate))
	}

	// API Management (protégé par ingress, pas de presign)
	s.mux.HandleFunc("GET /api/cameras", s.listCameras)
	s.mux.HandleFunc("PATCH /api/cameras/{name}", s.toggleCamera)
	s.mux.HandleFunc("GET /api/config", s.getConfig)
	s.mux.HandleFunc("GET /api/stats", s.getStats)
	s.mux.HandleFunc("GET /api/events-list", s.listEvents)

	// Health check
	s.mux.HandleFunc("/health", s.health)

	// SPA : servir index.html pour toutes les routes non-API
	s.mux.HandleFunc("/", s.serveIndex)
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
	frigatePath := r.URL.Path

	s.logger.Debug("proxy vers Frigate", "method", r.Method, "path", frigatePath)

	resp, err := s.client.Get(frigatePath)
	if err != nil {
		s.logger.Error("erreur proxy Frigate", "path", frigatePath, "error", err)
		http.Error(w, "erreur de communication avec Frigate", http.StatusBadGateway)
		return
	}
	defer func() { _ = resp.Body.Close() }()

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

// --- API Management ---

func (s *Server) listCameras(w http.ResponseWriter, _ *http.Request) {
	s.writeJSON(w, s.registry.Cameras())
}

func (s *Server) toggleCamera(w http.ResponseWriter, r *http.Request) {
	name := r.PathValue("name")
	if name == "" {
		http.Error(w, `{"error":"nom de caméra manquant"}`, http.StatusBadRequest)
		return
	}

	var body struct {
		Enabled bool `json:"enabled"`
	}
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
		http.Error(w, `{"error":"JSON invalide"}`, http.StatusBadRequest)
		return
	}

	if err := s.registry.SetEnabled(name, body.Enabled); err != nil {
		http.Error(w, fmt.Sprintf(`{"error":%q}`, err.Error()), http.StatusNotFound)
		return
	}

	cam, _ := s.registry.Camera(name)
	s.writeJSON(w, cam)
}

func (s *Server) getConfig(w http.ResponseWriter, _ *http.Request) {
	s.writeJSON(w, s.config.Sanitized())
}

func (s *Server) getStats(w http.ResponseWriter, _ *http.Request) {
	storeStats := s.eventStore.Stats()
	cameras := s.registry.Cameras()

	activeCameras := 0
	for _, c := range cameras {
		if c.Enabled {
			activeCameras++
		}
	}

	s.writeJSON(w, map[string]any{
		"events_24h":     storeStats.Events24h,
		"alerts_24h":     storeStats.Alerts24h,
		"detections_24h": storeStats.Detections24h,
		"total_cameras":  len(cameras),
		"active_cameras": activeCameras,
	})
}

func (s *Server) listEvents(w http.ResponseWriter, r *http.Request) {
	severity := r.URL.Query().Get("severity")
	limit := 50 // défaut
	if l := r.URL.Query().Get("limit"); l != "" {
		fmt.Sscanf(l, "%d", &limit)
	}
	s.writeJSON(w, s.eventStore.List(limit, severity))
}

// --- SPA ---

func (s *Server) serveIndex(w http.ResponseWriter, r *http.Request) {
	// Ne servir le SPA que pour les requêtes navigateur (pas les 404 API)
	if strings.HasPrefix(r.URL.Path, "/api/") {
		http.NotFound(w, r)
		return
	}

	data, err := webFS.ReadFile("web/index.html")
	if err != nil {
		http.Error(w, "index.html non trouvé", http.StatusInternalServerError)
		return
	}

	// Injecter le base href pour la compatibilité ingress HA
	ingressPath := r.Header.Get("X-Ingress-Path")
	if ingressPath == "" {
		ingressPath = "/"
	}
	if !strings.HasSuffix(ingressPath, "/") {
		ingressPath += "/"
	}

	html := strings.Replace(
		string(data),
		`<base href="/">`,
		fmt.Sprintf(`<base href="%s">`, ingressPath),
		1,
	)

	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	_, _ = w.Write([]byte(html))
}

// --- Helpers ---

func (s *Server) writeJSON(w http.ResponseWriter, v any) {
	w.Header().Set("Content-Type", "application/json")
	if err := json.NewEncoder(w).Encode(v); err != nil {
		s.logger.Error("erreur sérialisation JSON", "error", err)
	}
}

// ListenAndServe démarre le serveur HTTP.
func (s *Server) ListenAndServe(addr string) error {
	s.logger.Info("serveur API démarré", "addr", addr)
	return http.ListenAndServe(addr, s.mux)
}
