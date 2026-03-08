package filter

import "frigate-event-manager/internal/domain"

// SeverityFilter vérifie si la sévérité d'un événement Frigate
// fait partie des sévérités acceptées par l'utilisateur.
// Si aucune sévérité n'est configurée, tout est accepté.
type SeverityFilter struct {
    allowed []string
}

// NewSeverityFilter crée un filtre de sévérité.
// allowed = liste des sévérités acceptées (ex: ["alert", "detection"]).
// Si allowed est vide, le filtre laisse tout passer.
func NewSeverityFilter(allowed []string) *SeverityFilter {
    return &SeverityFilter{allowed: allowed}
}

// IsSatisfied retourne true si la sévérité de l'événement est acceptée.
func (f *SeverityFilter) IsSatisfied(event domain.EventState) bool {
    if len(f.allowed) == 0 {
        return true
    }
    for _, s := range f.allowed {
        if s == event.Severity {
            return true
        }
    }
    return false
}
