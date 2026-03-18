"""Ports du domaine — interfaces abstraites, zéro dépendance HA."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol

from .model import FrigateEvent


class NotifierPort(Protocol):
    """Port sortant — contrat que tout adaptateur de notification doit respecter."""

    async def async_notify(self, event: FrigateEvent) -> None:
        """Envoie une notification pour un événement Frigate."""
        ...


class EventSourcePort(Protocol):
    """Port entrant — source d'événements MQTT à écouter."""

    async def async_subscribe(
        self,
        topic: str,
        callback: Callable[[Any], None],
    ) -> Callable[[], None]:
        """Souscrit au topic. Retourne la fonction de désabonnement."""
        ...


class FrigatePort(Protocol):
    """Port sortant — accès à l'API REST Frigate."""

    async def get_cameras(self) -> list[str]:
        """Retourne la liste des noms de caméras."""
        ...


class MediaSignerPort(Protocol):
    """Port — signature et vérification de presigned URLs médias."""

    def sign_url(self, path: str) -> str:
        """Signe un path et retourne l'URL complète avec ?exp=...&sig=..."""
        ...

    def verify(self, path: str, exp_str: str, sig: str) -> bool:
        """Vérifie qu'une presigned URL est valide et non expirée."""
        ...
