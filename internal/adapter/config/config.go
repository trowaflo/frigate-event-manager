package config

import (
	"encoding/json"
	"fmt"
	"os"
)

// Config contient toute la configuration de l'addon.
// En production, elle est lue depuis /data/options.json (fichier HA).
type Config struct {
	// MQTT
	MQTTBrokerURL string `json:"mqtt_broker_url"`
	MQTTTopic     string `json:"mqtt_topic"`
	MQTTClientID  string `json:"mqtt_client_id"`
	MQTTUsername  string `json:"mqtt_username"`
	MQTTPassword  string `json:"mqtt_password"`

	// Anti-spam
	Cooldown int `json:"cooldown"` // secondes, défaut 30
	Debounce int `json:"debounce"` // secondes, défaut 5

	// Home Assistant — résolu automatiquement via l'environnement Supervisor
	HABaseURL     string `json:"-"` // jamais dans le fichier config, défaut http://supervisor/core
	HAToken       string `json:"-"` // jamais dans le fichier config, vient de SUPERVISOR_TOKEN
	NotifyService string `json:"notify_service"`

	// Filtres
	SeverityFilter []string `json:"severity_filter"`
	Cameras        []string `json:"cameras"`
}

// HasNotifier retourne true si le token Supervisor est disponible
// et qu'un service de notification est configuré.
func (c *Config) HasNotifier() bool {
	return c.HAToken != "" && c.NotifyService != ""
}

func Load(path string) (*Config, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, fmt.Errorf("impossible de lire le fichier config %q: %w", path, err)
	}

	var cfg Config
	if err := json.Unmarshal(data, &cfg); err != nil {
		return nil, fmt.Errorf("impossible de parser la config JSON: %w", err)
	}

	cfg.applyDefaults()
	cfg.applyEnvOverrides()

	if err := cfg.validate(); err != nil {
		return nil, fmt.Errorf("config invalide: %w", err)
	}

	return &cfg, nil
}

func (c *Config) applyEnvOverrides() {
	if v := os.Getenv("MQTT_USERNAME"); v != "" {
		c.MQTTUsername = v
	}
	if v := os.Getenv("MQTT_PASSWORD"); v != "" {
		c.MQTTPassword = v
	}
	if v := os.Getenv("SUPERVISOR_TOKEN"); v != "" {
		c.HAToken = v
	}
}

func (c *Config) applyDefaults() {
	if c.MQTTTopic == "" {
		c.MQTTTopic = "frigate/reviews"
	}
	if c.MQTTClientID == "" {
		c.MQTTClientID = "frigate-event-manager"
	}
	if c.Cooldown == 0 {
		c.Cooldown = 30
	}
	if c.Debounce == 0 {
		c.Debounce = 5
	}
	c.HABaseURL = "http://supervisor/core"
}

func (c *Config) validate() error {
	if c.MQTTBrokerURL == "" {
		return fmt.Errorf("mqtt_broker_url est obligatoire")
	}
	return nil
}
