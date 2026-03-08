package throttle

import (
    "sync"
    "time"

    "frigate-event-manager/internal/core/ports"
    "frigate-event-manager/internal/domain"
)

// Throttler est un décorateur d'EventHandler qui limite le rythme
// des notifications pour éviter le spam.
//
// Deux protections :
//   - Cooldown : délai minimum entre deux events DIFFÉRENTS sur la même caméra
//   - Debounce : délai minimum entre deux notifications du MÊME event (updates)
type Throttler struct {
    next     ports.EventHandler
    cooldown time.Duration
    debounce time.Duration

    mu      sync.Mutex
    events  map[string]time.Time // review ID → dernière notif envoyée
    cameras map[string]time.Time // caméra → dernière notif d'un *nouvel* event
}

func New(next ports.EventHandler, cooldown, debounce time.Duration) *Throttler {
    return &Throttler{
        next:     next,
        cooldown: cooldown,
        debounce: debounce,
        events:   make(map[string]time.Time),
        cameras:  make(map[string]time.Time),
    }
}

func (t *Throttler) HandleEvent(payload domain.FrigatePayload) error {
    if !t.tryAcquire(payload) {
        return nil
    }
    return t.next.HandleEvent(payload)
}

// tryAcquire vérifie ET enregistre en une seule prise de lock.
// Le lock ne couvre que des opérations sur des maps (nanosecondes).
// L'appel HTTP se fait APRÈS, sans lock.
func (t *Throttler) tryAcquire(payload domain.FrigatePayload) bool {
    t.mu.Lock()
    defer t.mu.Unlock()

    now := time.Now()
    id := payload.After.ID
    camera := payload.After.Camera

    _, knownEvent := t.events[id]

    if knownEvent {
        if t.debounce > 0 {
            if last := t.events[id]; now.Sub(last) < t.debounce {
                return false
            }
        }
    } else {
        if t.cooldown > 0 {
            if last, ok := t.cameras[camera]; ok && now.Sub(last) < t.cooldown {
                return false
            }
        }
    }

    // Enregistre MAINTENANT, avant de relâcher le lock
    t.events[id] = now
    if !knownEvent {
        t.cameras[camera] = now
    }

    return true
}
