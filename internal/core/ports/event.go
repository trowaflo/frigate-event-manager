package ports

import "frigate-event-manager/internal/domain"

// EventProcessor est le port d'entrée du Core.
// C'est par cette interface que les adapters (MQTT, tests, etc.)
// envoient des événements au cerveau de l'application.
// Le Core ne sait pas d'où viennent les événements — il reçoit
// des objets domain propres, jamais du JSON brut.
type EventProcessor interface {
	ProcessEvent(payload domain.FrigatePayload) error
}

// EventHandler est le port de sortie du Core.
// Quand un événement passe tous les filtres, le Core appelle
// cette interface pour déclencher une action (notification, log...).
type EventHandler interface {
	HandleEvent(payload domain.FrigatePayload) error
}
