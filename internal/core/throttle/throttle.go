package throttle

import (
	"sync"
	"time"

	"frigate-event-manager/internal/core/ports"
	"frigate-event-manager/internal/domain"
)

// defaultTTL est le délai de sécurité au-delà duquel une entrée est purgée
// si le "end" n'est jamais arrivé (ceinture-bretelles).
const defaultTTL = 30 * time.Minute

// Throttler est un décorateur d'EventHandler qui limite le rythme
// des notifications pour éviter le spam.
//
// Deux protections :
//   - Cooldown : délai minimum entre deux events DIFFÉRENTS sur la même caméra
//   - Debounce : délai minimum entre deux notifications du MÊME event (updates)
//
// Deux mécanismes de nettoyage :
//   - Event "end" : HandleEvent détecte le type "end" → supprime l'entrée immédiatement
//   - TTL (lazy) : purge les entrées > 30 min dans tryAcquire, au cas où "end" n'arrive jamais
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
    if payload.Type == "end" {
        t.release(payload.After.ID)         // ← minuscule
        return t.next.HandleEvent(payload)
    }
    if !t.tryAcquire(payload) {
        return nil
    }
    return t.next.HandleEvent(payload)
}

// release supprime un event terminé de la map interne.
func (t *Throttler) release(id string) {
    t.mu.Lock()
    defer t.mu.Unlock()
    delete(t.events, id)
}

// tryAcquire vérifie ET enregistre en une seule prise de lock.
// Le lock ne couvre que des opérations sur des maps (nanosecondes).
// L'appel HTTP se fait APRÈS, sans lock.
func (t *Throttler) tryAcquire(payload domain.FrigatePayload) bool {
	t.mu.Lock()
	defer t.mu.Unlock()

	now := time.Now()

	// Lazy cleanup : purge les entrées périmées (ceinture-bretelles)
	t.purgeExpired(now)

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

// purgeExpired supprime les entrées dont le TTL est dépassé.
// Appelé sous lock dans tryAcquire — la map events est petite
// (seulement les reviews actives), donc l'itération est négligeable.
func (t *Throttler) purgeExpired(now time.Time) {
	for id, last := range t.events {
		if now.Sub(last) > defaultTTL {
			delete(t.events, id)
		}
	}
}
