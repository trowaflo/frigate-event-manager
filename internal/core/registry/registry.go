package registry

import (
	"encoding/json"
	"fmt"
	"log/slog"
	"os"
	"path/filepath"
	"sync"
	"time"
)

// CameraState représente l'état connu d'une caméra découverte.
type CameraState struct {
	Name            string    `json:"name"`
	Enabled         bool      `json:"enabled"`          // notifications actives
	FirstSeen       time.Time `json:"first_seen"`       // première apparition
	LastEventTime   time.Time `json:"last_event_time"`  // dernier événement reçu
	LastSeverity    string    `json:"last_severity"`     // "alert" ou "detection"
	LastObjects     []string  `json:"last_objects"`      // ["person", "car", ...]
	EventCount24h   int       `json:"event_count_24h"`   // compteur glissant 24h
	eventTimestamps []time.Time                          // interne, pour le compteur 24h
}

// Listener est notifié quand le registry change.
type Listener interface {
	OnCameraUpdated(cam CameraState)
	OnCameraAdded(cam CameraState)
}

// Registry stocke les caméras découvertes et persiste l'état dans un fichier JSON.
type Registry struct {
	mu        sync.RWMutex
	cameras   map[string]*CameraState
	listeners []Listener
	statePath string
	now       func() time.Time // injectable pour les tests
}

// persistedState est la structure sérialisée dans state.json.
type persistedState struct {
	Cameras map[string]*persistedCamera `json:"cameras"`
}

type persistedCamera struct {
	Enabled       bool      `json:"enabled"`
	FirstSeen     time.Time `json:"first_seen"`
	LastEventTime time.Time `json:"last_event_time"`
	LastSeverity  string    `json:"last_severity"`
	LastObjects   []string  `json:"last_objects"`
}

// New crée un registry. statePath est le chemin vers le fichier de persistence (ex: /data/state.json).
func New(statePath string) *Registry {
	return &Registry{
		cameras:   make(map[string]*CameraState),
		statePath: statePath,
		now:       time.Now,
	}
}

// AddListener enregistre un listener notifié à chaque changement.
func (r *Registry) AddListener(l Listener) {
	r.mu.Lock()
	defer r.mu.Unlock()
	r.listeners = append(r.listeners, l)
}

// RecordEvent enregistre un événement pour une caméra.
// Si la caméra est nouvelle, elle est ajoutée et activée par défaut.
// Retourne true si la caméra vient d'être découverte.
func (r *Registry) RecordEvent(camera, severity string, objects []string) bool {
	r.mu.Lock()
	defer r.mu.Unlock()

	now := r.now()
	cam, exists := r.cameras[camera]

	if !exists {
		cam = &CameraState{
			Name:      camera,
			Enabled:   true, // plug & play : activée par défaut
			FirstSeen: now,
		}
		r.cameras[camera] = cam
	}

	cam.LastEventTime = now
	cam.LastSeverity = severity
	cam.LastObjects = objects

	// Compteur glissant 24h
	cam.eventTimestamps = append(cam.eventTimestamps, now)
	cutoff := now.Add(-24 * time.Hour)
	filtered := cam.eventTimestamps[:0]
	for _, ts := range cam.eventTimestamps {
		if ts.After(cutoff) {
			filtered = append(filtered, ts)
		}
	}
	cam.eventTimestamps = filtered
	cam.EventCount24h = len(filtered)

	// Persister après chaque changement
	if err := r.persistLocked(); err != nil {
		slog.Warn("échec de la persistence du registry", "erreur", err)
	}

	// Notifier les listeners
	snapshot := *cam
	if !exists {
		for _, l := range r.listeners {
			l.OnCameraAdded(snapshot)
		}
	} else {
		for _, l := range r.listeners {
			l.OnCameraUpdated(snapshot)
		}
	}

	return !exists
}

