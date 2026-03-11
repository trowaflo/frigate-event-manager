package eventstore

import (
	"sync"
	"time"
)

// EventRecord représente un événement enregistré pour la timeline.
type EventRecord struct {
	ReviewID  string    `json:"review_id"`
	Camera    string    `json:"camera"`
	Severity  string    `json:"severity"`
	Objects   []string  `json:"objects"`
	Zones     []string  `json:"zones"`
	Timestamp time.Time `json:"timestamp"`
}

// StatsSnapshot contient les statistiques du dashboard.
type StatsSnapshot struct {
	Events24h    int `json:"events_24h"`
	Alerts24h    int `json:"alerts_24h"`
	Detections24h int `json:"detections_24h"`
}

// Store est un ring buffer en mémoire pour les événements récents.
type Store struct {
	mu       sync.RWMutex
	records  []EventRecord
	capacity int
	now      func() time.Time // injectable pour les tests
}

// New crée un store avec une capacité maximale.
func New(capacity int) *Store {
	return &Store{
		records:  make([]EventRecord, 0, capacity),
		capacity: capacity,
		now:      time.Now,
	}
}

// Add ajoute un événement au store. Si le buffer est plein, le plus ancien est éjecté.
func (s *Store) Add(record EventRecord) {
	s.mu.Lock()
	defer s.mu.Unlock()

	if len(s.records) >= s.capacity {
		// Décaler tout d'un cran (éjecte le plus ancien en position 0)
		copy(s.records, s.records[1:])
		s.records[len(s.records)-1] = record
	} else {
		s.records = append(s.records, record)
	}
}

// List retourne les événements les plus récents.
// severity="" = tous. Résultat trié du plus récent au plus ancien.
func (s *Store) List(limit int, severity string) []EventRecord {
	s.mu.RLock()
	defer s.mu.RUnlock()

	var result []EventRecord

	// Parcourir du plus récent au plus ancien
	for i := len(s.records) - 1; i >= 0; i-- {
		r := s.records[i]
		if severity != "" && r.Severity != severity {
			continue
		}
		result = append(result, r)
		if limit > 0 && len(result) >= limit {
			break
		}
	}
	return result
}

// Stats retourne les statistiques sur les dernières 24h.
func (s *Store) Stats() StatsSnapshot {
	s.mu.RLock()
	defer s.mu.RUnlock()

	cutoff := s.now().Add(-24 * time.Hour)
	var snap StatsSnapshot

	for i := len(s.records) - 1; i >= 0; i-- {
		r := s.records[i]
		if r.Timestamp.Before(cutoff) {
			break // les records sont triés chronologiquement
		}
		snap.Events24h++
		switch r.Severity {
		case "alert":
			snap.Alerts24h++
		case "detection":
			snap.Detections24h++
		}
	}
	return snap
}

// Len retourne le nombre d'événements stockés.
func (s *Store) Len() int {
	s.mu.RLock()
	defer s.mu.RUnlock()
	return len(s.records)
}
