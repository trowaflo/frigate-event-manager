package filter

import (
	"slices"

	"frigate-event-manager/internal/domain"
)

// LabelFilter vérifie si un événement Frigate contient au moins un objet
// parmi les labels configurés.
// Source : after.Data.Objects (labels des objets détectés).
// Liste vide → tout accepter.
type LabelFilter struct {
	labels []string
}

// NewLabelFilter crée un filtre de labels.
// labels = liste des objets acceptés (ex: ["person", "car", "dog"]).
// Si labels est vide, le filtre laisse tout passer.
func NewLabelFilter(labels []string) *LabelFilter {
	return &LabelFilter{labels: labels}
}

// IsSatisfied retourne true si au moins un objet de l'événement est dans la liste des labels.
func (f *LabelFilter) IsSatisfied(event domain.EventState) bool {
	if len(f.labels) == 0 {
		return true
	}
	for _, obj := range event.Data.Objects {
		if slices.Contains(f.labels, obj) {
			return true
		}
	}
	return false
}
