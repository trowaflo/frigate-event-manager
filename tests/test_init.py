"""Tests for __init__.py — async_migrate_entry, async_setup_entry, async_unload_entry."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.core import HomeAssistant

from custom_components.frigate_event_manager.const import (
    CONF_NOTIFY_TARGET,
    CONF_URL,
    PERSISTENT_NOTIFICATION,
    PROXY_CLIENT_KEY,
    SIGNER_DOMAIN_KEY,
    SUBENTRY_TYPE_CAMERA,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

VALID_URL = "http://frigate.local:5000"


def _make_entry(
    version: int = 3,
    minor_version: int = 1,
    data: dict | None = None,
    subentries: dict | None = None,
) -> MagicMock:
    """Create a mock ConfigEntry."""
    entry = MagicMock()
    entry.version = version
    entry.minor_version = minor_version
    entry.data = data or {CONF_URL: VALID_URL}
    entry.subentries = subentries or {}
    entry.entry_id = "test-entry-id"
    entry.runtime_data = {}
    return entry


def _make_subentry(cam_name: str = "jardin") -> MagicMock:
    """Create a mock subentry for a camera."""
    subentry = MagicMock()
    subentry.subentry_id = f"sub_{cam_name}"
    subentry.subentry_type = SUBENTRY_TYPE_CAMERA
    subentry.data = {
        "camera": cam_name,
        CONF_NOTIFY_TARGET: PERSISTENT_NOTIFICATION,
    }
    return subentry


# ---------------------------------------------------------------------------
# Tests async_migrate_entry
# ---------------------------------------------------------------------------


class TestAsyncMigrateEntry:
    async def test_migration_v2_supprime_notify_target(
        self, hass: HomeAssistant
    ) -> None:
        """Migration v2→v3 removes notify_target from entry.data."""
        from custom_components.frigate_event_manager import async_migrate_entry

        entry = _make_entry(
            version=2,
            data={CONF_URL: VALID_URL, CONF_NOTIFY_TARGET: "notify.mobile"},
        )

        # Patch async_update_entry to intercept the call
        with patch.object(hass.config_entries, "async_update_entry") as mock_update:
            result = await async_migrate_entry(hass, entry)

        assert result is True
        mock_update.assert_called_once()
        call_kwargs = mock_update.call_args[1]
        assert CONF_NOTIFY_TARGET not in call_kwargs.get("data", {})
        assert call_kwargs.get("version") == 3
        assert call_kwargs.get("minor_version") == 1

    async def test_migration_v2_conserve_url(self, hass: HomeAssistant) -> None:
        """Migration v2→v3 preserves other data (url, username...)."""
        from custom_components.frigate_event_manager import async_migrate_entry

        entry = _make_entry(
            version=2,
            data={
                CONF_URL: VALID_URL,
                CONF_NOTIFY_TARGET: "notify.mobile",
                "username": "admin",
            },
        )

        with patch.object(hass.config_entries, "async_update_entry") as mock_update:
            await async_migrate_entry(hass, entry)

        call_kwargs = mock_update.call_args[1]
        new_data = call_kwargs.get("data", {})
        assert new_data.get(CONF_URL) == VALID_URL
        assert new_data.get("username") == "admin"

    async def test_migration_v3_migre_vers_v4(self, hass: HomeAssistant) -> None:
        """A v3 entry migrates to v4 (tuning entities) without data transformation."""
        from custom_components.frigate_event_manager import async_migrate_entry

        entry = _make_entry(version=3)

        with patch.object(hass.config_entries, "async_update_entry") as mock_update:
            result = await async_migrate_entry(hass, entry)

        assert result is True
        mock_update.assert_called_once()
        call_kwargs = mock_update.call_args[1]
        assert call_kwargs.get("version") == 4
        assert call_kwargs.get("minor_version") == 1

    async def test_migration_v2_sans_notify_target(self, hass: HomeAssistant) -> None:
        """Migration v2 without existing notify_target — no error."""
        from custom_components.frigate_event_manager import async_migrate_entry

        entry = _make_entry(version=2, data={CONF_URL: VALID_URL})

        with patch.object(hass.config_entries, "async_update_entry"):
            result = await async_migrate_entry(hass, entry)

        assert result is True

    async def test_migration_v4_migre_vers_v5(self, hass: HomeAssistant) -> None:
        """A v4 entry migrates to v5 (multi-screen config flow) without data transformation."""
        from custom_components.frigate_event_manager import async_migrate_entry

        entry = _make_entry(version=4)

        with patch.object(hass.config_entries, "async_update_entry") as mock_update:
            result = await async_migrate_entry(hass, entry)

        assert result is True
        mock_update.assert_called_once()
        call_kwargs = mock_update.call_args[1]
        assert call_kwargs.get("version") == 5
        assert call_kwargs.get("minor_version") == 1

    async def test_migration_v5_vers_v6_supprime_silent_duration(
        self, hass: HomeAssistant
    ) -> None:
        """v5 → v6 migration removes silent_duration from subentry data and bumps to v6."""
        from custom_components.frigate_event_manager import async_migrate_entry

        entry = _make_entry(version=5)

        with (
            patch.object(hass.config_entries, "async_update_entry") as mock_update_entry,
            patch.object(hass.config_entries, "async_update_subentry"),
        ):
            result = await async_migrate_entry(hass, entry)

        assert result is True
        mock_update_entry.assert_called_once()
        call_kwargs = mock_update_entry.call_args
        assert call_kwargs.kwargs.get("version") == 6


# ---------------------------------------------------------------------------
# Tests async_setup_entry
# ---------------------------------------------------------------------------

PATCH_MQTT_WAIT = "custom_components.frigate_event_manager.mqtt.async_wait_for_mqtt_client"
PATCH_COORDINATOR = "custom_components.frigate_event_manager.FrigateEventManagerCoordinator"
PATCH_NOTIFIER = "custom_components.frigate_event_manager.HANotifier"
PATCH_FORWARD = "homeassistant.config_entries.ConfigEntries.async_forward_entry_setups"
PATCH_HTTP = "homeassistant.core.HomeAssistant.http"


class TestAsyncSetupEntry:
    async def test_mqtt_non_disponible_leve_configentrynotready(
        self, hass: HomeAssistant
    ) -> None:
        """If MQTT is not available, ConfigEntryNotReady is raised."""
        from homeassistant.exceptions import ConfigEntryNotReady
        from custom_components.frigate_event_manager import async_setup_entry

        entry = _make_entry()

        with patch(PATCH_MQTT_WAIT, return_value=False):
            with pytest.raises(ConfigEntryNotReady):
                await async_setup_entry(hass, entry)

    async def test_setup_sans_subentries_cree_zero_coordinator(
        self, hass: HomeAssistant
    ) -> None:
        """Without subentries → no coordinator created."""
        from custom_components.frigate_event_manager import async_setup_entry

        entry = _make_entry(subentries={})
        # No internal/external URL → no signer
        hass.config.external_url = None
        hass.config.internal_url = None

        with (
            patch(PATCH_MQTT_WAIT, return_value=True),
            patch(
                "homeassistant.config_entries.ConfigEntries.async_forward_entry_setups",
                return_value=None,
            ),
        ):
            result = await async_setup_entry(hass, entry)

        assert result is True
        assert entry.runtime_data == {}

    async def test_setup_avec_subentry_camera_cree_coordinator(
        self, hass: HomeAssistant
    ) -> None:
        """A camera subentry → one coordinator created and started."""
        from custom_components.frigate_event_manager import async_setup_entry

        subentry = _make_subentry("jardin")
        entry = _make_entry(subentries={"sub_jardin": subentry})
        hass.config.external_url = None
        hass.config.internal_url = None

        mock_coordinator = AsyncMock()
        mock_coordinator.async_start = AsyncMock()

        with (
            patch(PATCH_MQTT_WAIT, return_value=True),
            patch(PATCH_COORDINATOR, return_value=mock_coordinator),
            patch(PATCH_NOTIFIER, return_value=MagicMock()),
            patch(
                "homeassistant.config_entries.ConfigEntries.async_forward_entry_setups",
                return_value=None,
            ),
        ):
            result = await async_setup_entry(hass, entry)

        assert result is True
        mock_coordinator.async_start.assert_called_once()

    async def test_setup_cree_proxy_client(self, hass: HomeAssistant) -> None:
        """async_setup_entry registers a FrigateClient in hass.data[PROXY_CLIENT_KEY]."""
        from custom_components.frigate_event_manager import async_setup_entry

        entry = _make_entry(subentries={})
        hass.config.external_url = None
        hass.config.internal_url = None

        with (
            patch(PATCH_MQTT_WAIT, return_value=True),
            patch(
                "homeassistant.config_entries.ConfigEntries.async_forward_entry_setups",
                return_value=None,
            ),
        ):
            await async_setup_entry(hass, entry)

        assert PROXY_CLIENT_KEY in hass.data

    async def test_setup_cree_signer_si_url_externe(
        self, hass: HomeAssistant
    ) -> None:
        """If HA external URL is configured → signer created in hass.data."""
        from custom_components.frigate_event_manager import async_setup_entry

        entry = _make_entry(subentries={})
        hass.config.external_url = "https://mon-ha.duckdns.org"
        hass.config.internal_url = None
        # Clean up any signer already present
        hass.data.pop(SIGNER_DOMAIN_KEY, None)
        # hass.http may be None in tests — patch to avoid register_view
        mock_http = MagicMock()
        hass.http = mock_http

        with (
            patch(PATCH_MQTT_WAIT, return_value=True),
            patch(
                "homeassistant.config_entries.ConfigEntries.async_forward_entry_setups",
                return_value=None,
            ),
        ):
            await async_setup_entry(hass, entry)

        assert SIGNER_DOMAIN_KEY in hass.data
        mock_http.register_view.assert_called_once()

    async def test_setup_sans_url_externe_log_warning(
        self, hass: HomeAssistant
    ) -> None:
        """Without HA URL → warning logged, signer absent."""
        from custom_components.frigate_event_manager import async_setup_entry

        entry = _make_entry(subentries={})
        hass.config.external_url = None
        hass.config.internal_url = None
        hass.data.pop(SIGNER_DOMAIN_KEY, None)

        with (
            patch(PATCH_MQTT_WAIT, return_value=True),
            patch(
                "homeassistant.config_entries.ConfigEntries.async_forward_entry_setups",
                return_value=None,
            ),
        ):
            await async_setup_entry(hass, entry)

        assert SIGNER_DOMAIN_KEY not in hass.data


# ---------------------------------------------------------------------------
# Tests async_unload_entry
# ---------------------------------------------------------------------------


class TestAsyncUnloadEntry:
    async def test_unload_appelle_async_stop_sur_coordinators(
        self, hass: HomeAssistant
    ) -> None:
        """async_unload_entry calls async_stop on each coordinator."""
        from custom_components.frigate_event_manager import async_unload_entry

        coordinator1 = AsyncMock()
        coordinator2 = AsyncMock()
        entry = _make_entry()
        entry.runtime_data = {"sub1": coordinator1, "sub2": coordinator2}

        with patch(
            "homeassistant.config_entries.ConfigEntries.async_unload_platforms",
            return_value=True,
        ):
            result = await async_unload_entry(hass, entry)

        assert result is True
        coordinator1.async_stop.assert_called_once()
        coordinator2.async_stop.assert_called_once()

    async def test_unload_sans_runtime_data_ne_crash_pas(
        self, hass: HomeAssistant
    ) -> None:
        """async_unload_entry without runtime_data does not raise an exception."""
        from custom_components.frigate_event_manager import async_unload_entry

        entry = _make_entry()
        # No runtime_data → getattr returns {}
        del entry.runtime_data

        with patch(
            "homeassistant.config_entries.ConfigEntries.async_unload_platforms",
            return_value=True,
        ):
            result = await async_unload_entry(hass, entry)

        assert result is True
