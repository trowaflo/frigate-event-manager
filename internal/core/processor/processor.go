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

func NewProcessor(filters *filter.FilterChain, handler ports.EventHandler) *Processor {
	return &Processor{
		filters: filters,
		handler: handler,
	}
}

// ProcessEvent traite un événement Frigate.
// Les trois types (new, update, end) suivent le même flux : filtre → handler.
// Le throttler gère le cleanup en interne quand il reçoit un "end".
func (p *Processor) ProcessEvent(payload domain.FrigatePayload) error {
	if payload.Type != "new" && payload.Type != "update" && payload.Type != "end" {
		return nil
	}

	if !p.filters.IsSatisfied(payload.After) {
		return nil
	}

	return p.handler.HandleEvent(payload)
}
