# Development notes

## Config entry versioning

### When to bump the version

The version (`VERSION` in `config_flow.py`) must be incremented only when the **stored data structure** changes.

| Change | Migration required |
| --- | --- |
| Adding a field to the config flow | ✅ Yes |
| Removing a field | ✅ Yes |
| Renaming a field | ✅ Yes |
| Code changes (logic, entities, filters) | ❌ No |

### How to write a migration

In `__init__.py`, add a block in `async_migrate_entry`:

```python
if entry.version == N:
    new_data = {**entry.data, "new_field": DEFAULT_VALUE}
    hass.config_entries.async_update_entry(entry, data=new_data, version=N+1, minor_version=1)
    _LOGGER.info("migration vN -> vN+1 complete")
    return True
```

Also bump `VERSION = N+1` in `FrigateEventManagerConfigFlow`.

### Avoiding migration with `.get()`

For an **optional new field**, using `entry.data.get("field", DEFAULT)` instead of `entry.data["field"]` makes migration optional — existing configs receive the default value on the fly without a migration block.

### History

| Version | Change |
| --- | --- |
| v2 → v3 | Removed global `notify_target` (moved to subentry) |
| v3 → v4 | Tuning parameters moved to `subentry.data` |
| v4 → v5 | Added notification templates (`notif_title`, `notif_message`, `critical_template`) |
| v5 → v6 | Removed `silent_duration` (silence duration hardcoded to 30 min) |
| v6 → v7 | Added `media_ttl` (signed URL expiry, default 3600s) |

---

## Presigned media URLs

Media URLs in notifications are signed with HMAC-SHA256 by HA itself (not by Frigate).

- Signing key: ephemeral, 32 random bytes, never persisted
- Automatic rotation every 24h (`DEFAULT_MEDIA_ROTATION`) without restart
- TTL configurable in the config flow (default 1h, min 5 min, max 24h)
- URL format: `?exp=<timestamp>&kid=<slot>&sig=<hmac>`
- `kid` = key slot ID (identifies which key to use for verification after rotation)
- Max 2 keys in memory: current slot + previous slot (transition window)

Interactive demo script: `scripts/demo_signer.py`

---

## Local deployment

```bash
task deploy   # SSH → copy custom_components/ + restart HA
task test     # pytest + coverage ≥80%
task lint     # ruff + markdownlint
```
