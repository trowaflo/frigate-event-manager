# Notification Templates

Frigate Event Manager supports [Jinja2 templates](https://www.home-assistant.io/docs/configuration/templating/)
for notification titles and messages, using the same engine as Home Assistant.

## Available variables

| Variable | Type | Description | Example |
| --- | --- | --- | --- |
| `camera` | `str` | Camera name (HTML-escaped) | `"front_door"` |
| `camera_name` | `str` | Alias for `camera` | `"front_door"` |
| `label` | `str` | First detected object | `"person"` |
| `objects` | `list[str]` | All detected objects | `["person", "car"]` |
| `zones` | `list[str]` | Active zones | `["driveway", "entrance"]` |
| `severity` | `str` | Event severity | `"alert"` or `"detection"` |
| `score` | `float` | Confidence score (0.0–1.0) | `0.87` |
| `start_time` | `float` | Event start timestamp (Unix) | `1711100400.0` |
| `review_id` | `str` | Frigate review ID | `"abc123"` |
| `clip_url` | `str` | Signed URL — video clip | `"https://…"` |
| `snapshot_url` | `str` | Signed URL — snapshot | `"https://…"` |
| `preview_url` | `str` | Signed URL — animated preview | `"https://…"` |
| `thumbnail_url` | `str` | Signed URL — thumbnail | `"https://…"` |

> URL fields are empty strings when no media is available or Frigate URL is not configured.

## Title examples

Default:

```jinja2
Frigate — {{ camera }}
```

With object and zone:

```jinja2
{{ label | title }} detected — {{ camera | replace('_', ' ') | title }}
```

With severity indicator:

```jinja2
{% if severity == 'alert' %}🚨{% else %}👁{% endif %} {{ camera }} — {{ label }}
```

## Message examples

Default:

```jinja2
{{ objects | join(', ') or 'unknown object' }} detected ({{ severity }})
```

With time and zones:

```jinja2
{{ label }} at {{ start_time | timestamp_custom('%H:%M') }}{% if zones %} · {{ zones | join(', ') }}{% endif %}
```

With score:

```jinja2
{{ label | title }} ({{ (score * 100) | round }}%) — {{ severity }}{% if zones %} in {{ zones | first }}{% endif %}
```

Multi-line with link (persistent notification only):

```jinja2
**{{ label | title }}** detected on `{{ camera }}`
Confidence: {{ (score * 100) | round }}%
{% if zones %}Zones: {{ zones | join(', ') }}{% endif %}
```

## Critical template examples

The critical template evaluates to `true` to trigger a critical iOS alert (high-volume sound, bypasses silent mode).

Always critical:

```jinja2
true
```

Critical only for alerts:

```jinja2
{{ severity == 'alert' }}
```

Critical at night only (adapt sensor names to your setup):

```jinja2
{{ severity == 'alert' and is_state('binary_sensor.night_mode', 'on') }}
```

Critical for specific cameras or objects:

```jinja2
{{ camera in ['front_door', 'garage'] and label == 'person' }}
```

## HA Jinja2 filters reference

| Filter | Example | Result |
| --- | --- | --- |
| `timestamp_custom('%H:%M')` | `{{ start_time \| timestamp_custom('%H:%M') }}` | `"14:35"` |
| `title` | `{{ label \| title }}` | `"Person"` |
| `upper` | `{{ severity \| upper }}` | `"ALERT"` |
| `replace('_', ' ')` | `{{ camera \| replace('_', ' ') }}` | `"front door"` |
| `join(', ')` | `{{ objects \| join(', ') }}` | `"person, car"` |
| `first` | `{{ zones \| first }}` | `"driveway"` |
| `round` | `{{ (score * 100) \| round }}` | `87` |

Full reference: [Home Assistant Templating](https://www.home-assistant.io/docs/configuration/templating/)
