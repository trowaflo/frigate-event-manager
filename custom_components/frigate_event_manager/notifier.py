"""Envoi de notifications HA pour Frigate Event Manager."""

from __future__ import annotations

import html
import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers import template as template_helper

from .const import (
    DEFAULT_NOTIF_MESSAGE,
    DEFAULT_NOTIF_TITLE,
    PERSISTENT_NOTIFICATION,
)
from .domain.model import FrigateEvent
from .domain.ports import MediaSignerPort

_LOGGER = logging.getLogger(__name__)


class HANotifier:
    """Envoie des notifications HA (persistent_notification ou notify.xxx)."""

    def __init__(
        self,
        hass: HomeAssistant,
        notify_target: str,
        title_tpl: str | None = None,
        message_tpl: str | None = None,
        signer: MediaSignerPort | None = None,
        frigate_url: str | None = None,
    ) -> None:
        """Initialise avec la cible, les templates optionnels et le signer media."""
        self._hass = hass
        self._target = notify_target
        self._title_tpl = title_tpl or DEFAULT_NOTIF_TITLE
        self._message_tpl = message_tpl or DEFAULT_NOTIF_MESSAGE
        self._signer = signer
        self._frigate_url = frigate_url.rstrip("/") if frigate_url else None

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

    def _build_media_urls(self, event: FrigateEvent) -> dict[str, str]:
        """Construit les URLs médias — presignées si signer disponible, directes sinon."""
        preview_url = snapshot_url = clip_url = thumbnail_url = ""

        if not event.review_id:
            return {
                "preview_url": preview_url,
                "snapshot_url": snapshot_url,
                "clip_url": clip_url,
                "thumbnail_url": thumbnail_url,
            }

        if self._signer:
            preview_url = self._signer.sign_url(f"/api/review/{event.review_id}/preview")
            if event.detections:
                det_id = event.detections[0]
                snapshot_url = self._signer.sign_url(f"/api/events/{det_id}/snapshot.jpg")
                clip_url = self._signer.sign_url(f"/api/events/{det_id}/clip.mp4")
                thumbnail_url = self._signer.sign_url(f"/api/events/{det_id}/thumbnail.jpg")
        elif self._frigate_url:
            base = self._frigate_url
            preview_url = f"{base}/api/review/{event.review_id}/preview"
            if event.detections:
                det_id = event.detections[0]
                snapshot_url = f"{base}/api/events/{det_id}/snapshot.jpg"
                clip_url = f"{base}/api/events/{det_id}/clip.mp4"
                thumbnail_url = f"{base}/api/events/{det_id}/thumbnail.jpg"

        return {
            "preview_url": preview_url,
            "snapshot_url": snapshot_url,
            "clip_url": clip_url,
            "thumbnail_url": thumbnail_url,
        }

    async def async_notify(self, event: FrigateEvent) -> None:
        """Envoie une notification pour un événement Frigate de type 'new'."""
        escaped_objects = [html.escape(o) for o in event.objects]
        media_urls = self._build_media_urls(event)

        variables = {
            "camera": html.escape(event.camera),
            "camera_name": html.escape(event.camera),
            "objects": escaped_objects,
            "label": escaped_objects[0] if escaped_objects else "",
            "zones": [html.escape(z) for z in event.zones],
            "severity": html.escape(event.severity),
            "score": event.score,
            "review_id": html.escape(event.review_id),
            **media_urls,
        }

        title = self._render(self._title_tpl, variables)
        message = self._render(self._message_tpl, variables)
        notification_id = f"frigate_{event.camera}_{event.review_id}"

        # Données enrichies pour HA Companion (image preview + lien au tap)
        companion_data: dict[str, Any] = {"tag": notification_id}
        if media_urls["snapshot_url"]:
            companion_data["image"] = media_urls["snapshot_url"]
        if media_urls["clip_url"] or media_urls["preview_url"]:
            companion_data["clickAction"] = media_urls["clip_url"] or media_urls["preview_url"]

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
                    {"title": title, "message": message, "data": companion_data},
                )
            else:
                _LOGGER.warning("notify_target invalide : %r", self._target)
                return

        _LOGGER.debug("Notification envoyée — caméra=%s message=%r", event.camera, message)
