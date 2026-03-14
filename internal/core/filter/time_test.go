package filter_test

import (
	"testing"
	"time"

	"github.com/stretchr/testify/assert"

	"frigate-event-manager/internal/core/filter"
	"frigate-event-manager/internal/domain"
)

// clockFixe retourne une clock figée à l'heure UTC donnée.
func clockFixe(heure int) func() time.Time {
	t := time.Date(2026, 1, 1, heure, 0, 0, 0, time.UTC)
	return func() time.Time { return t }
}

func TestTimeFilter_ListeVideAccepteTout(t *testing.T) {
	f := filter.NewTimeFilter([]int{}, nil)

	assert.True(t, f.IsSatisfied(domain.EventState{}), "liste vide doit accepter à toute heure")
}

func TestTimeFilter_HeureDansListeBloquee(t *testing.T) {
	f := filter.NewTimeFilter([]int{0, 1, 2, 3, 4, 5, 22, 23}, clockFixe(3))

	assert.False(t, f.IsSatisfied(domain.EventState{}), "heure 3 est désactivée, doit bloquer")
}

func TestTimeFilter_HeureHorsListeAcceptee(t *testing.T) {
	f := filter.NewTimeFilter([]int{0, 1, 2, 3, 4, 5, 22, 23}, clockFixe(12))

	assert.True(t, f.IsSatisfied(domain.EventState{}), "heure 12 n'est pas désactivée, doit passer")
}

func TestTimeFilter_PremierreHeureBloquee(t *testing.T) {
	f := filter.NewTimeFilter([]int{0, 22, 23}, clockFixe(0))

	assert.False(t, f.IsSatisfied(domain.EventState{}), "minuit (heure 0) est désactivé")
}

func TestTimeFilter_DerniereHeureBloquee(t *testing.T) {
	f := filter.NewTimeFilter([]int{23}, clockFixe(23))

	assert.False(t, f.IsSatisfied(domain.EventState{}), "23h est désactivé")
}

func TestTimeFilter_HeureJusteAvantBloquee(t *testing.T) {
	f := filter.NewTimeFilter([]int{22}, clockFixe(21))

	assert.True(t, f.IsSatisfied(domain.EventState{}), "21h n'est pas dans la liste [22]")
}

func TestTimeFilter_ClockNilUtiliseTimeNow(t *testing.T) {
	// Vérifier que nil clock ne panique pas (utilise time.Now en production)
	f := filter.NewTimeFilter([]int{}, nil)

	assert.NotPanics(t, func() {
		f.IsSatisfied(domain.EventState{})
	})
}
