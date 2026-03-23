<!-- markdownlint-disable first-line-heading MD033 -->

<img src="https://raw.githubusercontent.com/trowaflo/frigate-event-manager/main/icon.png"
     alt="Frigate Event Manager icon"
     width="20%"
     align="right"
     style="float: right; margin: 10px 0px 20px 20px;" />

[![Release](https://img.shields.io/github/v/release/trowaflo/frigate-event-manager)](https://github.com/trowaflo/frigate-event-manager/releases)
[![Build](https://github.com/trowaflo/frigate-event-manager/actions/workflows/validation.yml/badge.svg)](https://github.com/trowaflo/frigate-event-manager/actions/workflows/validation.yml)
[![Coverage](https://codecov.io/gh/trowaflo/frigate-event-manager/branch/main/graph/badge.svg)](https://codecov.io/gh/trowaflo/frigate-event-manager)
[![HACS](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://hacs.xyz)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://github.com/trowaflo/frigate-event-manager/blob/main/LICENSE)

# Frigate Event Manager

Home Assistant integration that listens to [Frigate NVR](https://frigate.video) events via MQTT,
applies configurable filters, and sends rich notifications to the HA Companion app.

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=trowaflo&repository=frigate-event-manager&category=integration)

## Features

- **Per-camera configuration** — each camera is an independent config entry with its own filters, throttle and notification settings
- **Smart filtering** — filter by zone, object label, time of day and severity (`alert` / `detection`)
- **Anti-spam** — configurable cooldown (per camera) and debounce to group rapid detections
- **Rich notifications** — snapshot, clip and preview URLs (presigned HMAC-SHA256), action buttons, iOS critical alerts
- **Silent mode** — mute a camera for a configurable duration directly from the notification
- **Jinja2 templates** — fully customisable title, message and critical condition

## Prerequisites

- Home Assistant 2024.11+
- [Frigate NVR](https://frigate.video) with MQTT enabled
- MQTT broker integrated in Home Assistant (`Settings > Devices & Services > MQTT`)
- [HA Companion app](https://companion.home-assistant.io/) for mobile notifications (optional — `persistent_notification` is also supported)

## Installation

### Via HACS (recommended)

1. Click the button above, or open HACS → Integrations → ⋮ → Custom repositories
2. Add `https://github.com/trowaflo/frigate-event-manager` — type **Integration**
3. Install **Frigate Event Manager**
4. Restart Home Assistant

### Manual

Copy `custom_components/frigate_event_manager/` to your `<config>/custom_components/` directory and restart.

## Configuration

Go to **Settings → Devices & Services → Add integration → Frigate Event Manager**.

The setup wizard has 5 steps:

| Step | What you configure |
| --- | --- |
| **Connection** | Frigate URL, notification target (`notify.mobile_app_xxx` or `persistent_notification`) |
| **Camera** | Camera to monitor, MQTT topic |
| **Filters** | Zones, object labels, disabled hours, severity (`alert` / `detection` / both) |
| **Behaviour** | Cooldown (s), debounce (s), silent duration (min), tap action, 3 action buttons |
| **Notifications** | Title template, message template, critical condition, sound and volume |

Repeat for each camera. Reconfiguration is available from the integration options at any time.

## Entities per camera

| Entity | Type | Description |
| --- | --- | --- |
| Notifications | `switch` | Enable / disable notifications for this camera |
| Motion | `binary_sensor` | `on` when a Frigate event is active |
| Active silence | `binary_sensor` | `on` while the camera is silenced |
| Silent mode | `button` | Activate silence for the configured duration |
| Cancel silence | `button` | Cancel an active silence immediately |
| Silence end | `sensor` | Timestamp when notifications will resume |

## Notification templates

Title, message and critical condition support [Jinja2 templates](https://www.home-assistant.io/docs/configuration/templating/).

Quick examples:

```jinja2
{# Title #}
{{ label | title }} — {{ camera | replace('_', ' ') | title }}

{# Message #}
{{ severity | upper }} at {{ start_time | timestamp_custom('%H:%M') }}{% if zones %} · {{ zones | join(', ') }}{% endif %}

{# Critical — alert only #}
{{ severity == 'alert' }}
```

Full variable reference and filter examples → [`docs/notifications.md`](docs/notifications.md)

## Action buttons

Up to 3 action buttons can be configured per camera:

| Value | Behaviour |
| --- | --- |
| `clip` | Opens the event clip (presigned URL) |
| `snapshot` | Opens the snapshot image |
| `preview` | Opens the animated preview |
| `silent_30min` | Silences the camera for 30 minutes |
| `silent_1h` | Silences the camera for 1 hour |
| `dismiss` | Dismisses the notification |

When all buttons are set to `none`, a default **Silence 30 min** button is added automatically.

## Media URLs (presigned proxy)

Notification media links (snapshot, clip, preview) are served through **HA's own HTTP server**, not directly from Frigate.

### How it works

When the integration starts, HA generates an ephemeral HMAC-SHA256 signing key (32 random bytes, in memory only, never stored). The key **rotates automatically every 24 hours** — no restart needed. Each media URL contains a slot ID (`kid`) so the correct key is used for verification:

```text
https://<your-ha>/api/frigate_em/media/api/events/<id>/snapshot.jpg?exp=<timestamp>&kid=<slot>&sig=<hmac>
```

When the mobile app opens the link, HA verifies the signature and expiry, then proxies the request to Frigate internally. **Your mobile app never needs direct access to Frigate.**

URLs expire after a configurable TTL (default **1 hour**, adjustable in the connection step: 5 min → 24 h).

### Prerequisite

HA's URL must be configured in **Settings → System → Network**. The integration uses the external URL first, then the internal URL as a fallback.

- **External URL set** → works from anywhere
- **Internal URL only** → works only on your home network
- **Neither set** → presigned URLs are disabled entirely and no media links are included in notifications

### Why not use Frigate's native proxy?

The official Frigate HA integration links directly to Frigate URLs. This integration signs URLs through HA instead, so:

- Only HA needs to be reachable from outside (standard setup for remote push notifications)
- Frigate can stay fully isolated on your local network
- No Frigate credentials are exposed in notification payloads

## License

[MIT](LICENSE) — © 2026 trowaflo
