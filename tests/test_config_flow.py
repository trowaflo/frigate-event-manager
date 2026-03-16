"""Tests du config flow Frigate Event Manager — flow 2 étapes."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import aiohttp
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
# Données valides pour les tests
# ---------------------------------------------------------------------------

VALID_USER_INPUT = {
    CONF_URL: "http://frigate.local:5000",
    CONF_NOTIFY_TARGET: "notify.mobile_app_iphone",
}

CAMERAS_LIST = ["jardin", "entree", "garage"]

# ---------------------------------------------------------------------------
# Helper — mock FrigateClient.get_cameras
# ---------------------------------------------------------------------------

PATCH_GET_CAMERAS = "custom_components.frigate_event_manager.config_flow.FrigateClient.get_cameras"
PATCH_SETUP_ENTRY = "custom_components.frigate_event_manager.async_setup_entry"


# ---------------------------------------------------------------------------
# Tests step user
# ---------------------------------------------------------------------------


async def test_config_flow_happy_path(hass: HomeAssistant) -> None:
    """Happy path : formulaire valide + get_cameras() OK → entrée créée."""
    with (
        patch(PATCH_GET_CAMERAS, new=AsyncMock(return_value=CAMERAS_LIST)),
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
    # Première configuration
    with (
        patch(PATCH_GET_CAMERAS, new=AsyncMock(return_value=CAMERAS_LIST)),
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

    # Deuxième tentative → abort
    result2 = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    assert result2["type"] == FlowResultType.ABORT
    assert result2["reason"] == "already_configured"


async def test_config_flow_cannot_connect(hass: HomeAssistant) -> None:
    """get_cameras() lève ClientError → formulaire réaffiché avec erreur cannot_connect."""
    with patch(
        PATCH_GET_CAMERAS,
        new=AsyncMock(side_effect=aiohttp.ClientConnectionError("connexion refusée")),
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

    assert result2["type"] == FlowResultType.FORM
    assert result2["step_id"] == "user"
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_config_flow_cannot_connect_server_error(hass: HomeAssistant) -> None:
    """ServerConnectionError (sous-classe de ClientError) → même comportement."""
    with patch(
        PATCH_GET_CAMERAS,
        new=AsyncMock(side_effect=aiohttp.ServerConnectionError("timeout")),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=VALID_USER_INPUT,
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"]["base"] == "cannot_connect"


async def test_config_flow_missing_url_field(hass: HomeAssistant) -> None:
    """CONF_URL est requis — voluptuous lève une exception si le champ est absent."""
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


async def test_config_flow_data_url_stored_correctly(hass: HomeAssistant) -> None:
    """L'URL saisie est conservée telle quelle dans entry.data."""
    url = "http://192.168.1.100:5000"
    with (
        patch(PATCH_GET_CAMERAS, new=AsyncMock(return_value=["cam1"])),
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


async def test_config_flow_get_cameras_called_with_provided_url(hass: HomeAssistant) -> None:
    """get_cameras() est bien appelé (validation de la connexion à Frigate)."""
    get_cameras_mock = AsyncMock(return_value=["cam1"])
    with (
        patch(PATCH_GET_CAMERAS, new=get_cameras_mock),
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

    get_cameras_mock.assert_called_once()


# ---------------------------------------------------------------------------
# Tests step camera
# ---------------------------------------------------------------------------


async def test_config_flow_step_camera_form_displayed(hass: HomeAssistant) -> None:
    """Step camera : le formulaire s'affiche correctement."""
    # Configurer l'entrée globale d'abord
    with (
        patch(PATCH_GET_CAMERAS, new=AsyncMock(return_value=CAMERAS_LIST)),
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

    # Lancer le step camera
    with patch(PATCH_GET_CAMERAS, new=AsyncMock(return_value=CAMERAS_LIST)):
        result_cam = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "camera"},
        )

    assert result_cam["type"] == FlowResultType.FORM
    assert result_cam["step_id"] == "camera"


async def test_config_flow_step_camera_creates_entry(hass: HomeAssistant) -> None:
    """Step camera : soumission valide → entrée caméra créée."""
    # Configurer l'entrée globale d'abord
    with (
        patch(PATCH_GET_CAMERAS, new=AsyncMock(return_value=CAMERAS_LIST)),
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

    # Ajouter une caméra
    with (
        patch(PATCH_GET_CAMERAS, new=AsyncMock(return_value=CAMERAS_LIST)),
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
    # Configurer l'entrée globale
    with (
        patch(PATCH_GET_CAMERAS, new=AsyncMock(return_value=CAMERAS_LIST)),
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

    # Première caméra
    with (
        patch(PATCH_GET_CAMERAS, new=AsyncMock(return_value=CAMERAS_LIST)),
        patch(PATCH_SETUP_ENTRY, return_value=True),
    ):
        result_cam1 = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "camera"},
        )
        await hass.config_entries.flow.async_configure(
            result_cam1["flow_id"],
            user_input={CONF_CAMERA: "jardin", CONF_NOTIFY_TARGET: ""},
        )

    # Deuxième tentative avec la même caméra → abort
    with patch(PATCH_GET_CAMERAS, new=AsyncMock(return_value=CAMERAS_LIST)):
        result_cam2 = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "camera"},
        )
        result_cam3 = await hass.config_entries.flow.async_configure(
            result_cam2["flow_id"],
            user_input={CONF_CAMERA: "jardin", CONF_NOTIFY_TARGET: ""},
        )

    assert result_cam3["type"] == FlowResultType.ABORT
    assert result_cam3["reason"] == "already_configured"


