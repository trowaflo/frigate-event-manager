"""Envoi de notifications HA pour Frigate Event Manager."""

from __future__ import annotations

import html
import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers import template as template_helper

from .const import (
    DEFAULT_NOTIF_MESSAGE,
    DEFAULT_NOTIF_TITLE,
    PERSISTENT_NOTIFICATION,
)
from .domain.model import FrigateEvent

_LOGGER = logging.getLogger(__name__)


class HANotifier:
    """Envoie des notifications HA (persistent_notification ou notify.xxx)."""

    def __init__(
        self,
        hass: HomeAssistant,
        notify_target: str,
        title_tpl: str | None = None,
        message_tpl: str | None = None,
    ) -> None:
        """Initialise avec la cible et les templates optionnels."""
        self._hass = hass
        self._target = notify_target
        self._title_tpl = title_tpl or DEFAULT_NOTIF_TITLE
        self._message_tpl = message_tpl or DEFAULT_NOTIF_MESSAGE

    def _render(self, tpl_str: str, variables: dict) -> str:
        """Rend un template Jinja2 HA avec les variables de l'événement."""
        try:
            return str(
                template_helper.Template(tpl_str, self._hass).async_render(
                    variables, parse_result=False
                )
            )
        except Exception:  # noqa: BLE001
            _LOGGER.warning("Erreur rendu template %r — utilisation brute", tpl_str)
            return tpl_str

    async def async_notify(self, event: FrigateEvent) -> None:
        """Envoie une notification pour un événement Frigate de type 'new'."""
        # Escaper les valeurs string pour prévenir l'injection dans les notifications
        variables = {
            "camera": html.escape(event.camera),
            "objects": [html.escape(o) for o in event.objects],
            "zones": [html.escape(z) for z in event.zones],
            "severity": html.escape(event.severity),
            "score": event.score,
            "review_id": html.escape(event.review_id),
        }

        title = self._render(self._title_tpl, variables)
        message = self._render(self._message_tpl, variables)
        notification_id = f"frigate_{event.camera}_{event.review_id}"

        if self._target == PERSISTENT_NOTIFICATION:
            await self._hass.services.async_call(
                "persistent_notification",
                "create",
                {
                    "title": title,
                    "message": message,
                    "notification_id": notification_id,
                },
            )
        else:
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

        _LOGGER.debug("Notification envoyée — caméra=%s message=%r", event.camera, message)
