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
	// Vide si le Supervisor ne fournit pas l'info (dev local).
	MediaBaseURL string
}

// addonInfoResponse est la réponse de GET /addons/self/info
type addonInfoResponse struct {
	Data struct {
		IngressURL string `json:"ingress_url"`
	} `json:"data"`
}

// FetchIngressInfo interroge l'API Supervisor pour obtenir les infos ingress de l'addon.
// Retourne une info vide (sans erreur) si le Supervisor n'est pas joignable (dev local).
func FetchIngressInfo(supervisorToken string) (IngressInfo, error) {
	if supervisorToken == "" {
		return IngressInfo{}, nil
	}

	client := &http.Client{Timeout: 5 * time.Second}

	req, err := http.NewRequest(http.MethodGet, supervisorURL+"/addons/self/info", nil)
	if err != nil {
		return IngressInfo{}, fmt.Errorf("impossible de créer la requête supervisor: %w", err)
	}
	req.Header.Set("Authorization", "Bearer "+supervisorToken)

	resp, err := client.Do(req)
	if err != nil {
		// Pas de supervisor = dev local, pas une erreur fatale
		return IngressInfo{}, nil
	}
	defer func() { _ = resp.Body.Close() }()

	if resp.StatusCode != http.StatusOK {
		return IngressInfo{}, nil
	}

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return IngressInfo{}, fmt.Errorf("impossible de lire la réponse supervisor: %w", err)
	}

	var info addonInfoResponse
	if err := json.Unmarshal(body, &info); err != nil {
		return IngressInfo{}, fmt.Errorf("impossible de parser la réponse supervisor: %w", err)
	}

	return IngressInfo{
		MediaBaseURL: strings.TrimRight(info.Data.IngressURL, "/"),
	}, nil
}