async def test_config_flow_step_camera_notify_target_none_when_empty(
    hass: HomeAssistant,
) -> None:
    """notify_target vide dans step camera → stocké comme None (pas chaîne vide)."""
    with (
        patch(PATCH_GET_CAMERAS, new=AsyncMock(return_value=CAMERAS_LIST)),
        patch(PATCH_SETUP_ENTRY, return_value=True),
    ):
        # Entrée globale
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )
        await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=VALID_USER_INPUT,
        )

    with (
        patch(PATCH_GET_CAMERAS, new=AsyncMock(return_value=CAMERAS_LIST)),
        patch(PATCH_SETUP_ENTRY, return_value=True),
    ):
        result_cam = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "camera"},
        )
        result_cam2 = await hass.config_entries.flow.async_configure(
            result_cam["flow_id"],
            user_input={CONF_CAMERA: "entree", CONF_NOTIFY_TARGET: ""},
        )

    assert result_cam2["type"] == FlowResultType.CREATE_ENTRY
    assert result_cam2["data"][CONF_NOTIFY_TARGET] is None


async def test_config_flow_step_camera_notify_target_stored(hass: HomeAssistant) -> None:
    """notify_target non-vide dans step camera → stocké tel quel."""
    with (
        patch(PATCH_GET_CAMERAS, new=AsyncMock(return_value=CAMERAS_LIST)),
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

    with (
        patch(PATCH_GET_CAMERAS, new=AsyncMock(return_value=CAMERAS_LIST)),
        patch(PATCH_SETUP_ENTRY, return_value=True),
    ):
        result_cam = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "camera"},
        )
        result_cam2 = await hass.config_entries.flow.async_configure(
            result_cam["flow_id"],
            user_input={
                CONF_CAMERA: "garage",
                CONF_NOTIFY_TARGET: "notify.mobile_app_tablet",
            },
        )

    assert result_cam2["type"] == FlowResultType.CREATE_ENTRY
    assert result_cam2["data"][CONF_NOTIFY_TARGET] == "notify.mobile_app_tablet"


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
    assert len(conf_keys) >= 4  # CONF_URL, CONF_NOTIFY_TARGET, CONF_CAMERA, CONF_MQTT_TOPIC
    for key in conf_keys:
        assert isinstance(key, str)
        assert len(key) > 0


async def test_const_conf_url_value() -> None:
    """CONF_URL doit valoir 'url'."""
    assert CONF_URL == "url"


async def test_const_conf_camera_value() -> None:
    """CONF_CAMERA doit valoir 'camera'."""
    assert CONF_CAMERA == "camera"


async def test_const_conf_notify_target_value() -> None:
    """CONF_NOTIFY_TARGET doit valoir 'notify_target'."""
    assert CONF_NOTIFY_TARGET == "notify_target"


async def test_const_conf_mqtt_topic_value() -> None:
    """CONF_MQTT_TOPIC doit valoir 'mqtt_topic'."""
    assert CONF_MQTT_TOPIC == "mqtt_topic"
