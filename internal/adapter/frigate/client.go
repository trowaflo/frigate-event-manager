package frigate

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"log/slog"
	"net/http"
	"strings"
	"sync"
	"time"
)

// Client gère l'authentification et les requêtes vers l'API Frigate.
// Il obtient un JWT via POST /api/login et le réutilise automatiquement.
type Client struct {
	baseURL  string
	user     string
	password string
	client   *http.Client
	logger   *slog.Logger

	mu    sync.Mutex
	token string
}

// NewClient crée un client Frigate authentifié.
func NewClient(baseURL, user, password string, logger *slog.Logger) *Client {
	return &Client{
		baseURL:  strings.TrimRight(baseURL, "/"),
		user:     user,
		password: password,
		client:   &http.Client{Timeout: 30 * time.Second},
		logger:   logger,
	}
}

type loginRequest struct {
	User     string `json:"user"`
	Password string `json:"password"`
}

// login obtient un JWT depuis Frigate via POST /api/login.
func (c *Client) login() error {
	body, err := json.Marshal(loginRequest{User: c.user, Password: c.password})
	if err != nil {
		return fmt.Errorf("impossible de sérialiser le login: %w", err)
	}

	resp, err := c.client.Post(c.baseURL+"/api/login", "application/json", bytes.NewReader(body))
	if err != nil {
		return fmt.Errorf("impossible de contacter Frigate pour le login: %w", err)
	}
	defer func() { _ = resp.Body.Close() }()

	if resp.StatusCode != http.StatusOK {
		respBody, _ := io.ReadAll(resp.Body)
		return fmt.Errorf("login Frigate échoué (HTTP %d): %s", resp.StatusCode, string(respBody))
	}

	// Le token JWT est dans le cookie set par Frigate
	for _, cookie := range resp.Cookies() {
		if cookie.Value != "" {
			c.token = cookie.Value
			c.logger.Debug("token Frigate obtenu", "cookie_name", cookie.Name)
			return nil
		}
	}

	// Fallback: essayer de lire le token depuis le body
	var result map[string]any
	respBody, _ := io.ReadAll(resp.Body)
	if err := json.Unmarshal(respBody, &result); err == nil {
		if token, ok := result["access_token"].(string); ok && token != "" {
			c.token = token
			c.logger.Debug("token Frigate obtenu depuis le body")
			return nil
		}
	}

	return fmt.Errorf("login Frigate réussi mais aucun token trouvé")
}

// ensureAuth s'assure qu'un token valide est disponible.
func (c *Client) ensureAuth() error {
	c.mu.Lock()
	defer c.mu.Unlock()

	if c.token != "" {
		return nil
	}
	return c.login()
}

// Do exécute une requête HTTP vers Frigate avec authentification.
// Retente une fois si le token a expiré (401).
func (c *Client) Do(req *http.Request) (*http.Response, error) {
	if err := c.ensureAuth(); err != nil {
		return nil, err
	}

	req.Header.Set("Authorization", "Bearer "+c.token)
	resp, err := c.client.Do(req)
	if err != nil {
		return nil, err
	}

	// Si 401, re-login et retry une fois
	if resp.StatusCode == http.StatusUnauthorized {
		_ = resp.Body.Close()
		c.mu.Lock()
		c.token = ""
		err = c.login()
		c.mu.Unlock()
		if err != nil {
			return nil, fmt.Errorf("re-login échoué: %w", err)
		}

		req.Header.Set("Authorization", "Bearer "+c.token)
		return c.client.Do(req)
	}

	return resp, nil
}

// Get effectue un GET authentifié vers un path relatif de l'API Frigate.
func (c *Client) Get(path string) (*http.Response, error) {
	url := c.baseURL + path
	req, err := http.NewRequest(http.MethodGet, url, nil)
	if err != nil {
		return nil, fmt.Errorf("impossible de créer la requête: %w", err)
	}
	return c.Do(req)
}

// BaseURL retourne l'URL de base de Frigate.
func (c *Client) BaseURL() string {
	return c.baseURL
}
