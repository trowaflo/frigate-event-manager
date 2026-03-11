package eventstore

import (
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
)

func TestAdd_And_List(t *testing.T) {
	s := New(10)
	now := time.Now()

	s.Add(EventRecord{ReviewID: "r1", Camera: "jardin", Severity: "alert", Timestamp: now})
	s.Add(EventRecord{ReviewID: "r2", Camera: "garage", Severity: "detection", Timestamp: now.Add(time.Second)})

	events := s.List(0, "")
	assert.Len(t, events, 2)
	assert.Equal(t, "r2", events[0].ReviewID, "plus recent en premier")
	assert.Equal(t, "r1", events[1].ReviewID)
}

func TestList_WithLimit(t *testing.T) {
	s := New(10)
	now := time.Now()

	for i := 0; i < 5; i++ {
		s.Add(EventRecord{ReviewID: "r", Camera: "cam", Severity: "alert", Timestamp: now.Add(time.Duration(i) * time.Second)})
	}

	events := s.List(3, "")
	assert.Len(t, events, 3)
}

func TestList_WithSeverityFilter(t *testing.T) {
	s := New(10)
	now := time.Now()

	s.Add(EventRecord{ReviewID: "r1", Severity: "alert", Timestamp: now})
	s.Add(EventRecord{ReviewID: "r2", Severity: "detection", Timestamp: now})
	s.Add(EventRecord{ReviewID: "r3", Severity: "alert", Timestamp: now})

	alerts := s.List(0, "alert")
	assert.Len(t, alerts, 2)

	detections := s.List(0, "detection")
	assert.Len(t, detections, 1)
}

func TestRingBuffer_Overflow(t *testing.T) {
	s := New(3)
	now := time.Now()

	s.Add(EventRecord{ReviewID: "r1", Timestamp: now})
	s.Add(EventRecord{ReviewID: "r2", Timestamp: now.Add(time.Second)})
	s.Add(EventRecord{ReviewID: "r3", Timestamp: now.Add(2 * time.Second)})
	s.Add(EventRecord{ReviewID: "r4", Timestamp: now.Add(3 * time.Second)})

	assert.Equal(t, 3, s.Len(), "ne dépasse pas la capacité")

	events := s.List(0, "")
	assert.Equal(t, "r4", events[0].ReviewID, "le plus récent")
	assert.Equal(t, "r2", events[2].ReviewID, "r1 a été éjecté")
}

func TestStats(t *testing.T) {
	s := New(100)
	now := time.Date(2025, 1, 2, 12, 0, 0, 0, time.UTC)
	s.now = func() time.Time { return now }

	// Event d'hier (hors 24h)
	s.Add(EventRecord{Severity: "alert", Timestamp: now.Add(-25 * time.Hour)})
	// Events dans les 24h
	s.Add(EventRecord{Severity: "alert", Timestamp: now.Add(-1 * time.Hour)})
	s.Add(EventRecord{Severity: "detection", Timestamp: now.Add(-30 * time.Minute)})
	s.Add(EventRecord{Severity: "alert", Timestamp: now.Add(-10 * time.Minute)})

	stats := s.Stats()
	assert.Equal(t, 3, stats.Events24h)
	assert.Equal(t, 2, stats.Alerts24h)
	assert.Equal(t, 1, stats.Detections24h)
}

func TestStats_EmptyStore(t *testing.T) {
	s := New(10)
	stats := s.Stats()
	assert.Equal(t, 0, stats.Events24h)
}
