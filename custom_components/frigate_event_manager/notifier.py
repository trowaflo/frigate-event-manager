"""HA notification sender for Frigate Event Manager."""

from __future__ import annotations

import html
import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers import template as template_helper

from .const import (
    DEFAULT_ACTION_BTN,
    DEFAULT_CRITICAL_SOUND,
    DEFAULT_CRITICAL_VOLUME,
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

# Stub values used when a template is rendered without a real event (e.g. config flow preview).
# Real event variables always override these.
_TEMPLATE_STUB: dict = {
    "camera": "<camera>",
    "camera_name": "<camera>",
    "label": "<label>",
    "objects": ["<object>"],
    "zones": [],
    "severity": "<severity>",
    "score": 0.0,
    "start_time": 0.0,
    "review_id": "<review_id>",
    "clip_url": "",
    "snapshot_url": "",
    "preview_url": "",
    "thumbnail_url": "",
}

# Action button config: title, SF Symbols icon, destructive (red)
_ACTION_BTN_CONFIG: dict[str, dict] = {
    "clip":        {"title": "Clip",          "icon": "sfsymbols:video"},
    "snapshot":    {"title": "Snapshot",      "icon": "sfsymbols:camera"},
    "preview":     {"title": "Preview",       "icon": "sfsymbols:play.circle"},
    "silent_30min":{"title": "Silence 30 min","icon": "sfsymbols:speaker.zzz", "destructive": True},
    "silent_1h":   {"title": "Silence 1h",    "icon": "sfsymbols:speaker.zzz", "destructive": True},
    "dismiss":     {"title": "Ignorer",       "icon": "sfsymbols:xmark.circle"},
}


class HANotifier:
    """Send HA notifications (persistent_notification or notify.xxx)."""

    def __init__(
        self,
        hass: HomeAssistant,
        notify_target: str,
        title_tpl: str | None = None,
        message_tpl: str | None = None,
        signer: MediaSignerPort | None = None,
        frigate_url: str | None = None,
        tap_action: str = DEFAULT_TAP_ACTION,
        critical_sound: str = DEFAULT_CRITICAL_SOUND,
        critical_volume: float = DEFAULT_CRITICAL_VOLUME,
    ) -> None:
        """Initialize with the target, optional templates and media signer."""
        self._hass = hass
        self._target = notify_target
        self._title_tpl = title_tpl or DEFAULT_NOTIF_TITLE
        self._message_tpl = message_tpl or DEFAULT_NOTIF_MESSAGE
        self._signer = signer
        self._frigate_url = frigate_url.rstrip("/") if frigate_url else None
        self._tap_action = tap_action
        self._critical_sound = critical_sound
        self._critical_volume = critical_volume
        # Action button configuration (none = no button)
        self._action_btns: list[str] = [DEFAULT_ACTION_BTN, DEFAULT_ACTION_BTN, DEFAULT_ACTION_BTN]

    # --- Live setters (called by text/select entities) ---

    def set_title_template(self, tpl: str | None) -> None:
        """Update the title template live."""
        self._title_tpl = tpl or DEFAULT_NOTIF_TITLE

    def set_message_template(self, tpl: str | None) -> None:
        """Update the message template live."""
        self._message_tpl = tpl or DEFAULT_NOTIF_MESSAGE

    def set_tap_action(self, tap_action: str) -> None:
        """Update the tap action live."""
        self._tap_action = tap_action

    def set_action_buttons(self, btn1: str, btn2: str, btn3: str) -> None:
        """Update the 3 notification action buttons live."""
        self._action_btns = [btn1, btn2, btn3]

    def _render(self, tpl_str: str, variables: dict) -> str:
        """Render a HA Jinja2 template with the event variables.

        Known variables missing from the context (e.g. during a preview without a
        real event) are replaced by stub placeholders such as ``<camera>`` so the
        template renders gracefully instead of raising an UndefinedError.
        Real values always take precedence over stubs.
        """
        try:
            return str(
                template_helper.Template(tpl_str, self._hass).async_render(
                    {**_TEMPLATE_STUB, **variables}, parse_result=False
                )
            )
        except Exception:  # noqa: BLE001
            _LOGGER.warning("template render error %r — using raw value", tpl_str)
            return tpl_str

    def _build_media_urls(self, event: FrigateEvent) -> dict[str, str]:
        """Build media URLs — presigned if signer available, direct otherwise."""
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

    def _build_actions_from_btns(
        self, media_urls: dict[str, str], camera: str
    ) -> list[dict] | None:
        """Build the Companion actions list from the _action_btns config.

        Returns None if all buttons are 'none' (auto-generation behavior).
        """
        if all(v == DEFAULT_ACTION_BTN for v in self._action_btns):
            return None

        actions: list[dict] = []
        for btn_value in self._action_btns:
            if btn_value == DEFAULT_ACTION_BTN:
                continue
            cfg = _ACTION_BTN_CONFIG.get(btn_value, {})
            title = cfg.get("title", btn_value)
            icon = cfg.get("icon")
            destructive = cfg.get("destructive", False)

            if btn_value == "clip" and media_urls.get("clip_url"):
                btn = {"action": "URI", "title": title, "uri": media_urls["clip_url"]}
            elif btn_value == "snapshot" and media_urls.get("snapshot_url"):
                btn = {"action": "URI", "title": title, "uri": media_urls["snapshot_url"]}
            elif btn_value == "preview" and media_urls.get("preview_url"):
                btn = {"action": "URI", "title": title, "uri": media_urls["preview_url"]}
            elif btn_value == "silent_30min":
                btn = {"action": f"fem_silent_30min_{camera}", "title": title}
            elif btn_value == "silent_1h":
                btn = {"action": f"fem_silent_1h_{camera}", "title": title}
            elif btn_value == "dismiss":
                btn = {"action": "DISMISS_NOTIFICATION", "title": title}
            else:
                continue

            if icon:
                btn["icon"] = icon
            if destructive:
                btn["destructive"] = True
            actions.append(btn)
        return actions

    async def async_notify(self, event: FrigateEvent, *, critical: bool = False) -> None:
        """Send a notification for a Frigate event of type 'new' or 'update'."""
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
            "start_time": event.start_time,
            "review_id": html.escape(event.review_id),
            **media_urls,
        }

        title = self._render(self._title_tpl, variables)
        message = self._render(self._message_tpl, variables)
        notification_id = f"frigate_{event.camera}_{event.review_id}"

        if self._target == PERSISTENT_NOTIFICATION:
            # persistent_notification: markdown links in message, no enriched data
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
            # HA Companion: enriched data (image, tap, buttons, group)
            companion_data: dict[str, Any] = {"tag": notification_id}

            # iOS group — groups notifications by camera
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

            # Critical notification (iOS critical alert + Android high-priority channel)
            if critical:
                companion_data["push"] = {
                    "sound": {"name": self._critical_sound, "critical": 1, "volume": self._critical_volume}
                }
                companion_data["channel"] = "frigate_critical"

            # Action buttons — use _action_btns if configured, otherwise auto-generate
            configured_actions = self._build_actions_from_btns(media_urls, event.camera)
            if configured_actions is not None:
                # Buttons configured via select entities — list may be empty (URI buttons without URL)
                if configured_actions:
                    companion_data["actions"] = configured_actions
            else:
                # All buttons set to "none" — show only the silence button
                companion_data["actions"] = [{
                    "action": f"fem_silent_30min_{event.camera}",
                    "title": "Silence 30 min",
                    "icon": "sfsymbols:speaker.zzz",
                    "destructive": True,
                }]

            parts = self._target.split(".", 1)
            if len(parts) == 2:
                domain, service = parts
                await self._hass.services.async_call(
                    domain,
                    service,
                    {"title": title, "message": message, "data": companion_data},
                )
            else:
                _LOGGER.warning("invalid notify_target: %r", self._target)
                return

        _LOGGER.debug("notification sent — camera=%s message=%r", event.camera, message)
