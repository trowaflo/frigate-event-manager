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
	TTL      int `json:"ttl"`      // minutes, défaut 30

	// Home Assistant — résolu automatiquement via l'environnement Supervisor
	HABaseURL     string `json:"-"` // jamais dans le fichier config, défaut http://supervisor/core
	HAToken       string `json:"-"` // jamais dans le fichier config, vient de SUPERVISOR_TOKEN
	NotifyService string `json:"notify_service"`

	// Frigate
	FrigateURL      string `json:"frigate_url"`
	FrigateUser     string `json:"frigate_user"`
	FrigatePassword string `json:"frigate_password"`
	APIPort         int    `json:"api_port"`
	PresignTTL      int    `json:"presign_ttl"` // minutes, défaut 60

	// Media — URL de base pour les presigned URLs dans les notifications.
	// En prod HA, résolu automatiquement via l'external URL HA + ingress path.
	// En dev, fallback sur localhost:APIPort.
	MediaBaseURL string `json:"media_base_url"`

	// Persistence
	PersistEvents bool `json:"persist_events"` // sauvegarde le ring buffer sur disque

	// HACS — désactive le MQTT Discovery quand l'intégration HACS gère les entités.
	// Absent ou true = MQTT Discovery actif (comportement par défaut).
	// false = MQTT Discovery désactivé, entités gérées par l'intégration HACS.
	MQTTDiscovery *bool `json:"mqtt_discovery"`

	// Filtres
	SeverityFilter    []string `json:"severity_filter"`
	Cameras           []string `json:"cameras"`
	Zones             []string `json:"zones"`
	ZoneMulti         bool     `json:"zone_multi"`
	ZoneOrderEnforced bool     `json:"zone_order_enforced"`
	Labels            []string `json:"labels"`
	DisableTimes      []int    `json:"disable_times"`
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

// SetMediaBaseURL définit l'URL de base pour les presigned URLs.
// Priorité : config explicite > ingressURL (Supervisor) > localhost (dev).
func (c *Config) SetMediaBaseURL(ingressURL string) {
	if !c.HasFrigate() {
		return
	}
	if c.MediaBaseURL != "" {
		return // configuré explicitement par l'utilisateur
	}
	if ingressURL != "" {
		c.MediaBaseURL = ingressURL
		return
	}
	c.MediaBaseURL = fmt.Sprintf("http://localhost:%d", c.APIPort)
}

// HasFrigate retourne true si l'URL Frigate et les credentials sont configurés.
func (c *Config) HasFrigate() bool {
	return c.FrigateURL != "" && c.FrigateUser != "" && c.FrigatePassword != ""
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
	if v := os.Getenv("FRIGATE_USER"); v != "" {
		c.FrigateUser = v
	}
	if v := os.Getenv("FRIGATE_PASSWORD"); v != "" {
		c.FrigatePassword = v
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
	if c.TTL == 0 {
		c.TTL = 30
	}
	if c.APIPort == 0 {
		c.APIPort = 5555
	}
	if c.PresignTTL == 0 {
		c.PresignTTL = 60
	}
	if c.MQTTDiscovery == nil {
		v := true
		c.MQTTDiscovery = &v
	}
	c.HABaseURL = "http://supervisor/core"
}

// MQTTDiscoveryEnabled retourne true si le MQTT Discovery est actif.
// Absent dans la config = true (comportement par défaut préservé).
func (c *Config) MQTTDiscoveryEnabled() bool {
	return c.MQTTDiscovery != nil && *c.MQTTDiscovery
}

// Sanitized retourne la config sans secrets pour affichage dans la Web UI.
// Les mots de passe sont masqués, les tokens sont omis.
func (c *Config) Sanitized() map[string]any {
	mask := func(s string) string {
		if s == "" {
			return ""
		}
		return "***"
	}
	return map[string]any{
		"mqtt_broker_url":     c.MQTTBrokerURL,
		"mqtt_topic":          c.MQTTTopic,
		"mqtt_client_id":      c.MQTTClientID,
		"mqtt_username":       c.MQTTUsername,
		"mqtt_password":       mask(c.MQTTPassword),
		"notify_service":      c.NotifyService,
		"frigate_url":         c.FrigateURL,
		"frigate_user":        c.FrigateUser,
		"frigate_password":    mask(c.FrigatePassword),
		"api_port":            c.APIPort,
		"presign_ttl":         c.PresignTTL,
		"media_base_url":      c.MediaBaseURL,
		"cooldown":            c.Cooldown,
		"debounce":            c.Debounce,
		"ttl":                 c.TTL,
		"persist_events":      c.PersistEvents,
		"severity_filter":     c.SeverityFilter,
		"cameras":             c.Cameras,
		"zones":               c.Zones,
		"zone_multi":          c.ZoneMulti,
		"zone_order_enforced": c.ZoneOrderEnforced,
		"labels":              c.Labels,
		"disable_times":       c.DisableTimes,
		"mqtt_discovery":      c.MQTTDiscoveryEnabled(),
	}
}

func (c *Config) validate() error {
	if c.MQTTBrokerURL == "" {
		return fmt.Errorf("mqtt_broker_url est obligatoire")
	}
	return nil
}