// SetEnabled active ou désactive les notifications pour une caméra.
func (r *Registry) SetEnabled(camera string, enabled bool) error {
	r.mu.Lock()
	defer r.mu.Unlock()

	cam, exists := r.cameras[camera]
	if !exists {
		return fmt.Errorf("camera %q inconnue", camera)
	}

	cam.Enabled = enabled
	if err := r.persistLocked(); err != nil {
		slog.Warn("échec de la persistence du registry", "erreur", err)
	}

	snapshot := *cam
	for _, l := range r.listeners {
		l.OnCameraUpdated(snapshot)
	}
	return nil
}

// IsEnabled retourne si les notifications sont actives pour cette caméra.
func (r *Registry) IsEnabled(camera string) bool {
	r.mu.RLock()
	defer r.mu.RUnlock()

	cam, exists := r.cameras[camera]
	if !exists {
		return true // caméra inconnue = activée par défaut
	}
	return cam.Enabled
}

// Cameras retourne un snapshot de toutes les caméras connues.
func (r *Registry) Cameras() []CameraState {
	r.mu.RLock()
	defer r.mu.RUnlock()

	result := make([]CameraState, 0, len(r.cameras))
	for _, cam := range r.cameras {
		result = append(result, *cam)
	}
	return result
}

// Camera retourne l'état d'une caméra. Retourne false si inconnue.
func (r *Registry) Camera(name string) (CameraState, bool) {
	r.mu.RLock()
	defer r.mu.RUnlock()

	cam, exists := r.cameras[name]
	if !exists {
		return CameraState{}, false
	}
	return *cam, true
}

// Load charge l'état depuis le fichier de persistence.
// Si le fichier n'existe pas, le registry reste vide (premier démarrage).
func (r *Registry) Load() error {
	r.mu.Lock()
	defer r.mu.Unlock()

	data, err := os.ReadFile(r.statePath)
	if err != nil {
		if os.IsNotExist(err) {
			return nil // premier démarrage
		}
		return fmt.Errorf("impossible de lire %s: %w", r.statePath, err)
	}

	var state persistedState
	if err := json.Unmarshal(data, &state); err != nil {
		return fmt.Errorf("impossible de parser %s: %w", r.statePath, err)
	}

	for name, pc := range state.Cameras {
		r.cameras[name] = &CameraState{
			Name:          name,
			Enabled:       pc.Enabled,
			FirstSeen:     pc.FirstSeen,
			LastEventTime: pc.LastEventTime,
			LastSeverity:  pc.LastSeverity,
			LastObjects:   pc.LastObjects,
		}
	}
	return nil
}

// persistLocked écrit l'état sur disque. Appelé avec mu verrouillé.
func (r *Registry) persistLocked() error {
	state := persistedState{
		Cameras: make(map[string]*persistedCamera, len(r.cameras)),
	}
	for name, cam := range r.cameras {
		state.Cameras[name] = &persistedCamera{
			Enabled:       cam.Enabled,
			FirstSeen:     cam.FirstSeen,
			LastEventTime: cam.LastEventTime,
			LastSeverity:  cam.LastSeverity,
			LastObjects:   cam.LastObjects,
		}
	}

	data, err := json.MarshalIndent(state, "", "  ")
	if err != nil {
		return fmt.Errorf("impossible de sérialiser l'état: %w", err)
	}

	// Écriture atomique : écrire dans un fichier temporaire puis renommer
	dir := filepath.Dir(r.statePath)
	tmp, err := os.CreateTemp(dir, "state-*.json.tmp")
	if err != nil {
		return fmt.Errorf("impossible de créer le fichier temporaire: %w", err)
	}

	if _, err := tmp.Write(data); err != nil {
		_ = tmp.Close()
		_ = os.Remove(tmp.Name())
		return fmt.Errorf("impossible d'écrire l'état: %w", err)
	}
	if err := tmp.Close(); err != nil {
		_ = os.Remove(tmp.Name())
		return err
	}

	if err := os.Rename(tmp.Name(), r.statePath); err != nil {
		_ = os.Remove(tmp.Name())
		return fmt.Errorf("impossible de renommer le fichier d'état: %w", err)
	}
	return nil
}
