package eventstore

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
)

// persistedData est la structure sérialisée dans events.json.
type persistedData struct {
	Events []EventRecord `json:"events"`
}

// EnablePersistence active la sauvegarde automatique sur disque.
// Chaque appel à Add() déclenchera une écriture atomique dans path.
func (s *Store) EnablePersistence(path string) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.persistPath = path
}

// Load charge les événements depuis le fichier de persistence.
// Si le fichier n'existe pas, le store reste vide (premier démarrage).
// Les événements chargés respectent la capacité max du ring buffer :
// si le fichier contient plus d'events que la capacité, seuls les plus récents sont gardés.
func (s *Store) Load(path string) error {
	s.mu.Lock()
	defer s.mu.Unlock()

	data, err := os.ReadFile(path)
	if err != nil {
		if os.IsNotExist(err) {
			return nil // premier démarrage
		}
		return fmt.Errorf("impossible de lire %s: %w", path, err)
	}

	var persisted persistedData
	if err := json.Unmarshal(data, &persisted); err != nil {
		return fmt.Errorf("impossible de parser %s: %w", path, err)
	}

	events := persisted.Events
	// Respecter la capacité : garder uniquement les plus récents
	if len(events) > s.capacity {
		events = events[len(events)-s.capacity:]
	}

	s.records = events
	return nil
}

// persistLocked écrit les événements sur disque. Appelé avec mu verrouillé.
func (s *Store) persistLocked() error {
	if s.persistPath == "" {
		return nil
	}

	persisted := persistedData{Events: s.records}
	data, err := json.MarshalIndent(persisted, "", "  ")
	if err != nil {
		return fmt.Errorf("impossible de sérialiser les événements: %w", err)
	}

	// Écriture atomique : tmp + rename
	dir := filepath.Dir(s.persistPath)
	tmp, err := os.CreateTemp(dir, "events-*.json.tmp")
	if err != nil {
		return fmt.Errorf("impossible de créer le fichier temporaire: %w", err)
	}

	if _, err := tmp.Write(data); err != nil {
		_ = tmp.Close()
		_ = os.Remove(tmp.Name())
		return fmt.Errorf("impossible d'écrire les événements: %w", err)
	}
	if err := tmp.Close(); err != nil {
		_ = os.Remove(tmp.Name())
		return fmt.Errorf("impossible de fermer le fichier temporaire: %w", err)
	}

	if err := os.Rename(tmp.Name(), s.persistPath); err != nil {
		_ = os.Remove(tmp.Name())
		return fmt.Errorf("impossible de renommer le fichier d'événements: %w", err)
	}
	// Garantir les permissions explicitement (indépendamment de l'umask du processus)
	if err := os.Chmod(s.persistPath, 0600); err != nil {
		return fmt.Errorf("impossible de définir les permissions du fichier d'événements: %w", err)
	}
	return nil
}
