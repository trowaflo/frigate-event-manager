package filter

import "frigate-event-manager/internal/domain"

// ZoneFilter vérifie si un événement Frigate concerne une ou plusieurs zones configurées.
// Source : after.CurrentZones (zones actives) + after.EnteredZones (zones traversées).
//
// Comportement :
//   - Liste vide → tout accepter
//   - ZoneMulti=false → au moins une zone config présente dans CurrentZones ou EnteredZones
//   - ZoneMulti=true  → toutes les zones config présentes dans CurrentZones ou EnteredZones
//   - ZoneOrderEnforced=true → les zones config apparaissent dans cet ordre dans EnteredZones
type ZoneFilter struct {
	zones         []string
	multi         bool
	orderEnforced bool
}

// NewZoneFilter crée un filtre de zones.
//
//   - zones          : liste des zones acceptées (vide = tout accepter)
//   - multi          : true = toutes les zones requises, false = au moins une
//   - orderEnforced  : true = l'ordre des zones dans EnteredZones doit correspondre à zones
func NewZoneFilter(zones []string, multi bool, orderEnforced bool) *ZoneFilter {
	return &ZoneFilter{zones: zones, multi: multi, orderEnforced: orderEnforced}
}

// IsSatisfied retourne true si les zones de l'événement satisfont la configuration.
func (f *ZoneFilter) IsSatisfied(event domain.EventState) bool {
	if len(f.zones) == 0 {
		return true
	}

	if f.orderEnforced {
		return f.checkOrder(event.EnteredZones)
	}

	// Ensemble de recherche : union de CurrentZones et EnteredZones
	present := make(map[string]bool, len(event.CurrentZones)+len(event.EnteredZones))
	for _, z := range event.CurrentZones {
		present[z] = true
	}
	for _, z := range event.EnteredZones {
		present[z] = true
	}

	if f.multi {
		// Toutes les zones config doivent être présentes
		for _, z := range f.zones {
			if !present[z] {
				return false
			}
		}
		return true
	}

	// Au moins une zone config doit être présente
	for _, z := range f.zones {
		if present[z] {
			return true
		}
	}
	return false
}

// checkOrder vérifie que les zones config apparaissent dans cet ordre dans enteredZones.
// Les zones config doivent être une sous-séquence ordonnée de enteredZones.
func (f *ZoneFilter) checkOrder(enteredZones []string) bool {
	idx := 0
	for _, z := range enteredZones {
		if idx < len(f.zones) && z == f.zones[idx] {
			idx++
		}
	}
	return idx == len(f.zones)
}
