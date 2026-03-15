package supervisor

import (
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"strings"
	"time"
)

const supervisorURL = "http://supervisor"

// IngressInfo contient les infos ingress retournées par le Supervisor.
type IngressInfo struct {
	// MediaBaseURL est l'URL complète pour accéder à l'addon depuis l'extérieur.
	// Ex: "https://ha.example.com/api/hassio_ingress/TOKEN"
	// Vide si le Supervisor n'est pas joignable (dev local).
	MediaBaseURL string
}

// addonInfoResponse est la réponse de GET /addons/self/info
type addonInfoResponse struct {
	Data struct {
		IngressURL string `json:"ingress_url"`
	} `json:"data"`
}

// coreConfigResponse est la réponse de GET /core/api/config
type coreConfigResponse struct {
	ExternalURL string `json:"external_url"`
	InternalURL string `json:"internal_url"`
}

// FetchIngressInfo interroge l'API Supervisor pour obtenir l'URL complète de l'addon.
// Combine l'external_url HA avec l'ingress_url de l'addon.
// Retourne une info vide (sans erreur) si le Supervisor n'est pas joignable (dev local).
func FetchIngressInfo(supervisorToken string) (IngressInfo, error) {
	if supervisorToken == "" {
		return IngressInfo{}, nil
	}

	client := &http.Client{Timeout: 5 * time.Second}

	ingressPath, err := fetchIngressPath(client, supervisorToken)
	if err != nil || ingressPath == "" {
		return IngressInfo{}, err
	}

	externalURL, err := fetchExternalURL(client, supervisorToken)
	if err != nil || externalURL == "" {
		return IngressInfo{}, err
	}

	return IngressInfo{
		MediaBaseURL: strings.TrimRight(externalURL, "/") + ingressPath,
	}, nil
}

func fetchIngressPath(client *http.Client, token string) (string, error) {
	req, err := http.NewRequest(http.MethodGet, supervisorURL+"/addons/self/info", nil)
	if err != nil {
		return "", fmt.Errorf("impossible de créer la requête addon/info: %w", err)
	}
	req.Header.Set("Authorization", "Bearer "+token)

	resp, err := client.Do(req)
	if err != nil {
		return "", nil // pas de supervisor = dev local
	}
	defer func() { _ = resp.Body.Close() }()

	if resp.StatusCode != http.StatusOK {
		return "", nil
	}

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return "", fmt.Errorf("impossible de lire la réponse addon/info: %w", err)
	}

	var info addonInfoResponse
	if err := json.Unmarshal(body, &info); err != nil {
		return "", fmt.Errorf("impossible de parser addon/info: %w", err)
	}

	return strings.TrimRight(info.Data.IngressURL, "/"), nil
}

func fetchExternalURL(client *http.Client, token string) (string, error) {
	req, err := http.NewRequest(http.MethodGet, supervisorURL+"/core/api/config", nil)
	if err != nil {
		return "", fmt.Errorf("impossible de créer la requête core/api/config: %w", err)
	}
	req.Header.Set("Authorization", "Bearer "+token)

	resp, err := client.Do(req)
	if err != nil {
		return "", nil
	}
	defer func() { _ = resp.Body.Close() }()

	if resp.StatusCode != http.StatusOK {
		return "", nil
	}

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return "", fmt.Errorf("impossible de lire la réponse core/api/config: %w", err)
	}

	var cfg coreConfigResponse
	if err := json.Unmarshal(body, &cfg); err != nil {
		return "", fmt.Errorf("impossible de parser core/api/config: %w", err)
	}

	// Préférer l'URL externe, fallback sur interne
	if cfg.ExternalURL != "" {
		return cfg.ExternalURL, nil
	}
	return cfg.InternalURL, nil
}
