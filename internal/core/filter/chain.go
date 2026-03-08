package filter

import "frigate-event-manager/internal/domain"

// Filter est l'interface que tout filtre doit implémenter.
// Chaque filtre reçoit l'état complet de l'événement et décide
// s'il est satisfait (true) ou s'il bloque l'événement (false).
type Filter interface {
    IsSatisfied(event domain.EventState) bool
}

// FilterChain évalue une liste de filtres en AND logique.
// Si tous les filtres sont satisfaits → l'événement passe.
// Si un seul échoue → l'événement est bloqué.
// Une chaîne vide accepte tout.
type FilterChain struct {
    filters []Filter
}

// NewFilterChain crée une chaîne avec les filtres donnés.
func NewFilterChain(filters ...Filter) *FilterChain {
    return &FilterChain{filters: filters}
}

// IsSatisfied retourne true si TOUS les filtres sont satisfaits (AND logique).
func (c *FilterChain) IsSatisfied(event domain.EventState) bool {
    for _, f := range c.filters {
        if !f.IsSatisfied(event) {
            return false
        }
    }
    return true
}
