package eventstore

import (
	"fmt"
	"os"
	"path/filepath"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestPersistence_SaveAndLoad(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "events.json")

	// Créer un store, activer la persistence, ajouter des events
	store := New(10)
	store.EnablePersistence(path)

	store.Add(EventRecord{
		ReviewID: "r1", Camera: "jardin", Severity: "alert",
		Objects: []string{"person"}, Timestamp: time.Date(2025, 3, 11, 10, 0, 0, 0, time.UTC),
	})
	store.Add(EventRecord{
		ReviewID: "r2", Camera: "garage", Severity: "detection",
		Objects: []string{"car"}, Timestamp: time.Date(2025, 3, 11, 11, 0, 0, 0, time.UTC),
	})

	// Vérifier que le fichier existe
	_, err := os.Stat(path)
	require.NoError(t, err)

	// Charger dans un nouveau store
	store2 := New(10)
	err = store2.Load(path)
	require.NoError(t, err)

	assert.Equal(t, 2, store2.Len())
	events := store2.List(0, "")
	assert.Equal(t, "r2", events[0].ReviewID)
	assert.Equal(t, "r1", events[1].ReviewID)
}

func TestPersistence_LoadRespectsCapacity(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "events.json")

	// Créer un store de capacité 10, y mettre 5 events
	store := New(10)
	store.EnablePersistence(path)
	for i := 0; i < 5; i++ {
		store.Add(EventRecord{
			ReviewID: fmt.Sprintf("r%d", i), Camera: "cam",
			Timestamp: time.Date(2025, 3, 11, i, 0, 0, 0, time.UTC),
		})
	}

	// Charger dans un store de capacité 3 : seuls les 3 plus récents sont gardés
	store2 := New(3)
	err := store2.Load(path)
	require.NoError(t, err)

	assert.Equal(t, 3, store2.Len())
	events := store2.List(0, "")
	assert.Equal(t, "r4", events[0].ReviewID) // plus récent
	assert.Equal(t, "r2", events[2].ReviewID) // plus ancien gardé
}

func TestPersistence_LoadFileNotExists(t *testing.T) {
	store := New(10)
	err := store.Load("/tmp/does-not-exist-xyz.json")
	assert.NoError(t, err)
	assert.Equal(t, 0, store.Len())
}

func TestPersistence_LoadCorruptedFile(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "events.json")
	os.WriteFile(path, []byte("not json"), 0644)

	store := New(10)
	err := store.Load(path)
	assert.Error(t, err)
}

func TestPersistence_DisabledByDefault(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "events.json")

	// Sans EnablePersistence, Add() ne crée pas de fichier
	store := New(10)
	store.Add(EventRecord{ReviewID: "r1", Camera: "cam"})

	_, err := os.Stat(path)
	assert.True(t, os.IsNotExist(err))
}
