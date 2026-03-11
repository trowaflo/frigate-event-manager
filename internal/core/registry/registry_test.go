package registry

import (
	"os"
	"path/filepath"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func tempStatePath(t *testing.T) string {
	t.Helper()
	return filepath.Join(t.TempDir(), "state.json")
}

func TestRecordEvent_NewCamera(t *testing.T) {
	r := New(tempStatePath(t))

	isNew := r.RecordEvent("jardin", "alert", []string{"person"})

	assert.True(t, isNew, "devrait être une nouvelle caméra")
	cam, ok := r.Camera("jardin")
	assert.True(t, ok)
	assert.Equal(t, "jardin", cam.Name)
	assert.True(t, cam.Enabled, "activée par défaut")
	assert.Equal(t, "alert", cam.LastSeverity)
	assert.Equal(t, []string{"person"}, cam.LastObjects)
	assert.Equal(t, 1, cam.EventCount24h)
}

func TestRecordEvent_ExistingCamera(t *testing.T) {
	r := New(tempStatePath(t))

	r.RecordEvent("jardin", "detection", []string{"cat"})
	isNew := r.RecordEvent("jardin", "alert", []string{"person"})

	assert.False(t, isNew, "caméra déjà connue")
	cam, _ := r.Camera("jardin")
	assert.Equal(t, "alert", cam.LastSeverity)
	assert.Equal(t, []string{"person"}, cam.LastObjects)
	assert.Equal(t, 2, cam.EventCount24h)
}

func TestSetEnabled(t *testing.T) {
	r := New(tempStatePath(t))
	r.RecordEvent("garage", "detection", []string{"car"})

	assert.True(t, r.IsEnabled("garage"))

	err := r.SetEnabled("garage", false)
	require.NoError(t, err)
	assert.False(t, r.IsEnabled("garage"))

	err = r.SetEnabled("garage", true)
	require.NoError(t, err)
	assert.True(t, r.IsEnabled("garage"))
}

func TestSetEnabled_UnknownCamera(t *testing.T) {
	r := New(tempStatePath(t))

	err := r.SetEnabled("inconnu", false)
	assert.Error(t, err)
}

func TestIsEnabled_UnknownCamera(t *testing.T) {
	r := New(tempStatePath(t))

	assert.True(t, r.IsEnabled("inconnu"), "caméra inconnue = activée par défaut")
}

func TestCameras(t *testing.T) {
	r := New(tempStatePath(t))
	r.RecordEvent("jardin", "alert", []string{"person"})
	r.RecordEvent("garage", "detection", []string{"car"})

	cams := r.Cameras()
	assert.Len(t, cams, 2)

	names := map[string]bool{}
	for _, c := range cams {
		names[c.Name] = true
	}
	assert.True(t, names["jardin"])
	assert.True(t, names["garage"])
}

func TestPersistence_LoadSave(t *testing.T) {
	path := tempStatePath(t)

	// Premier registry : enregistrer des caméras
	r1 := New(path)
	r1.RecordEvent("jardin", "alert", []string{"person"})
	r1.RecordEvent("garage", "detection", []string{"car"})
	require.NoError(t, r1.SetEnabled("garage", false))

	// Deuxième registry : charger depuis le fichier
	r2 := New(path)
	require.NoError(t, r2.Load())

	cams := r2.Cameras()
	assert.Len(t, cams, 2)

	jardin, ok := r2.Camera("jardin")
	assert.True(t, ok)
	assert.True(t, jardin.Enabled)
	assert.Equal(t, "alert", jardin.LastSeverity)

	garage, ok := r2.Camera("garage")
	assert.True(t, ok)
	assert.False(t, garage.Enabled, "should stay disabled after reload")
}

func TestPersistence_LoadMissingFile(t *testing.T) {
	r := New(filepath.Join(t.TempDir(), "nonexistent.json"))

	err := r.Load()
	assert.NoError(t, err, "fichier manquant = premier démarrage, pas d'erreur")
	assert.Empty(t, r.Cameras())
}

func TestEventCount24h_Expiry(t *testing.T) {
	path := tempStatePath(t)
	r := New(path)

	now := time.Date(2025, 1, 1, 12, 0, 0, 0, time.UTC)
	r.now = func() time.Time { return now }

	r.RecordEvent("jardin", "alert", []string{"person"})

	// Avancer de 25h
	now = now.Add(25 * time.Hour)
	r.RecordEvent("jardin", "detection", []string{"cat"})

	cam, _ := r.Camera("jardin")
	assert.Equal(t, 1, cam.EventCount24h, "l'ancien événement devrait avoir expiré")
}

func TestListener_OnCameraAdded(t *testing.T) {
	r := New(tempStatePath(t))
	spy := &spyListener{}
	r.AddListener(spy)

	r.RecordEvent("jardin", "alert", []string{"person"})

	assert.Len(t, spy.added, 1)
	assert.Equal(t, "jardin", spy.added[0].Name)
	assert.Empty(t, spy.updated)
}

func TestListener_OnCameraUpdated(t *testing.T) {
	r := New(tempStatePath(t))
	spy := &spyListener{}
	r.AddListener(spy)

	r.RecordEvent("jardin", "detection", []string{"cat"})
	r.RecordEvent("jardin", "alert", []string{"person"})

	assert.Len(t, spy.added, 1)
	assert.Len(t, spy.updated, 1)
	assert.Equal(t, "alert", spy.updated[0].LastSeverity)
}

func TestPersistence_AtomicWrite(t *testing.T) {
	path := tempStatePath(t)
	r := New(path)
	r.RecordEvent("jardin", "alert", []string{"person"})

	// Le fichier doit exister
	_, err := os.Stat(path)
	assert.NoError(t, err)

	// Pas de fichiers temporaires restants
	entries, _ := os.ReadDir(filepath.Dir(path))
	for _, e := range entries {
		assert.NotContains(t, e.Name(), ".tmp", "fichier temporaire non nettoyé")
	}
}

// --- spy ---

type spyListener struct {
	added   []CameraState
	updated []CameraState
}

func (s *spyListener) OnCameraAdded(cam CameraState) {
	s.added = append(s.added, cam)
}

func (s *spyListener) OnCameraUpdated(cam CameraState) {
	s.updated = append(s.updated, cam)
}
