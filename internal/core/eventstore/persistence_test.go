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
	require.NoError(t, os.WriteFile(path, []byte("not json"), 0644))

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

func TestPersistence_AtomicWrite_NoTempFilesRemaining(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "events.json")

	store := New(10)
	store.EnablePersistence(path)
	store.Add(EventRecord{ReviewID: "r1", Camera: "cam", Severity: "alert"})

	// Vérifier qu'aucun fichier .tmp ne reste
	entries, err := os.ReadDir(dir)
	require.NoError(t, err)
	for _, e := range entries {
		assert.NotContains(t, e.Name(), ".tmp", "fichier temporaire non nettoyé: %s", e.Name())
	}
}

func TestPersistence_PersistLocked_EchecSiDossierNonAccessible(t *testing.T) {
	if os.Getuid() == 0 {
		t.Skip("test de permissions ignoré si root")
	}
	dir := t.TempDir()

	// Créer d'abord le fichier avec du contenu valide
	path := filepath.Join(dir, "events.json")
	store := New(10)
	store.EnablePersistence(path)
	store.Add(EventRecord{ReviewID: "r1", Camera: "cam"})

	// Vérifier que le fichier a bien été créé
	_, err := os.Stat(path)
	require.NoError(t, err)

	// Maintenant rendre le répertoire non-accessible en écriture
	require.NoError(t, os.Chmod(dir, 0555))
	t.Cleanup(func() { _ = os.Chmod(dir, 0755) })

	// Tenter d'écrire à nouveau : l'erreur est loguée, pas retournée par Add
	store.Add(EventRecord{ReviewID: "r2", Camera: "cam2"})
	// Le store contient bien les 2 events en mémoire
	assert.Equal(t, 2, store.Len())
}

func TestPersistence_Load_EchecSiFichierEstUnDossier(t *testing.T) {
	dir := t.TempDir()
	// Créer un dossier avec le même nom que le fichier attendu
	fakeFile := filepath.Join(dir, "events.json")
	require.NoError(t, os.Mkdir(fakeFile, 0755))

	store := New(10)
	err := store.Load(fakeFile)
	assert.Error(t, err, "lire un répertoire comme fichier doit retourner une erreur")
}
