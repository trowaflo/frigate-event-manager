package config_test

import (
	"os"
	"path/filepath"
	"testing"

	"frigate-event-manager/internal/adapter/config"
)

// writeTestFile crée un fichier temporaire avec le contenu donné.
// Retourne le chemin du fichier.
func writeTestFile(t *testing.T, content string) string {
	t.Helper()
	dir := t.TempDir()
	path := filepath.Join(dir, "options.json")
	if err := os.WriteFile(path, []byte(content), 0600); err != nil {
		t.Fatal(err)
	}
	return path
}

// --- Load : parsing et valeurs par défaut ---

func TestLoad_ValidConfig(t *testing.T) {
	path := writeTestFile(t, `{
        "mqtt_broker_url": "tcp://192.168.1.50:1883",
        "mqtt_topic": "frigate/reviews",
        "mqtt_client_id": "my-addon",
        "severity_filter": ["alert"],
        "cameras": ["front_cam", "jardin"]
    }`)

	cfg, err := config.Load(path)

	if err != nil {
		t.Fatalf("erreur inattendue: %v", err)
	}
	if cfg.MQTTBrokerURL != "tcp://192.168.1.50:1883" {
		t.Errorf("broker attendu 'tcp://192.168.1.50:1883', reçu '%s'", cfg.MQTTBrokerURL)
	}
	if cfg.MQTTTopic != "frigate/reviews" {
		t.Errorf("topic attendu 'frigate/reviews', reçu '%s'", cfg.MQTTTopic)
	}
	if cfg.MQTTClientID != "my-addon" {
		t.Errorf("client_id attendu 'my-addon', reçu '%s'", cfg.MQTTClientID)
	}
	if len(cfg.SeverityFilter) != 1 || cfg.SeverityFilter[0] != "alert" {
		t.Errorf("severity_filter attendu [alert], reçu %v", cfg.SeverityFilter)
	}
	if len(cfg.Cameras) != 2 {
		t.Errorf("cameras attendues 2, reçu %d", len(cfg.Cameras))
	}
}

func TestLoad_DefaultValues(t *testing.T) {
	path := writeTestFile(t, `{
        "mqtt_broker_url": "tcp://localhost:1883"
    }`)

	cfg, err := config.Load(path)

	if err != nil {
		t.Fatalf("erreur inattendue: %v", err)
	}
	if cfg.MQTTTopic != "frigate/reviews" {
		t.Errorf("topic par défaut attendu 'frigate/reviews', reçu '%s'", cfg.MQTTTopic)
	}
	if cfg.MQTTClientID != "frigate-event-manager" {
		t.Errorf("client_id par défaut attendu 'frigate-event-manager', reçu '%s'", cfg.MQTTClientID)
	}
	if cfg.Cooldown != 30 {
		t.Errorf("cooldown par défaut attendu 30, reçu %d", cfg.Cooldown)
	}
	if cfg.Debounce != 5 {
		t.Errorf("debounce par défaut attendu 5, reçu %d", cfg.Debounce)
	}
	if cfg.HABaseURL != "http://supervisor/core" {
		t.Errorf("ha_base_url par défaut attendu 'http://supervisor/core', reçu '%s'", cfg.HABaseURL)
	}
}

func TestLoad_MissingBrokerURL_ReturnsError(t *testing.T) {
	path := writeTestFile(t, `{
        "mqtt_topic": "frigate/reviews"
    }`)

	_, err := config.Load(path)

	if err == nil {
		t.Fatal("une erreur était attendue quand mqtt_broker_url est vide")
	}
}

func TestLoad_FileNotFound_ReturnsError(t *testing.T) {
	_, err := config.Load("/chemin/inexistant/options.json")

	if err == nil {
		t.Fatal("une erreur était attendue pour un fichier inexistant")
	}
}

func TestLoad_InvalidJSON_ReturnsError(t *testing.T) {
	path := writeTestFile(t, `{invalid json`)

	_, err := config.Load(path)

	if err == nil {
		t.Fatal("une erreur était attendue pour du JSON invalide")
	}
}

func TestLoad_EmptySeverityFilter_AcceptsAll(t *testing.T) {
	path := writeTestFile(t, `{
        "mqtt_broker_url": "tcp://localhost:1883",
        "severity_filter": []
    }`)

	cfg, err := config.Load(path)

	if err != nil {
		t.Fatalf("erreur inattendue: %v", err)
	}
	if len(cfg.SeverityFilter) != 0 {
		t.Errorf("severity_filter vide attendu, reçu %v", cfg.SeverityFilter)
	}
}

