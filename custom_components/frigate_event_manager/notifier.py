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
    DEFAULT_TAP_ACTION,
    PERSISTENT_NOTIFICATION,
    TAP_ACTION_CLIP,
    TAP_ACTION_PREVIEW,
    TAP_ACTION_SNAPSHOT,
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
        tap_action: str = DEFAULT_TAP_ACTION,
    ) -> None:
        """Initialise avec la cible, les templates optionnels et le signer media."""
        self._hass = hass
        self._target = notify_target
        self._title_tpl = title_tpl or DEFAULT_NOTIF_TITLE
        self._message_tpl = message_tpl or DEFAULT_NOTIF_MESSAGE
        self._signer = signer
        self._frigate_url = frigate_url.rstrip("/") if frigate_url else None
        self._tap_action = tap_action

    # --- Setters live (appelés par les entités text/select) ---

    def set_title_template(self, tpl: str | None) -> None:
        """Met à jour le template de titre à chaud."""
        self._title_tpl = tpl or DEFAULT_NOTIF_TITLE

    def set_message_template(self, tpl: str | None) -> None:
        """Met à jour le template de message à chaud."""
        self._message_tpl = tpl or DEFAULT_NOTIF_MESSAGE

    def set_tap_action(self, tap_action: str) -> None:
        """Met à jour l'action au tap à chaud."""
        self._tap_action = tap_action

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

    async def async_notify(self, event: FrigateEvent, *, critical: bool = False) -> None:
        """Envoie une notification pour un événement Frigate de type 'new' ou 'update'."""
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

        if self._target == PERSISTENT_NOTIFICATION:
            # persistent_notification : liens markdown dans le message, pas de data enrichie
            if any(media_urls.get(k) for k in ("clip_url", "snapshot_url", "preview_url")):
                links = []
                if media_urls.get("clip_url"):
                    links.append(f"[Clip](<{media_urls['clip_url']}>)")
                if media_urls.get("snapshot_url"):
                    links.append(f"[Snapshot](<{media_urls['snapshot_url']}>)")
                if media_urls.get("preview_url"):
                    links.append(f"[Preview](<{media_urls['preview_url']}>)")
                message += "\n" + " · ".join(links)

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
            # HA Companion : données enrichies (image, tap, boutons, group)
            companion_data: dict[str, Any] = {"tag": notification_id}

            # Group iOS — regroupe les notifications par caméra
            companion_data["group"] = f"frigate-{html.escape(event.camera)}"

            if media_urls["snapshot_url"]:
                companion_data["image"] = media_urls["snapshot_url"]

            tap_url = {
                TAP_ACTION_CLIP: media_urls["clip_url"],
                TAP_ACTION_SNAPSHOT: media_urls["snapshot_url"],
                TAP_ACTION_PREVIEW: media_urls["preview_url"],
            }.get(self._tap_action, media_urls["clip_url"])
            if tap_url:
                companion_data["url"] = tap_url          # iOS
                companion_data["clickAction"] = tap_url  # Android

            # Notification critique (iOS critical alert + Android channel haute priorité)
            if critical:
                companion_data["push"] = {
                    "sound": {"name": "default", "critical": 1, "volume": 1.0}
                }
                companion_data["channel"] = "frigate_critical"

            # Boutons d'action — uniquement les URLs disponibles
            actions = []
            if media_urls["clip_url"]:
                actions.append({"action": "URI", "title": "Clip", "uri": media_urls["clip_url"]})
            if media_urls["snapshot_url"]:
                actions.append({"action": "URI", "title": "Snapshot", "uri": media_urls["snapshot_url"]})
            if media_urls["preview_url"]:
                actions.append({"action": "URI", "title": "Preview", "uri": media_urls["preview_url"]})
            if actions:
                companion_data["actions"] = actions

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
