"""Tests du config flow Frigate Event Manager — flow 2 étapes."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.frigate_event_manager.const import (
    CONF_CAMERA,
    CONF_MQTT_TOPIC,
    CONF_NOTIFY_TARGET,
    CONF_URL,
    DEFAULT_MQTT_TOPIC,
    DOMAIN,
)

# ---------------------------------------------------------------------------
# Données valides
# ---------------------------------------------------------------------------

VALID_USER_INPUT = {
    CONF_URL: "http://frigate.local:5000",
    CONF_NOTIFY_TARGET: "notify.mobile_app_iphone",
}

CAMERAS_LIST = ["entree", "garage", "jardin"]

# ---------------------------------------------------------------------------
# Patches
# ---------------------------------------------------------------------------

PATCH_DETECT_URL = "custom_components.frigate_event_manager.config_flow._detect_frigate_url"
PATCH_DISCOVER = "custom_components.frigate_event_manager.config_flow._discover_frigate_cameras"
PATCH_SETUP_ENTRY = "custom_components.frigate_event_manager.async_setup_entry"


# ---------------------------------------------------------------------------
# Tests step user
# ---------------------------------------------------------------------------


async def test_config_flow_happy_path(hass: HomeAssistant) -> None:
    """Happy path : formulaire valide → entrée créée."""
    with (
        patch(PATCH_DETECT_URL, return_value=None),
        patch(PATCH_SETUP_ENTRY, return_value=True),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "user"

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=VALID_USER_INPUT,
        )

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Frigate Event Manager"
    assert result2["data"][CONF_URL] == "http://frigate.local:5000"
    assert result2["data"][CONF_NOTIFY_TARGET] == "notify.mobile_app_iphone"


async def test_config_flow_already_configured(hass: HomeAssistant) -> None:
    """Si l'intégration est déjà configurée → abort already_configured."""
    with (
        patch(PATCH_DETECT_URL, return_value=None),
        patch(PATCH_SETUP_ENTRY, return_value=True),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )
        await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=VALID_USER_INPUT,
        )

    result2 = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    assert result2["type"] == FlowResultType.ABORT
    assert result2["reason"] == "already_configured"


async def test_config_flow_frigate_url_autodetected(hass: HomeAssistant) -> None:
    """Si Frigate intégration présente → URL pré-remplie dans le champ."""
    with (
        patch(PATCH_DETECT_URL, return_value="http://frigate.local:5000"),
        patch(PATCH_SETUP_ENTRY, return_value=True),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )
        assert result["type"] == FlowResultType.FORM
        # L'URL est pré-remplie mais le champ est toujours présent (modifiable)
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=VALID_USER_INPUT,
        )

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["data"][CONF_URL] == "http://frigate.local:5000"


async def test_config_flow_frigate_url_override(hass: HomeAssistant) -> None:
    """Même si Frigate détectée, l'utilisateur peut saisir une autre URL."""
    override_url = "https://frigate.mondomaine.com"
    with (
        patch(PATCH_DETECT_URL, return_value="http://192.168.1.10:5000"),
        patch(PATCH_SETUP_ENTRY, return_value=True),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_URL: override_url, CONF_NOTIFY_TARGET: "notify.test"},
        )

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["data"][CONF_URL] == override_url


async def test_config_flow_missing_url_field(hass: HomeAssistant) -> None:
    """CONF_URL est requis — voluptuous lève une exception si absent."""
    with patch(PATCH_DETECT_URL, return_value=None):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )
    assert result["type"] == FlowResultType.FORM

    invalid_input = {k: v for k, v in VALID_USER_INPUT.items() if k != CONF_URL}
    with pytest.raises(Exception):
        await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=invalid_input,
        )


async def test_config_flow_missing_notify_target_field(hass: HomeAssistant) -> None:
    """CONF_NOTIFY_TARGET est requis — voluptuous lève une exception si absent."""
    with patch(PATCH_DETECT_URL, return_value=None):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )
    assert result["type"] == FlowResultType.FORM

    invalid_input = {k: v for k, v in VALID_USER_INPUT.items() if k != CONF_NOTIFY_TARGET}
    with pytest.raises(Exception):
        await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=invalid_input,
        )


async def test_config_flow_url_stored_correctly(hass: HomeAssistant) -> None:
    """L'URL saisie est conservée telle quelle dans entry.data."""
    url = "http://192.168.1.100:5000"
    with (
        patch(PATCH_DETECT_URL, return_value=None),
        patch(PATCH_SETUP_ENTRY, return_value=True),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_URL: url, CONF_NOTIFY_TARGET: "notify.test"},
        )

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["data"][CONF_URL] == url


# ---------------------------------------------------------------------------
# Tests step camera
# ---------------------------------------------------------------------------


async def _setup_global_entry(hass: HomeAssistant) -> None:
    """Helper : configure l'entrée globale."""
    with (
        patch(PATCH_DETECT_URL, return_value=None),
        patch(PATCH_SETUP_ENTRY, return_value=True),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )
        await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=VALID_USER_INPUT,
        )


