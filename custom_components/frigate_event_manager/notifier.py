"""Envoi de notifications HA pour Frigate Event Manager."""

from __future__ import annotations

import html
import logging

from homeassistant.core import HomeAssistant

from .const import PERSISTENT_NOTIFICATION
from .domain.model import FrigateEvent

_LOGGER = logging.getLogger(__name__)


class HANotifier:
    """Envoie des notifications HA (persistent_notification ou notify.xxx)."""

    def __init__(self, hass: HomeAssistant, notify_target: str) -> None:
        """Initialise avec la cible de notification."""
        self._hass = hass
        self._target = notify_target

    async def async_notify(self, event: FrigateEvent) -> None:
        """Envoie une notification pour un événement Frigate de type 'new'."""
        camera = html.escape(str(event.camera))
        objects = html.escape(", ".join(event.objects) if event.objects else "objet inconnu")
        severity = html.escape(str(event.severity))

        title = f"Frigate — {camera}"
        message = f"{objects} détecté ({severity})"

        if self._target == PERSISTENT_NOTIFICATION:
            await self._hass.services.async_call(
                "persistent_notification",
                "create",
                {
                    "title": title,
                    "message": message,
                    "notification_id": f"frigate_{camera}_{html.escape(str(event.review_id))}",
                },
            )
        else:
            # notify.mobile_app_xxx ou autre service
            parts = self._target.split(".", 1)
            if len(parts) == 2:
                domain, service = parts
                await self._hass.services.async_call(
                    domain,
                    service,
                    {"title": title, "message": message},
                )
            else:
                _LOGGER.warning("notify_target invalide : %r", self._target)
                return

        _LOGGER.debug("Notification envoyée — caméra=%s message=%r", camera, message)
