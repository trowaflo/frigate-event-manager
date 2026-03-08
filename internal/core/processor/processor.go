package processor

import (
    "frigate-event-manager/internal/core/filter"
    "frigate-event-manager/internal/core/ports"
    "frigate-event-manager/internal/domain"
)

// Processor est le cerveau de l'application.
// Il reçoit des événements Frigate, les passe dans la chaîne de filtres,
// et appelle le handler si l'événement est accepté.
type Processor struct {
    filters *filter.FilterChain
    handler ports.EventHandler
}

// NewProcessor crée un Processor avec sa chaîne de filtres et son handler de sortie.
func NewProcessor(filters *filter.FilterChain, handler ports.EventHandler) *Processor {
    return &Processor{
        filters: filters,
        handler: handler,
    }
}

// ProcessEvent traite un événement Frigate.
// Pour l'instant, seuls les événements "new" sont traités.
// Les "update" et "end" seront gérés quand on implémentera la boucle.
func (p *Processor) ProcessEvent(payload domain.FrigatePayload) error {
    if payload.Type != "new" {
        return nil
    }

    if !p.filters.IsSatisfied(payload.After) {
        return nil
    }

    return p.handler.HandleEvent(payload)
}
