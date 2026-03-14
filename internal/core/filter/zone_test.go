package filter_test

import (
	"testing"

	"github.com/stretchr/testify/assert"

	"frigate-event-manager/internal/core/filter"
	"frigate-event-manager/internal/domain"
)

func newEventWithZones(current, entered []string) domain.EventState {
	return domain.EventState{
		CurrentZones: current,
		EnteredZones: entered,
	}
}

// --- Liste vide ---

func TestZoneFilter_ListeVideAccepteTout(t *testing.T) {
	f := filter.NewZoneFilter([]string{}, false, false)

	assert.True(t, f.IsSatisfied(newEventWithZones(nil, nil)), "liste vide doit tout accepter")
	assert.True(t, f.IsSatisfied(newEventWithZones([]string{"jardin"}, nil)))
}

// --- ZoneMulti=false : au moins une zone ---

func TestZoneFilter_MultiFalse_AuMoinsUneZoneCurrentMatch(t *testing.T) {
	f := filter.NewZoneFilter([]string{"jardin", "entree"}, false, false)

	assert.True(t, f.IsSatisfied(newEventWithZones([]string{"jardin"}, nil)),
		"jardin est dans CurrentZones, doit passer")
}

func TestZoneFilter_MultiFalse_AuMoinsUneZoneEnteredMatch(t *testing.T) {
	f := filter.NewZoneFilter([]string{"jardin", "entree"}, false, false)

	assert.True(t, f.IsSatisfied(newEventWithZones(nil, []string{"entree"})),
		"entree est dans EnteredZones, doit passer")
}

func TestZoneFilter_MultiFalse_AucuneZoneMatch_Bloque(t *testing.T) {
	f := filter.NewZoneFilter([]string{"jardin", "entree"}, false, false)

	assert.False(t, f.IsSatisfied(newEventWithZones([]string{"garage"}, []string{"couloir"})),
		"aucune zone config dans l'événement, doit bloquer")
}

func TestZoneFilter_MultiFalse_ZonesVidesEvenement_Bloque(t *testing.T) {
	f := filter.NewZoneFilter([]string{"jardin"}, false, false)

	assert.False(t, f.IsSatisfied(newEventWithZones(nil, nil)),
		"événement sans zones, filtre non vide doit bloquer")
}

// --- ZoneMulti=true : toutes les zones requises ---

func TestZoneFilter_MultiTrue_ToutesZonesPresentes_Accepte(t *testing.T) {
	f := filter.NewZoneFilter([]string{"jardin", "entree"}, true, false)

	assert.True(t, f.IsSatisfied(newEventWithZones([]string{"jardin"}, []string{"entree"})),
		"jardin dans Current, entree dans Entered : toutes présentes")
}

func TestZoneFilter_MultiTrue_UneZoneManquante_Bloque(t *testing.T) {
	f := filter.NewZoneFilter([]string{"jardin", "entree"}, true, false)

	assert.False(t, f.IsSatisfied(newEventWithZones([]string{"jardin"}, nil)),
		"entree manquante, doit bloquer")
}

func TestZoneFilter_MultiTrue_ToutesZonesDansEntered_Accepte(t *testing.T) {
	f := filter.NewZoneFilter([]string{"jardin", "entree"}, true, false)

	assert.True(t, f.IsSatisfied(newEventWithZones(nil, []string{"jardin", "entree"})))
}

// --- ZoneOrderEnforced=true ---

func TestZoneFilter_OrderEnforced_OrdreRespecteDansEntered_Accepte(t *testing.T) {
	f := filter.NewZoneFilter([]string{"entree", "couloir", "jardin"}, true, true)

	// Sous-séquence dans l'ordre
	assert.True(t, f.IsSatisfied(newEventWithZones(
		nil,
		[]string{"entree", "couloir", "garage", "jardin"},
	)), "ordre respecté (sous-séquence)")
}

func TestZoneFilter_OrderEnforced_OrdreInverse_Bloque(t *testing.T) {
	f := filter.NewZoneFilter([]string{"entree", "couloir", "jardin"}, true, true)

	assert.False(t, f.IsSatisfied(newEventWithZones(
		nil,
		[]string{"jardin", "couloir", "entree"},
	)), "ordre inversé doit bloquer")
}

func TestZoneFilter_OrderEnforced_SousSequencePartielle_Bloque(t *testing.T) {
	f := filter.NewZoneFilter([]string{"entree", "couloir", "jardin"}, true, true)

	assert.False(t, f.IsSatisfied(newEventWithZones(
		nil,
		[]string{"entree", "jardin"}, // couloir manquant
	)), "couloir manquant dans la séquence, doit bloquer")
}

func TestZoneFilter_OrderEnforced_EnteredVide_Bloque(t *testing.T) {
	f := filter.NewZoneFilter([]string{"entree"}, true, true)

	assert.False(t, f.IsSatisfied(newEventWithZones([]string{"entree"}, nil)),
		"orderEnforced cherche dans EnteredZones uniquement, CurrentZones ignoré")
}

func TestZoneFilter_OrderEnforced_SeulementUneZone_Accepte(t *testing.T) {
	f := filter.NewZoneFilter([]string{"jardin"}, true, true)

	assert.True(t, f.IsSatisfied(newEventWithZones(nil, []string{"entree", "jardin"})))
}
