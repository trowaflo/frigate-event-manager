"""Anti-spam par caméra — Throttler à cooldown configurable.

Sépare la décision (should_notify) de l'enregistrement (record)
pour permettre une utilisation sans effet de bord involontaire.

Utilisation typique :
    if throttler.should_notify(camera):
        await notifier.notify(...)
        throttler.record(camera)
"""

from __future__ import annotations

import time
from collections.abc import Callable


class Throttler:
    """Contrôle l'anti-spam par caméra via un cooldown configurable.

    Le Throttler maintient en mémoire le timestamp de la dernière
    notification envoyée pour chaque caméra. La méthode should_notify()
    est en lecture seule : elle n'altère pas l'état. C'est record() qui
    consigne la notification.
    """

    def __init__(
        self,
        cooldown: int = 60,
        clock: Callable[[], float] = time.time,
    ) -> None:
        """Initialise le Throttler.

        Args:
            cooldown: Durée minimale en secondes entre deux notifications
                      pour une même caméra (défaut : 60 s).
            clock:    Fonction retournant le temps courant en secondes
                      depuis l'epoch. Injectable pour les tests.
        """
        self._cooldown = cooldown
        self._clock = clock
        # Dictionnaire camera_name → timestamp dernière notification
        self._last_notified: dict[str, float] = {}

    def should_notify(self, camera: str, now: float | None = None) -> bool:
        """Indique si une notification peut être envoyée pour cette caméra.

        Retourne True si aucune notification n'a encore été enregistrée
        pour cette caméra, ou si le cooldown est écoulé depuis la dernière.

        Cette méthode est en lecture seule : elle ne modifie pas l'état.

        Args:
            camera: Nom de la caméra à vérifier.
            now:    Instant courant en secondes depuis l'epoch.
                    Si None, utilise self._clock().

        Returns:
            True si la notification est autorisée, False si le cooldown
            n'est pas encore écoulé.
        """
        instant = now if now is not None else self._clock()
        derniere = self._last_notified.get(camera)

        # Première notification pour cette caméra : toujours autorisée
        if derniere is None:
            return True

        return (instant - derniere) >= self._cooldown

    def record(self, camera: str, now: float | None = None) -> None:
        """Enregistre le timestamp de la dernière notification pour une caméra.

        À appeler après avoir effectivement envoyé la notification.

        Args:
            camera: Nom de la caméra dont on enregistre la notification.
            now:    Instant courant en secondes depuis l'epoch.
                    Si None, utilise self._clock().
        """
        instant = now if now is not None else self._clock()
        self._last_notified[camera] = instant
