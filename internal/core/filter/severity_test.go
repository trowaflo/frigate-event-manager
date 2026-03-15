package filter_test

import (
	"testing"

	"frigate-event-manager/internal/core/filter"
	"frigate-event-manager/internal/domain"
)

func newEvent(severity string) domain.EventState {
	return domain.EventState{Severity: severity}
}

func TestSeverityFilter_AlertMatchesAlert(t *testing.T) {
	f := filter.NewSeverityFilter([]string{"alert"})

	if !f.IsSatisfied(newEvent("alert")) {
		t.Error("alert devrait satisfaire le filtre [alert]")
	}
}

func TestSeverityFilter_DetectionDoesNotMatchAlert(t *testing.T) {
	f := filter.NewSeverityFilter([]string{"alert"})

	if f.IsSatisfied(newEvent("detection")) {
		t.Error("detection ne devrait PAS satisfaire le filtre [alert]")
	}
}

func TestSeverityFilter_BothSeveritiesAccepted(t *testing.T) {
	f := filter.NewSeverityFilter([]string{"alert", "detection"})

	if !f.IsSatisfied(newEvent("alert")) {
		t.Error("alert devrait satisfaire [alert, detection]")
	}
	if !f.IsSatisfied(newEvent("detection")) {
		t.Error("detection devrait satisfaire [alert, detection]")
	}
}

func TestSeverityFilter_EmptyConfigAcceptsAll(t *testing.T) {
	f := filter.NewSeverityFilter([]string{})

	if !f.IsSatisfied(newEvent("alert")) {
		t.Error("filtre vide devrait accepter alert")
	}
	if !f.IsSatisfied(newEvent("detection")) {
		t.Error("filtre vide devrait accepter detection")
	}
}

func TestSeverityFilter_UnknownSeverityBlocked(t *testing.T) {
	f := filter.NewSeverityFilter([]string{"alert"})

	if f.IsSatisfied(newEvent("warning")) {
		t.Error("severity inconnue ne devrait PAS passer un filtre qui n'attend que alert")
	}
}
