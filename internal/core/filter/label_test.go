package filter_test

import (
	"testing"

	"github.com/stretchr/testify/assert"

	"frigate-event-manager/internal/core/filter"
	"frigate-event-manager/internal/domain"
)

func newEventWithObjects(objects ...string) domain.EventState {
	return domain.EventState{
		Data: domain.EventData{Objects: objects},
	}
}

func TestLabelFilter_ListeVideAccepteTout(t *testing.T) {
	f := filter.NewLabelFilter([]string{})

	assert.True(t, f.IsSatisfied(newEventWithObjects("person")), "liste vide doit accepter person")
	assert.True(t, f.IsSatisfied(newEventWithObjects()), "liste vide doit accepter sans objets")
}

func TestLabelFilter_LabelPresentAccepte(t *testing.T) {
	f := filter.NewLabelFilter([]string{"person"})

	assert.True(t, f.IsSatisfied(newEventWithObjects("person")))
}

func TestLabelFilter_LabelAbsentBloque(t *testing.T) {
	f := filter.NewLabelFilter([]string{"person"})

	assert.False(t, f.IsSatisfied(newEventWithObjects("car")))
}

func TestLabelFilter_AuMoinsUnLabelSuffit(t *testing.T) {
	f := filter.NewLabelFilter([]string{"person", "car"})

	assert.True(t, f.IsSatisfied(newEventWithObjects("car", "dog")),
		"car est dans la liste config, doit passer")
}

func TestLabelFilter_AucunLabelMatchBloque(t *testing.T) {
	f := filter.NewLabelFilter([]string{"person", "car"})

	assert.False(t, f.IsSatisfied(newEventWithObjects("dog", "cat")))
}

func TestLabelFilter_EvenementSansObjetsBloque(t *testing.T) {
	f := filter.NewLabelFilter([]string{"person"})

	assert.False(t, f.IsSatisfied(newEventWithObjects()))
}

func TestLabelFilter_MultipleObjectsDontUnMatch(t *testing.T) {
	f := filter.NewLabelFilter([]string{"dog"})

	assert.True(t, f.IsSatisfied(newEventWithObjects("person", "car", "dog")))
}
