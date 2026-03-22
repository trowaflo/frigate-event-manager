"""MQTT DataUpdateCoordinator for Frigate Event Manager — push-only."""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import replace
from typing import Any

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import template as template_helper
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    ACTION_BTN_OPTIONS,
    CONF_ACTION_BTN1,
    CONF_ACTION_BTN2,
    CONF_ACTION_BTN3,
    CONF_CAMERA,
    CONF_COOLDOWN,
    CONF_CRITICAL_TEMPLATE,
    CONF_DEBOUNCE,
    CONF_DISABLED_HOURS,
    CONF_LABELS,
    CONF_SEVERITY,
    CONF_ZONES,
    DEFAULT_ACTION_BTN,
    DEFAULT_DEBOUNCE,
    DEFAULT_MQTT_TOPIC,
    DEFAULT_SEVERITY,
    DEFAULT_THROTTLE_COOLDOWN,
    DOMAIN,
    EVENT_MOBILE_APP_NOTIFICATION_ACTION,
)
from .domain.filter import FilterChain, LabelFilter, SeverityFilter, TimeFilter, ZoneFilter
from .domain.model import CameraState, _parse_event
from .domain.ports import EventSourcePort, NotifierPort
from .domain.throttle import Throttler

_LOGGER = logging.getLogger(__name__)


class FrigateEventManagerCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """MQTT Coordinator — push-only, per camera (subentry)."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        subentry: ConfigSubentry,
        *,
        notifier: NotifierPort | None = None,
        event_source: EventSourcePort,
    ) -> None:
        """Initialize the coordinator for a given camera.

        event_source must be injected: HaMqttAdapter in production, fake in tests.
        """
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{subentry.data[CONF_CAMERA]}",
            update_interval=None,
            config_entry=entry,
        )
        self._camera: str = subentry.data[CONF_CAMERA]
        self._camera_state = CameraState(name=self._camera)
        self._unsubscribe_mqtt: Any = None
        self._notifier: NotifierPort | None = notifier
        self._event_source: EventSourcePort = event_source
        self._throttler = Throttler(
            cooldown=subentry.data.get(CONF_COOLDOWN, DEFAULT_THROTTLE_COOLDOWN)
        )
        # Store filter parameters for hot-rebuild
        self._zones: list[str] = subentry.data.get(CONF_ZONES, [])
        self._labels: list[str] = subentry.data.get(CONF_LABELS, [])
        self._disabled_hours: list[int] = subentry.data.get(CONF_DISABLED_HOURS, [])
        self._severities: list[str] = subentry.data.get(CONF_SEVERITY, DEFAULT_SEVERITY)
        self._filter_chain = self._build_filter_chain()

        # Debounce
        self._debounce_seconds: int = subentry.data.get(CONF_DEBOUNCE, DEFAULT_DEBOUNCE)
        self._debounce_task: asyncio.Task | None = None
        self._pending_objects: set[str] = set()
        self._pending_event: Any = None  # last received FrigateEvent

        # Active reviews tracker — prevents premature motion=False on multi-events
        self._active_reviews: set[str] = set()

        # Critical template
        self._critical_template: str | None = subentry.data.get(CONF_CRITICAL_TEMPLATE) or None

        # Silent mode
        self._silent_until: float = 0.0
        self._cancel_silent: Any = None
        # Persist silent mode via HA Store — survives restarts
        self._store: Store = Store(
            hass,
            1,
            f"frigate_event_manager_{self._camera}",
        )

        # Notification action buttons (configurable via select entities)
        self._action_btn1: str = subentry.data.get(CONF_ACTION_BTN1, DEFAULT_ACTION_BTN)
        self._action_btn2: str = subentry.data.get(CONF_ACTION_BTN2, DEFAULT_ACTION_BTN)
        self._action_btn3: str = subentry.data.get(CONF_ACTION_BTN3, DEFAULT_ACTION_BTN)

        # Unsubscribe handle for mobile_app_notification_action listener
        self._unsubscribe_notif_action: Any = None

    @property
    def camera(self) -> str:
        """Camera name managed by this coordinator."""
        return self._camera

    @property
    def camera_state(self) -> CameraState:
        """Direct access to CameraState."""
        return self._camera_state

    @property
    def silent_until(self) -> float:
        """End timestamp of silent mode (0.0 if inactive)."""
        return self._silent_until

    def set_camera_enabled(self, enabled: bool) -> None:
        """Enable or disable notifications for this camera."""
        self._camera_state.enabled = enabled
        self.async_set_updated_data(self._camera_state.as_dict())

    # --- Setters kept for test compatibility ---

    def set_cooldown(self, seconds: int) -> None:
        """Update the anti-spam cooldown live."""
        self._throttler = Throttler(cooldown=seconds)

    def set_debounce(self, seconds: int) -> None:
        """Update the debounce window live."""
        self._debounce_seconds = seconds

    def set_severity(self, severities: list[str]) -> None:
        """Update the severity filter live."""
        self._severities = severities
        self._filter_chain = self._build_filter_chain()

    def set_tap_action(self, tap_action: str) -> None:
        """Update the tap action live (delegates to notifier)."""
        if self._notifier is not None and hasattr(self._notifier, "set_tap_action"):
            self._notifier.set_tap_action(tap_action)  # type: ignore[union-attr]

    def set_notif_title(self, tpl: str | None) -> None:
        """Update the title template live (delegates to notifier)."""
        if self._notifier is not None and hasattr(self._notifier, "set_title_template"):
            self._notifier.set_title_template(tpl)  # type: ignore[union-attr]

    def set_notif_message(self, tpl: str | None) -> None:
        """Update the message template live (delegates to notifier)."""
        if self._notifier is not None and hasattr(self._notifier, "set_message_template"):
            self._notifier.set_message_template(tpl)  # type: ignore[union-attr]

    def set_critical_template(self, tpl: str | None) -> None:
        """Update the critical template live."""
        self._critical_template = tpl or None

    def set_action_btn1(self, value: str) -> None:
        """Update action button #1 live."""
        self._action_btn1 = value if value in ACTION_BTN_OPTIONS else DEFAULT_ACTION_BTN
        self._sync_action_btns_to_notifier()

    def set_action_btn2(self, value: str) -> None:
        """Update action button #2 live."""
        self._action_btn2 = value if value in ACTION_BTN_OPTIONS else DEFAULT_ACTION_BTN
        self._sync_action_btns_to_notifier()

    def set_action_btn3(self, value: str) -> None:
        """Update action button #3 live."""
        self._action_btn3 = value if value in ACTION_BTN_OPTIONS else DEFAULT_ACTION_BTN
        self._sync_action_btns_to_notifier()

    def _sync_action_btns_to_notifier(self) -> None:
        """Propagate the 3 action buttons to the notifier."""
        if self._notifier is not None and hasattr(self._notifier, "set_action_buttons"):
            self._notifier.set_action_buttons(  # type: ignore[union-attr]
                self._action_btn1, self._action_btn2, self._action_btn3
            )

    @callback
    def _handle_notification_action(self, event: Any) -> None:
        """Handle mobile_app_notification_action events — activates silent mode."""
        action = event.data.get("action", "")
        if action == f"fem_silent_30min_{self._camera}":
            _LOGGER.debug("silent 30min action received — camera=%s", self._camera)
            self.activate_silent_mode(duration_min=30)
        elif action == f"fem_silent_1h_{self._camera}":
            _LOGGER.debug("silent 1h action received — camera=%s", self._camera)
            self.activate_silent_mode(duration_min=60)

    def _build_filter_chain(self) -> FilterChain:
        """Rebuild the FilterChain from stored attributes."""
        return FilterChain([
            ZoneFilter(self._zones),
            LabelFilter(self._labels),
            TimeFilter(self._disabled_hours),
            SeverityFilter(self._severities),
        ])

    def _is_critical(self, event: Any) -> bool:
        """Evaluate the critical template — returns True if the notification should be critical."""
        if not self._critical_template:
            return False
        variables = {
            "camera": event.camera,
            "severity": event.severity,
            "objects": event.objects,
            "zones": event.zones,
            "start_time": event.start_time,
        }
        try:
            result = template_helper.Template(
                self._critical_template, self.hass
            ).async_render(variables, parse_result=False)
            return str(result).strip().lower() == "true"
        except Exception:  # noqa: BLE001
            _LOGGER.warning(
                "critical_template evaluation error — camera=%s template=%r",
                self._camera,
                self._critical_template,
            )
            return False

    def _on_silent_expired(self, _: Any) -> None:
        """Reset silent mode after timer expiration."""
        self._silent_until = 0.0
        self._cancel_silent = None
        self.hass.async_create_task(self._store.async_save({"silent_until": 0.0}))
        self.async_set_updated_data(self._camera_state.as_dict())

    def activate_silent_mode(self, *, duration_min: int | None = None) -> None:
        """Activate silent mode for the configured duration (or duration_min if provided)."""
        if self._cancel_silent is not None:
            self._cancel_silent()
        effective_duration = duration_min if duration_min is not None else 30
        self._silent_until = time.time() + effective_duration * 60

        self._cancel_silent = async_call_later(
            self.hass,
            effective_duration * 60,
            self._on_silent_expired,
        )
        # Persist the value to survive an HA restart
        self.hass.async_create_task(
            self._store.async_save({"silent_until": self._silent_until})
        )
        self.async_set_updated_data(self._camera_state.as_dict())
        _LOGGER.info(
            "silent mode activated — camera=%s duration=%d min",
            self._camera,
            effective_duration,
        )

    async def async_start(self) -> None:
        """Subscribe to the Frigate MQTT topic via the injected adapter."""
        self._unsubscribe_mqtt = await self._event_source.async_subscribe(
            DEFAULT_MQTT_TOPIC,
            self._handle_mqtt_message,
        )
        _LOGGER.info("MQTT subscribed — camera=%s topic=%s", self._camera, DEFAULT_MQTT_TOPIC)

        # Listen for mobile notification actions (silent_30min / silent_1h)
        self._unsubscribe_notif_action = self.hass.bus.async_listen(
            EVENT_MOBILE_APP_NOTIFICATION_ACTION,
            self._handle_notification_action,
        )

        # Initial sync of action buttons with the notifier
        self._sync_action_btns_to_notifier()

        # Restore silent mode from Store if still active
        stored = await self._store.async_load() or {}
        silent_until = float(stored.get("silent_until", 0.0))
        if silent_until > time.time():
            self._silent_until = silent_until
            remaining = silent_until - time.time()
            _LOGGER.info(
                "silent mode restored — camera=%s remaining=%.0fs",
                self._camera,
                remaining,
            )

            self._cancel_silent = async_call_later(
                self.hass,
                remaining,
                self._on_silent_expired,
            )

    async def async_cancel_silent(self) -> None:
        """Cancel the active silent mode immediately."""
        if self._cancel_silent is not None:
            self._cancel_silent()
            self._cancel_silent = None
        self._silent_until = 0.0
        self.hass.async_create_task(
            self._store.async_save({"silent_until": 0.0})
        )
        self.async_set_updated_data(self._camera_state.as_dict())
        _LOGGER.info("silent mode cancelled — camera=%s", self._camera)

    async def async_remove_store(self) -> None:
        """Remove the persistent store associated with this camera."""
        await self._store.async_remove()

    async def async_stop(self) -> None:
        """Unsubscribe from MQTT and the notification action listener."""
        if self._debounce_task is not None:
            self._debounce_task.cancel()
            self._debounce_task = None
        if self._cancel_silent is not None:
            self._cancel_silent()
            self._cancel_silent = None
        if self._unsubscribe_notif_action is not None:
            self._unsubscribe_notif_action()
            self._unsubscribe_notif_action = None
        if self._unsubscribe_mqtt is not None:
            self._unsubscribe_mqtt()
            self._unsubscribe_mqtt = None
            _LOGGER.debug("MQTT unsubscribed — camera=%s", self._camera)

    @callback
    def _handle_mqtt_message(self, message: Any) -> None:
        """MQTT callback — parse, filter by camera, update state, notify."""
        event = _parse_event(message.payload)
        if event is None:
            _LOGGER.debug("MQTT payload ignored — not parseable (camera=%s)", self._camera)
            return
        if event.camera != self._camera:
            return

        state = self._camera_state

        if event.type in ("new", "update"):
            state.last_severity = event.severity
            state.last_objects = event.objects
            state.last_event_time = event.start_time
            if event.type == "new":
                if event.review_id:
                    self._active_reviews.add(event.review_id)
                state.motion = True
        elif event.type == "end":
            if event.review_id:
                self._active_reviews.discard(event.review_id)
            # motion stays True if other reviews are still active
            state.motion = len(self._active_reviews) > 0
            state.last_event_time = event.end_time or event.start_time

        _LOGGER.debug(
            "event processed — camera=%s type=%s severity=%s objects=%s",
            event.camera, event.type, event.severity, event.objects,
        )

        if event.type in ("new", "update"):
            if (
                state.enabled
                and self._notifier is not None
                and self._filter_chain.apply(event)
                and self._throttler.should_notify(self._camera)
                and time.time() > self._silent_until
            ):
                if self._debounce_seconds == 0:
                    # Immediate send — record() after await to avoid cooldown on failure
                    async def _notify_and_record(evt: Any, crit: bool) -> None:
                        await self._notifier.async_notify(evt, critical=crit)
                        self._throttler.record(self._camera)

                    self.hass.async_create_task(
                        _notify_and_record(event, self._is_critical(event))
                    )
                else:
                    # Accumulate for debounce
                    self._pending_objects.update(event.objects)
                    self._pending_event = event
                    if self._debounce_task is not None:
                        self._debounce_task.cancel()
                    self._debounce_task = self.hass.async_create_task(
                        self._debounce_send()
                    )
        elif event.type == "end":
            # Cancel debounce + release cooldown at end of event
            if self._debounce_task is not None:
                self._debounce_task.cancel()
                self._debounce_task = None
            self._pending_objects.clear()
            self._pending_event = None
            self._throttler.release(self._camera)

        self.async_set_updated_data(state.as_dict())

    async def _debounce_send(self) -> None:
        """Send the grouped notification after the debounce window."""
        try:
            await asyncio.sleep(self._debounce_seconds)
        except asyncio.CancelledError:
            return

        if self._pending_event is None or self._notifier is None:
            return

        # Synthetic event with all accumulated objects
        grouped_event = replace(
            self._pending_event,
            objects=list(self._pending_objects),
        )
        # _is_critical is evaluated on grouped_event whose severity is that of the last
        # update received (not necessarily the highest) — intentional behavior,
        # consistent with the debounce logic that retains the last known camera state.
        await self._notifier.async_notify(grouped_event, critical=self._is_critical(grouped_event))
        self._throttler.record(self._camera)

        # Reset
        self._pending_objects.clear()
        self._pending_event = None
        self._debounce_task = None

    async def _async_update_data(self) -> dict[str, Any]:
        """Not used — coordinator in push-only MQTT mode."""
        return self.data or {}
