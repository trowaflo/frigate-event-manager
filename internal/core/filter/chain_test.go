package filter_test

import (
	"testing"

	"frigate-event-manager/internal/core/filter"
	"frigate-event-manager/internal/domain"
)

// stubFilter est un faux filtre pour les tests — il retourne toujours la même réponse.
type stubFilter struct {
	result bool
}

func (s *stubFilter) IsSatisfied(event domain.EventState) bool {
	return s.result
}

func TestFilterChain_EmptyChainAcceptsAll(t *testing.T) {
	// Aucun filtre configuré → tout passe (pas de raison de bloquer)
	chain := filter.NewFilterChain()

	event := domain.EventState{Severity: "alert"}
	if !chain.IsSatisfied(event) {
		t.Error("une chaîne vide devrait tout accepter")
	}
}

func TestFilterChain_AllFiltersPass(t *testing.T) {
	// Tous les filtres disent oui → l'événement passe
	chain := filter.NewFilterChain(
		&stubFilter{result: true},
		&stubFilter{result: true},
	)

	event := domain.EventState{Severity: "alert"}
	if !chain.IsSatisfied(event) {
		t.Error("tous les filtres passent, la chaîne devrait accepter")
	}
}

func TestFilterChain_OneFilterFails(t *testing.T) {
	// Un filtre dit non → l'événement est bloqué
	chain := filter.NewFilterChain(
		&stubFilter{result: true},
		&stubFilter{result: false},
		&stubFilter{result: true},
	)

	event := domain.EventState{Severity: "alert"}
	if chain.IsSatisfied(event) {
		t.Error("un filtre échoue, la chaîne devrait bloquer")
	}
}

func TestFilterChain_AllFiltersFail(t *testing.T) {
	// Tous les filtres disent non → évidemment bloqué
	chain := filter.NewFilterChain(
		&stubFilter{result: false},
		&stubFilter{result: false},
	)

	event := domain.EventState{Severity: "alert"}
	if chain.IsSatisfied(event) {
		t.Error("tous les filtres échouent, la chaîne devrait bloquer")
	}
}
