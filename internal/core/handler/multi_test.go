package handler_test

import (
	"errors"
	"io"
	"log/slog"
	"testing"

	"frigate-event-manager/internal/core/handler"
	"frigate-event-manager/internal/core/ports"
	"frigate-event-manager/internal/domain"

	"github.com/stretchr/testify/assert"
)

var _ ports.EventHandler = (*handler.Multi)(nil)

type spyHandler struct {
	called  bool
	payload domain.FrigatePayload
	err     error
}

func (s *spyHandler) HandleEvent(p domain.FrigatePayload) error {
	s.called = true
	s.payload = p
	return s.err
}

func newTestLogger() *slog.Logger {
	return slog.New(slog.NewTextHandler(io.Discard, nil))
}

func TestMulti_DispatchesToAllHandlers(t *testing.T) {
	h1 := &spyHandler{}
	h2 := &spyHandler{}

	multi := handler.NewMulti(newTestLogger())
	multi.Add("h1", h1)
	multi.Add("h2", h2)

	payload := domain.FrigatePayload{
		Type:  "new",
		After: domain.EventState{ID: "r123", Camera: "front"},
	}

	err := multi.HandleEvent(payload)

	assert.NoError(t, err)
	assert.True(t, h1.called)
	assert.True(t, h2.called)
	assert.Equal(t, "r123", h1.payload.After.ID)
	assert.Equal(t, "r123", h2.payload.After.ID)
}

func TestMulti_ContinuesOnError(t *testing.T) {
	failing := &spyHandler{err: errors.New("boom")}
	passing := &spyHandler{}

	multi := handler.NewMulti(newTestLogger())
	multi.Add("failing", failing)
	multi.Add("passing", passing)

	err := multi.HandleEvent(domain.FrigatePayload{
		Type:  "new",
		After: domain.EventState{ID: "r456"},
	})

	assert.NoError(t, err, "Multi should never return an error")
	assert.True(t, failing.called)
	assert.True(t, passing.called, "passing handler should still be called after failing one")
}

func TestMulti_NoHandlers(t *testing.T) {
	multi := handler.NewMulti(newTestLogger())
	err := multi.HandleEvent(domain.FrigatePayload{})
	assert.NoError(t, err)
}
