package domain

// FrigatePayload représente un message MQTT reçu de Frigate sur le topic reviews.
// Chaque message a un type (new/update/end) et deux snapshots de l'événement :
// - Before : l'état précédent (vide pour "new")
// - After  : l'état actuel après la mise à jour
type FrigatePayload struct {
	Type   string     `json:"type"`
	Before EventState `json:"before"`
	After  EventState `json:"after"`
}

// EventState représente l'état d'un review Frigate à un instant T.
type EventState struct {
	ID           string    `json:"id"`
	Camera       string    `json:"camera"`
	StartTime    float64   `json:"start_time"`
	EndTime      *float64  `json:"end_time"` // nil = événement en cours
	Severity     string    `json:"severity"`
	ThumbPath    string    `json:"thumb_path"`
	Data         EventData `json:"data"`
	CurrentZones []string  `json:"current_zones"` // zones actuellement occupées
	EnteredZones []string  `json:"entered_zones"` // zones traversées depuis le début
}

// EventData contient les données de détection associées au review.
type EventData struct {
	Detections []string `json:"detections"`
	Objects    []string `json:"objects"`
	SubLabels  []string `json:"sub_labels"`
	Zones      []string `json:"zones"`
	Audio      []string `json:"audio"`
}