async def test_config_flow_step_camera_form_displayed(hass: HomeAssistant) -> None:
    """Step camera : le formulaire s'affiche correctement."""
    await _setup_global_entry(hass)

    with patch(PATCH_DISCOVER, return_value=CAMERAS_LIST):
        result_cam = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "camera"},
        )

    assert result_cam["type"] == FlowResultType.FORM
    assert result_cam["step_id"] == "camera"


async def test_config_flow_step_camera_creates_entry(hass: HomeAssistant) -> None:
    """Step camera : soumission valide → entrée caméra créée."""
    await _setup_global_entry(hass)

    with (
        patch(PATCH_DISCOVER, return_value=CAMERAS_LIST),
        patch(PATCH_SETUP_ENTRY, return_value=True),
    ):
        result_cam = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "camera"},
        )
        result_cam2 = await hass.config_entries.flow.async_configure(
            result_cam["flow_id"],
            user_input={CONF_CAMERA: "jardin", CONF_NOTIFY_TARGET: ""},
        )

    assert result_cam2["type"] == FlowResultType.CREATE_ENTRY
    assert result_cam2["title"] == "Caméra jardin"
    assert result_cam2["data"][CONF_CAMERA] == "jardin"


async def test_config_flow_step_camera_already_configured(hass: HomeAssistant) -> None:
    """Ajouter deux fois la même caméra → abort already_configured."""
    await _setup_global_entry(hass)

    with (
        patch(PATCH_DISCOVER, return_value=CAMERAS_LIST),
        patch(PATCH_SETUP_ENTRY, return_value=True),
    ):
        r1 = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "camera"}
        )
        await hass.config_entries.flow.async_configure(
            r1["flow_id"],
            user_input={CONF_CAMERA: "jardin", CONF_NOTIFY_TARGET: ""},
        )

    with patch(PATCH_DISCOVER, return_value=CAMERAS_LIST):
        r2 = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "camera"}
        )
        r3 = await hass.config_entries.flow.async_configure(
            r2["flow_id"],
            user_input={CONF_CAMERA: "jardin", CONF_NOTIFY_TARGET: ""},
        )

    assert r3["type"] == FlowResultType.ABORT
    assert r3["reason"] == "already_configured"


async def test_config_flow_step_camera_notify_target_none_when_empty(
    hass: HomeAssistant,
) -> None:
    """notify_target vide → stocké comme None."""
    await _setup_global_entry(hass)

    with (
        patch(PATCH_DISCOVER, return_value=CAMERAS_LIST),
        patch(PATCH_SETUP_ENTRY, return_value=True),
    ):
        r = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "camera"}
        )
        r2 = await hass.config_entries.flow.async_configure(
            r["flow_id"],
            user_input={CONF_CAMERA: "entree", CONF_NOTIFY_TARGET: ""},
        )

    assert r2["type"] == FlowResultType.CREATE_ENTRY
    assert r2["data"][CONF_NOTIFY_TARGET] is None


async def test_config_flow_step_camera_notify_target_stored(hass: HomeAssistant) -> None:
    """notify_target non-vide → stocké tel quel."""
    await _setup_global_entry(hass)

    with (
        patch(PATCH_DISCOVER, return_value=CAMERAS_LIST),
        patch(PATCH_SETUP_ENTRY, return_value=True),
    ):
        r = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "camera"}
        )
        r2 = await hass.config_entries.flow.async_configure(
            r["flow_id"],
            user_input={CONF_CAMERA: "garage", CONF_NOTIFY_TARGET: "notify.tablet"},
        )

    assert r2["type"] == FlowResultType.CREATE_ENTRY
    assert r2["data"][CONF_NOTIFY_TARGET] == "notify.tablet"


async def test_config_flow_step_camera_no_global_entry(hass: HomeAssistant) -> None:
    """Step camera sans entrée globale → abort missing_global_entry."""
    with patch(PATCH_DISCOVER, return_value=CAMERAS_LIST):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "camera"}
        )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "missing_global_entry"


# ---------------------------------------------------------------------------
# Tests constantes
# ---------------------------------------------------------------------------


async def test_const_domain() -> None:
    """DOMAIN doit être cohérent avec le nom du dossier."""
    assert DOMAIN == "frigate_event_manager"


async def test_const_mqtt_topic_default() -> None:
    """DEFAULT_MQTT_TOPIC doit correspondre au topic Frigate standard."""
    assert DEFAULT_MQTT_TOPIC == "frigate/reviews"


async def test_const_conf_keys_are_strings() -> None:
    """Toutes les clés CONF_* doivent être des chaînes non-vides."""
    from custom_components.frigate_event_manager import const

    conf_keys = [v for k, v in vars(const).items() if k.startswith("CONF_")]
    assert len(conf_keys) >= 4
    for key in conf_keys:
        assert isinstance(key, str)
        assert len(key) > 0


async def test_const_conf_url_value() -> None:
    assert CONF_URL == "url"


async def test_const_conf_camera_value() -> None:
    assert CONF_CAMERA == "camera"


async def test_const_conf_notify_target_value() -> None:
    assert CONF_NOTIFY_TARGET == "notify_target"


async def test_const_conf_mqtt_topic_value() -> None:
    assert CONF_MQTT_TOPIC == "mqtt_topic"
