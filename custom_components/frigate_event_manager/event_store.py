"""Ring buffer d'événements Frigate en mémoire.

Conserve les N derniers événements (défaut 200) pour affichage
dans l'interface HA ou les services. Pas de persistence disque :
le buffer est reconstruit au redémarrage via les messages MQTT.
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass

from .coordinator import FrigateEvent


@dataclass
class EventRecord:
    """Instantané immuable d'un événement Frigate stocké dans le buffer."""

    camera: str
    severity: str
    objects: list[str]
    zones: list[str]
    timestamp: float
    thumb_path: str


class EventStore:
    """Ring buffer thread-safe pour les événements Frigate.

    Utilise un deque à taille fixe : le plus ancien événement est
    automatiquement évincé quand le buffer est plein.
    """

    def __init__(self, maxlen: int = 200) -> None:
        """Initialise le buffer avec une capacité maximale.

        Args:
            maxlen: Nombre maximum d'événements conservés (défaut 200).
        """
        self._store: deque[EventRecord] = deque(maxlen=maxlen)

    def add(self, event: FrigateEvent) -> None:
        """Crée un EventRecord depuis un FrigateEvent et l'ajoute au buffer.

        Utilise le start_time de l'événement comme timestamp de référence.
        Si start_time vaut 0.0 (champ absent), on replie sur l'heure courante.
        """
        timestamp = event.start_time if event.start_time > 0.0 else time.time()
        record = EventRecord(
            camera=event.camera,
            severity=event.severity,
            objects=list(event.objects),
            zones=list(event.zones),
            timestamp=timestamp,
            thumb_path=event.thumb_path,
        )
        self._store.append(record)

    def list(
        self,
        limit: int = 50,
        severity: str | None = None,
    ) -> list[EventRecord]:
        """Retourne les N derniers événements, le plus récent en premier.

        Args:
            limit:    Nombre maximum d'enregistrements retournés.
            severity: Si fourni, ne retourne que les événements de cette sévérité.
                      None = tout retourner (pas de filtre).

        Returns:
            Liste ordonnée du plus récent au plus ancien.
        """
        # Itération en ordre inverse (plus récent en tête)
        candidats = reversed(self._store)

        if severity is not None:
            candidats = (r for r in candidats if r.severity == severity)

        return list(candidats)[:limit]

    def stats(self) -> dict[str, int]:
        """Calcule des statistiques sur les événements des dernières 24h.

        Returns:
            Dictionnaire avec :
            - ``events_24h``  : nombre total d'événements sur 24h.
            - ``alerts_24h``  : nombre d'événements de sévérité "alert" sur 24h.
        """
        seuil = time.time() - 86400  # 24h en secondes

        events_24h = 0
        alerts_24h = 0

        for record in self._store:
            if record.timestamp >= seuil:
                events_24h += 1
                if record.severity == "alert":
                    alerts_24h += 1

        return {
            "events_24h": events_24h,
            "alerts_24h": alerts_24h,
        }
