package registry

import (
	"os"
	"path/filepath"
	"testing"
	"time"

	"frigate-event-manager/internal/domain"

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

func TestPersistence_LoadCorruptedFile(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "state.json")
	err := os.WriteFile(path, []byte("not valid json"), 0600)
	require.NoError(t, err)

	r := New(path)
	err = r.Load()
	assert.Error(t, err, "JSON corrompu doit retourner une erreur")
}

func TestPersistence_LoadReadError(t *testing.T) {
	// Tester via un répertoire avec le même nom que le fichier attendu
	dir := t.TempDir()
	subDir := filepath.Join(dir, "state.json")
	require.NoError(t, os.Mkdir(subDir, 0755))

	// statePath pointe sur un répertoire, pas un fichier → erreur de lecture
	r := New(subDir)
	err := r.Load()
	assert.Error(t, err, "lire un répertoire comme fichier doit retourner une erreur")
}

func TestPersistence_PersistLocked_WriteFailure(t *testing.T) {
	if os.Getuid() == 0 {
		t.Skip("test de permissions ignoré si root")
	}
	dir := t.TempDir()
	// Rendre le répertoire non-accessible en écriture
	require.NoError(t, os.Chmod(dir, 0555))
	t.Cleanup(func() { _ = os.Chmod(dir, 0755) })

	path := filepath.Join(dir, "state.json")
	r := New(path)
	// RecordEvent appelle persistLocked — l'erreur est loguée mais pas propagée
	// On vérifie que le fichier n'existe pas (écriture impossible)
	r.RecordEvent("cam1", "alert", []string{"person"})
	_, err := os.Stat(path)
	assert.True(t, os.IsNotExist(err), "le fichier ne doit pas exister si le dossier est en lecture seule")
}

func TestCamera_Unknown(t *testing.T) {
	r := New(tempStatePath(t))
	_, ok := r.Camera("inconnue")
	assert.False(t, ok)
}

func TestSetEnabled_NotifiesListener(t *testing.T) {
	r := New(tempStatePath(t))
	spy := &spyListener{}
	r.AddListener(spy)
	r.RecordEvent("garage", "detection", []string{"car"})

	// Réinitialiser l'espion après l'ajout initial
	spy.updated = nil

	err := r.SetEnabled("garage", false)
	require.NoError(t, err)
	assert.Len(t, spy.updated, 1, "SetEnabled doit notifier les listeners")
	assert.False(t, spy.updated[0].Enabled)
}

// --- tests Handler ---

func TestHandler_NewHandler(t *testing.T) {
	r := New(tempStatePath(t))
	h := NewHandler(r)
	assert.NotNil(t, h)
}

func TestHandler_HandleEvent_NouvelleCamera(t *testing.T) {
	r := New(tempStatePath(t))
	h := NewHandler(r)

	// Importer le package domain via une structure inline conforme
	// Le domaine est dans le même module — on utilise le type directement
	err := h.HandleEvent(frigatePayload("jardin", "alert", []string{"person"}))
	require.NoError(t, err)

	cam, ok := r.Camera("jardin")
	assert.True(t, ok)
	assert.Equal(t, "alert", cam.LastSeverity)
	assert.Equal(t, []string{"person"}, cam.LastObjects)
}

func TestHandler_HandleEvent_CameraVide(t *testing.T) {
	r := New(tempStatePath(t))
	h := NewHandler(r)

	err := h.HandleEvent(frigatePayload("", "alert", []string{"person"}))
	require.NoError(t, err)
	assert.Empty(t, r.Cameras(), "caméra vide ignorée")
}

func TestHandler_HandleEvent_PlusieursEvenements(t *testing.T) {
	r := New(tempStatePath(t))
	h := NewHandler(r)

	require.NoError(t, h.HandleEvent(frigatePayload("jardin", "detection", []string{"cat"})))
	require.NoError(t, h.HandleEvent(frigatePayload("jardin", "alert", []string{"person"})))
	require.NoError(t, h.HandleEvent(frigatePayload("garage", "detection", []string{"car"})))

	assert.Len(t, r.Cameras(), 2)
	cam, ok := r.Camera("jardin")
	assert.True(t, ok)
	assert.Equal(t, "alert", cam.LastSeverity)
	assert.Equal(t, 2, cam.EventCount24h)
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

// frigatePayload construit un FrigatePayload minimal pour les tests du Handler.
func frigatePayload(camera, severity string, objects []string) domain.FrigatePayload {
	return domain.FrigatePayload{
		Type: "new",
		After: domain.EventState{
			ID:       "test-review-id",
			Camera:   camera,
			Severity: severity,
			Data: domain.EventData{
				Objects: objects,
			},
		},
	}
}
