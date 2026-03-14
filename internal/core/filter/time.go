package filter

import (
	"slices"
	"time"

	"frigate-event-manager/internal/domain"
)

// TimeFilter bloque les événements pendant les heures de silence configurées.
// Les heures sont exprimées en UTC (0–23).
// Liste vide → tout accepter.
// L'heure est évaluée à chaque appel IsSatisfied (pas au boot).
type TimeFilter struct {
	disabledHours []int
	clock         func() time.Time
}

// NewTimeFilter crée un filtre de plages horaires.
//
//   - disabledHours : liste des heures UTC bloquées (ex: [0,1,2,3,22,23])
//   - clock         : source d'heure injectée pour les tests ; nil = time.Now
func NewTimeFilter(disabledHours []int, clock func() time.Time) *TimeFilter {
	if clock == nil {
		clock = time.Now
	}
	return &TimeFilter{disabledHours: disabledHours, clock: clock}
}

// IsSatisfied retourne true si l'heure actuelle n'est PAS dans les heures de silence.
func (f *TimeFilter) IsSatisfied(_ domain.EventState) bool {
	if len(f.disabledHours) == 0 {
		return true
	}
	currentHour := f.clock().UTC().Hour()
	if slices.Contains(f.disabledHours, currentHour) {
		return false
	}
	return true
}
