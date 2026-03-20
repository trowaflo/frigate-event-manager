"""Tests de __init__.py — async_migrate_entry, async_setup_entry, async_unload_entry."""

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
    """Crée un ConfigEntry mock."""
    entry = MagicMock()
    entry.version = version
    entry.minor_version = minor_version
    entry.data = data or {CONF_URL: VALID_URL}
    entry.subentries = subentries or {}
    entry.entry_id = "test-entry-id"
    entry.runtime_data = {}
    return entry


def _make_subentry(cam_name: str = "jardin") -> MagicMock:
    """Crée une subentry mock pour une caméra."""
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
        """Migration v2→v3 supprime notify_target de entry.data."""
        from custom_components.frigate_event_manager import async_migrate_entry

        entry = _make_entry(
            version=2,
            data={CONF_URL: VALID_URL, CONF_NOTIFY_TARGET: "notify.mobile"},
        )

        # Patcher async_update_entry pour intercepter l'appel
        with patch.object(hass.config_entries, "async_update_entry") as mock_update:
            result = await async_migrate_entry(hass, entry)

        assert result is True
        mock_update.assert_called_once()
        call_kwargs = mock_update.call_args[1]
        assert CONF_NOTIFY_TARGET not in call_kwargs.get("data", {})
        assert call_kwargs.get("version") == 3
        assert call_kwargs.get("minor_version") == 1

    async def test_migration_v2_conserve_url(self, hass: HomeAssistant) -> None:
        """Migration v2→v3 conserve les autres données (url, username...)."""
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
        """Une entry en v3 migre vers v4 (entités de réglage) sans transformation de données."""
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
        """Migration v2 sans notify_target existant — pas d'erreur."""
        from custom_components.frigate_event_manager import async_migrate_entry

        entry = _make_entry(version=2, data={CONF_URL: VALID_URL})

        with patch.object(hass.config_entries, "async_update_entry"):
            result = await async_migrate_entry(hass, entry)

        assert result is True


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
        """Si MQTT non disponible, ConfigEntryNotReady est levée."""
        from homeassistant.exceptions import ConfigEntryNotReady
        from custom_components.frigate_event_manager import async_setup_entry

        entry = _make_entry()

        with patch(PATCH_MQTT_WAIT, return_value=False):
            with pytest.raises(ConfigEntryNotReady):
                await async_setup_entry(hass, entry)

    async def test_setup_sans_subentries_cree_zero_coordinator(
        self, hass: HomeAssistant
    ) -> None:
        """Sans subentries → aucun coordinator créé."""
        from custom_components.frigate_event_manager import async_setup_entry

        entry = _make_entry(subentries={})
        # Pas de URL interne/externe → pas de signer
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
        """Une subentry caméra → un coordinator créé et démarré."""
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
        """async_setup_entry enregistre un FrigateClient dans hass.data[PROXY_CLIENT_KEY]."""
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
        """Si URL externe HA est configurée → signer créé dans hass.data."""
        from custom_components.frigate_event_manager import async_setup_entry

        entry = _make_entry(subentries={})
        hass.config.external_url = "https://mon-ha.duckdns.org"
        hass.config.internal_url = None
        # Nettoyer le signer potentiellement déjà présent
        hass.data.pop(SIGNER_DOMAIN_KEY, None)
        # hass.http peut être None en tests — patch pour éviter register_view
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
        """Sans URL HA → warning loggé, signer absent."""
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
        """async_unload_entry appelle async_stop sur chaque coordinator."""
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
        """async_unload_entry sans runtime_data ne lève pas d'exception."""
        from custom_components.frigate_event_manager import async_unload_entry

        entry = _make_entry()
        # Pas de runtime_data → getattr retourne {}
        del entry.runtime_data

        with patch(
            "homeassistant.config_entries.ConfigEntries.async_unload_platforms",
            return_value=True,
        ):
            result = await async_unload_entry(hass, entry)

        assert result is True
