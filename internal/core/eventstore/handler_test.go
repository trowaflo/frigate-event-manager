package eventstore

import (
	"testing"

	"frigate-event-manager/internal/domain"

	"github.com/stretchr/testify/assert"
)

func TestHandler_RecordsEvent(t *testing.T) {
	store := New(10)
	h := NewHandler(store)

	err := h.HandleEvent(domain.FrigatePayload{
		Type: "new",
		After: domain.EventState{
			ID:        "review-123",
			Camera:    "jardin",
			Severity:  "alert",
			StartTime: 1704067200, // 2024-01-01 00:00:00 UTC
			Data: domain.EventData{
				Objects: []string{"person"},
				Zones:   []string{"front_yard"},
			},
		},
	})

	assert.NoError(t, err)
	assert.Equal(t, 1, store.Len())

	events := store.List(1, "")
	assert.Equal(t, "review-123", events[0].ReviewID)
	assert.Equal(t, "jardin", events[0].Camera)
	assert.Equal(t, []string{"person"}, events[0].Objects)
	assert.Equal(t, []string{"front_yard"}, events[0].Zones)
}

func TestHandler_SkipsEmptyCamera(t *testing.T) {
	store := New(10)
	h := NewHandler(store)

	_ = h.HandleEvent(domain.FrigatePayload{
		After: domain.EventState{ID: "r1", Camera: ""},
	})
	assert.Equal(t, 0, store.Len())
}

func TestHandler_SkipsEmptyID(t *testing.T) {
	store := New(10)
	h := NewHandler(store)

	_ = h.HandleEvent(domain.FrigatePayload{
		After: domain.EventState{ID: "", Camera: "jardin"},
	})
	assert.Equal(t, 0, store.Len())
}