// --- Env overrides ---

func TestLoad_EnvOverrides_MQTTCredentials(t *testing.T) {
	path := writeTestFile(t, `{
        "mqtt_broker_url": "tcp://localhost:1883"
    }`)

	t.Setenv("MQTT_USERNAME", "env_user")
	t.Setenv("MQTT_PASSWORD", "env_pass")

	cfg, err := config.Load(path)

	if err != nil {
		t.Fatalf("erreur inattendue: %v", err)
	}
	if cfg.MQTTUsername != "env_user" {
		t.Errorf("username attendu 'env_user', reçu '%s'", cfg.MQTTUsername)
	}
	if cfg.MQTTPassword != "env_pass" {
		t.Errorf("password attendu 'env_pass', reçu '%s'", cfg.MQTTPassword)
	}
}

func TestLoad_EnvOverrides_SupervisorToken(t *testing.T) {
	path := writeTestFile(t, `{
        "mqtt_broker_url": "tcp://localhost:1883",
        "notify_service": "mobile_app_iphone"
    }`)

	t.Setenv("SUPERVISOR_TOKEN", "supervisor_jwt_token")

	cfg, err := config.Load(path)

	if err != nil {
		t.Fatalf("erreur inattendue: %v", err)
	}
	if cfg.HAToken != "supervisor_jwt_token" {
		t.Errorf("token attendu 'supervisor_jwt_token', reçu '%s'", cfg.HAToken)
	}
	if !cfg.HasNotifier() {
		t.Error("devrait avoir un notifier avec SUPERVISOR_TOKEN + notify_service")
	}
}

// --- HasNotifier ---

func TestConfig_HasNotifier_True(t *testing.T) {
	cfg := &config.Config{
		HAToken:       "token",
		NotifyService: "mobile_app_iphone",
	}
	if !cfg.HasNotifier() {
		t.Error("devrait avoir un notifier quand token + service sont remplis")
	}
}

func TestConfig_HasNotifier_False_MissingToken(t *testing.T) {
	cfg := &config.Config{
		NotifyService: "mobile_app_iphone",
	}
	if cfg.HasNotifier() {
		t.Error("ne devrait PAS avoir un notifier sans token")
	}
}

func TestConfig_HasNotifier_False_MissingService(t *testing.T) {
	cfg := &config.Config{
		HAToken: "token",
	}
	if cfg.HasNotifier() {
		t.Error("ne devrait PAS avoir un notifier sans notify_service")
	}
}

// --- Sanitized ---

func TestConfig_Sanitized_MasksSecrets(t *testing.T) {
	cfg := &config.Config{
		MQTTBrokerURL:   "tcp://localhost:1883",
		MQTTTopic:       "frigate/reviews",
		MQTTUsername:     "user",
		MQTTPassword:     "secret_password",
		FrigateURL:       "http://frigate:5000",
		FrigateUser:      "admin",
		FrigatePassword:  "frigate_secret",
		NotifyService:    "persistent_notification",
		Cooldown:         30,
		Debounce:         5,
		TTL:              30,
		APIPort:          5555,
		PresignTTL:       60,
		SeverityFilter:   []string{"alert"},
	}

	s := cfg.Sanitized()

	// Valeurs visibles
	if s["mqtt_broker_url"] != "tcp://localhost:1883" {
		t.Errorf("mqtt_broker_url attendu, reçu %v", s["mqtt_broker_url"])
	}
	if s["frigate_user"] != "admin" {
		t.Errorf("frigate_user attendu 'admin', reçu %v", s["frigate_user"])
	}
	if s["cooldown"] != 30 {
		t.Errorf("cooldown attendu 30, reçu %v", s["cooldown"])
	}

	// Secrets masqués
	if s["mqtt_password"] != "***" {
		t.Errorf("mqtt_password devrait être masqué, reçu %v", s["mqtt_password"])
	}
	if s["frigate_password"] != "***" {
		t.Errorf("frigate_password devrait être masqué, reçu %v", s["frigate_password"])
	}
}

func TestConfig_Sanitized_EmptyPasswordsStayEmpty(t *testing.T) {
	cfg := &config.Config{
		MQTTBrokerURL: "tcp://localhost:1883",
	}

	s := cfg.Sanitized()

	if s["mqtt_password"] != "" {
		t.Errorf("mot de passe vide devrait rester vide, reçu %v", s["mqtt_password"])
	}
	if s["frigate_password"] != "" {
		t.Errorf("mot de passe vide devrait rester vide, reçu %v", s["frigate_password"])
	}
}
