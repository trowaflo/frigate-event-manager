"""Ports sortants du domaine — interfaces abstraites, zéro dépendance HA."""

from __future__ import annotations

from typing import Protocol

from .model import FrigateEvent


class NotifierPort(Protocol):
    """Port sortant — contrat que tout adaptateur de notification doit respecter."""

    async def async_notify(self, event: FrigateEvent) -> None:
        """Envoie une notification pour un événement Frigate."""
        ...
