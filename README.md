# Frigate Event Manager

[![HACS](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://hacs.xyz)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Home Assistant integration that listens to [Frigate NVR](https://frigate.video) events via MQTT,
applies configurable filters, and sends rich notifications to the HA Companion app.

## Features

- **Per-camera configuration** — each camera is an independent config entry with its own filters, throttle and notification settings
- **Smart filtering** — filter by zone, object label, time of day and severity (`alert` / `detection`)
- **Anti-spam** — configurable cooldown (per camera) and debounce to group rapid detections
- **Rich notifications** — snapshot, clip and preview URLs (presigned HMAC-SHA256), action buttons, iOS critical alerts
- **Silent mode** — mute a camera for a configurable duration directly from the notification
- **Jinja2 templates** — fully customisable title, message and critical condition

## Prerequisites

- Home Assistant 2024.1+
- [Frigate NVR](https://frigate.video) with MQTT enabled
- MQTT broker integrated in Home Assistant (`Settings > Devices & Services > MQTT`)
- [HA Companion app](https://companion.home-assistant.io/) for mobile notifications (optional — `persistent_notification` is also supported)

## Installation

### Via HACS (recommended)

1. Open HACS → Integrations → ⋮ → Custom repositories
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

## Architecture

Hexagonal architecture — domain logic has zero HA dependency.
Diagrams and component details → [`docs/architecture.md`](docs/architecture.md)

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).
Issues and pull requests welcome — please use the provided templates.

## License

[MIT](LICENSE) — © 2026 trowaflo
