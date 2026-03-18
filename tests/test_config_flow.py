"""Tests du config flow Frigate Event Manager — subentries."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.frigate_event_manager.const import (
    CONF_CAMERA,
    CONF_DISABLED_HOURS,
    CONF_LABELS,
    CONF_NOTIFY_TARGET,
    CONF_PASSWORD,
    CONF_URL,
    CONF_USERNAME,
    CONF_ZONES,
    DOMAIN,
    PERSISTENT_NOTIFICATION,
    SUBENTRY_TYPE_CAMERA,
)

# ---------------------------------------------------------------------------
# Données valides
# ---------------------------------------------------------------------------

VALID_URL = "http://frigate.local:5000"
VALID_USER_INPUT = {
    CONF_URL: VALID_URL,
    CONF_USERNAME: "",
    CONF_PASSWORD: "",
}
VALID_NOTIFY_INPUT = {CONF_NOTIFY_TARGET: PERSISTENT_NOTIFICATION}
CAMERAS_LIST = ["entree", "garage", "jardin"]

# ---------------------------------------------------------------------------
# Patches
# ---------------------------------------------------------------------------

PATCH_DETECT = "custom_components.frigate_event_manager.config_flow._detect_frigate_config"
PATCH_CLIENT = "custom_components.frigate_event_manager.config_flow.FrigateClient"
PATCH_SETUP = "custom_components.frigate_event_manager.async_setup_entry"
PATCH_NOTIFY = "custom_components.frigate_event_manager.config_flow._get_notify_options"


def _mock_client(cameras: list[str] | None = None):
    """Retourne un mock FrigateClient."""
    m = AsyncMock()
    m.get_cameras = AsyncMock(return_value=cameras or [])
    return m


# ---------------------------------------------------------------------------
# Tests config flow principal
# ---------------------------------------------------------------------------


async def test_step_user_affiche_formulaire(hass: HomeAssistant) -> None:
    """Le formulaire user s'affiche correctement."""
    with patch(PATCH_DETECT, return_value={}):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_step_user_preremplit_depuis_frigate(hass: HomeAssistant) -> None:
    """Les champs sont pré-remplis si l'intégration Frigate est présente."""
    with patch(PATCH_DETECT, return_value={"url": VALID_URL, "username": "admin", "password": None}):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
    assert result["type"] == FlowResultType.FORM


async def test_step_user_cannot_connect(hass: HomeAssistant) -> None:
    """Erreur cannot_connect si Frigate inaccessible."""
    import aiohttp
    mock = _mock_client()
    mock.get_cameras.side_effect = aiohttp.ClientError
    with (
        patch(PATCH_DETECT, return_value={}),
        patch(PATCH_CLIENT, return_value=mock),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=VALID_USER_INPUT
        )
    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"]["base"] == "cannot_connect"


async def test_step_user_valide_passe_a_notify(hass: HomeAssistant) -> None:
    """Connexion valide → passage à l'étape notify."""
    with (
        patch(PATCH_DETECT, return_value={}),
        patch(PATCH_CLIENT, return_value=_mock_client([])),
        patch(PATCH_NOTIFY, return_value=[PERSISTENT_NOTIFICATION]),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=VALID_USER_INPUT
        )
    assert result2["type"] == FlowResultType.FORM
    assert result2["step_id"] == "notify"


async def test_flow_complet_cree_entry(hass: HomeAssistant) -> None:
    """Flow complet (user + notify) → entry créée avec les bonnes données."""
    with (
        patch(PATCH_DETECT, return_value={}),
        patch(PATCH_CLIENT, return_value=_mock_client([])),
        patch(PATCH_NOTIFY, return_value=[PERSISTENT_NOTIFICATION]),
        patch(PATCH_SETUP, return_value=True),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=VALID_USER_INPUT
        )
        result_final = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=VALID_NOTIFY_INPUT
        )

    assert result_final["type"] == FlowResultType.CREATE_ENTRY
    assert result_final["data"][CONF_URL] == VALID_URL
    assert result_final["data"][CONF_NOTIFY_TARGET] == PERSISTENT_NOTIFICATION


async def test_flow_already_configured(hass: HomeAssistant) -> None:
    """Deuxième tentative de config → abort already_configured."""
    with (
        patch(PATCH_DETECT, return_value={}),
        patch(PATCH_CLIENT, return_value=_mock_client([])),
        patch(PATCH_NOTIFY, return_value=[PERSISTENT_NOTIFICATION]),
        patch(PATCH_SETUP, return_value=True),
    ):
        r1 = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        await hass.config_entries.flow.async_configure(
            r1["flow_id"], user_input=VALID_USER_INPUT
        )
        await hass.config_entries.flow.async_configure(
            r1["flow_id"], user_input=VALID_NOTIFY_INPUT
        )

    r2 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert r2["type"] == FlowResultType.ABORT
    assert r2["reason"] == "already_configured"


async def _create_entry(hass: HomeAssistant) -> str:
    """Helper : crée une config entry valide et retourne son entry_id."""
    with (
        patch(PATCH_DETECT, return_value={}),
        patch(PATCH_CLIENT, return_value=_mock_client(CAMERAS_LIST)),
        patch(PATCH_NOTIFY, return_value=[PERSISTENT_NOTIFICATION]),
        patch(PATCH_SETUP, return_value=True),
    ):
        r = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        await hass.config_entries.flow.async_configure(
            r["flow_id"], user_input=VALID_USER_INPUT
        )
        await hass.config_entries.flow.async_configure(
            r["flow_id"], user_input=VALID_NOTIFY_INPUT
        )
    # Récupère l'entry_id réel depuis le registre HA
    entries = hass.config_entries.async_entries(DOMAIN)
    assert entries, "Config entry non créée"
    return entries[0].entry_id


# ---------------------------------------------------------------------------
# Tests subentry — ajout caméra
# ---------------------------------------------------------------------------


async def test_subentry_affiche_formulaire_camera(hass: HomeAssistant) -> None:
    """Le formulaire d'ajout de caméra s'affiche avec la liste des caméras."""
    entry_id = await _create_entry(hass)

    with (
        patch(PATCH_CLIENT, return_value=_mock_client(CAMERAS_LIST)),
        patch(PATCH_NOTIFY, return_value=[PERSISTENT_NOTIFICATION]),
    ):
        result = await hass.config_entries.subentries.async_init(
            (entry_id, SUBENTRY_TYPE_CAMERA),
            context={"source": config_entries.SOURCE_USER},
        )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_subentry_cree_camera(hass: HomeAssistant) -> None:
    """Ajout d'une caméra → subentry créée avec les bonnes données."""
    entry_id = await _create_entry(hass)

    with (
        patch(PATCH_CLIENT, return_value=_mock_client(CAMERAS_LIST)),
        patch(PATCH_NOTIFY, return_value=[PERSISTENT_NOTIFICATION]),
        patch(PATCH_SETUP, return_value=True),
    ):
        r = await hass.config_entries.subentries.async_init(
            (entry_id, SUBENTRY_TYPE_CAMERA),
            context={"source": config_entries.SOURCE_USER},
        )
        r2 = await hass.config_entries.subentries.async_configure(
            r["flow_id"],
            user_input={CONF_CAMERA: "entree", CONF_NOTIFY_TARGET: PERSISTENT_NOTIFICATION},
        )

    assert r2["type"] == FlowResultType.CREATE_ENTRY
    assert r2["title"] == "Caméra entree"


async def test_subentry_cameras_deja_configurees_exclues(hass: HomeAssistant) -> None:
    """Les caméras déjà configurées n'apparaissent plus dans la liste."""
    entry_id = await _create_entry(hass)

    # Ajouter entree
    with (
        patch(PATCH_CLIENT, return_value=_mock_client(CAMERAS_LIST)),
        patch(PATCH_NOTIFY, return_value=[PERSISTENT_NOTIFICATION]),
        patch(PATCH_SETUP, return_value=True),
    ):
        r1 = await hass.config_entries.subentries.async_init(
            (entry_id, SUBENTRY_TYPE_CAMERA), context={"source": config_entries.SOURCE_USER}
        )
        await hass.config_entries.subentries.async_configure(
            r1["flow_id"],
            user_input={CONF_CAMERA: "entree", CONF_NOTIFY_TARGET: PERSISTENT_NOTIFICATION},
        )

    # Essayer d'ajouter toutes les caméras quand elles sont toutes déjà configurées
    with (
        patch(PATCH_CLIENT, return_value=_mock_client(["entree"])),
        patch(PATCH_NOTIFY, return_value=[PERSISTENT_NOTIFICATION]),
    ):
        r2 = await hass.config_entries.subentries.async_init(
            (entry_id, SUBENTRY_TYPE_CAMERA), context={"source": config_entries.SOURCE_USER}
        )

    assert r2["type"] == FlowResultType.ABORT
    assert r2["reason"] == "no_cameras_available"


async def test_subentry_cannot_connect(hass: HomeAssistant) -> None:
    """Erreur réseau lors de l'ajout de caméra → erreur affichée."""
    import aiohttp

    entry_id = await _create_entry(hass)

    mock = _mock_client()
    mock.get_cameras.side_effect = aiohttp.ClientError

    with (
        patch(PATCH_CLIENT, return_value=mock),
        patch(PATCH_NOTIFY, return_value=[PERSISTENT_NOTIFICATION]),
    ):
        result = await hass.config_entries.subentries.async_init(
            (entry_id, SUBENTRY_TYPE_CAMERA), context={"source": config_entries.SOURCE_USER}
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["base"] == "cannot_connect"


# ---------------------------------------------------------------------------
# Tests constantes
# ---------------------------------------------------------------------------


async def test_const_domain() -> None:
    """DOMAIN correspond au nom du dossier."""
    assert DOMAIN == "frigate_event_manager"


async def test_const_conf_url() -> None:
    assert CONF_URL == "url"


async def test_const_conf_camera() -> None:
    assert CONF_CAMERA == "camera"


async def test_const_persistent_notification() -> None:
    assert PERSISTENT_NOTIFICATION == "persistent_notification"


# ---------------------------------------------------------------------------
# Tests subentry — filtres
# ---------------------------------------------------------------------------


async def test_subentry_cree_camera_avec_filtres(hass: HomeAssistant) -> None:
    """Les filtres sont sérialisés correctement dans subentry.data."""
    entry_id = await _create_entry(hass)

    with (
        patch(PATCH_CLIENT, return_value=_mock_client(CAMERAS_LIST)),
        patch(PATCH_NOTIFY, return_value=[PERSISTENT_NOTIFICATION]),
        patch(PATCH_SETUP, return_value=True),
    ):
        r = await hass.config_entries.subentries.async_init(
            (entry_id, SUBENTRY_TYPE_CAMERA),
            context={"source": config_entries.SOURCE_USER},
        )
        r2 = await hass.config_entries.subentries.async_configure(
            r["flow_id"],
            user_input={
                CONF_CAMERA: "entree",
                CONF_NOTIFY_TARGET: PERSISTENT_NOTIFICATION,
                CONF_ZONES: "jardin,rue",
                CONF_LABELS: "person,car",
                CONF_DISABLED_HOURS: "0,1,2",
            },
        )

    assert r2["type"] == FlowResultType.CREATE_ENTRY
    assert r2["data"][CONF_ZONES] == ["jardin", "rue"]
    assert r2["data"][CONF_LABELS] == ["person", "car"]
    assert r2["data"][CONF_DISABLED_HOURS] == [0, 1, 2]


async def test_subentry_cree_camera_sans_filtres(hass: HomeAssistant) -> None:
    """Sans filtres, les listes sont vides (tout accepter)."""
    entry_id = await _create_entry(hass)

    with (
        patch(PATCH_CLIENT, return_value=_mock_client(CAMERAS_LIST)),
        patch(PATCH_NOTIFY, return_value=[PERSISTENT_NOTIFICATION]),
        patch(PATCH_SETUP, return_value=True),
    ):
        r = await hass.config_entries.subentries.async_init(
            (entry_id, SUBENTRY_TYPE_CAMERA),
            context={"source": config_entries.SOURCE_USER},
        )
        r2 = await hass.config_entries.subentries.async_configure(
            r["flow_id"],
            user_input={
                CONF_CAMERA: "entree",
                CONF_NOTIFY_TARGET: PERSISTENT_NOTIFICATION,
                CONF_ZONES: "",
                CONF_LABELS: "",
                CONF_DISABLED_HOURS: "",
            },
        )

    assert r2["type"] == FlowResultType.CREATE_ENTRY
    assert r2["data"][CONF_ZONES] == []
    assert r2["data"][CONF_LABELS] == []
    assert r2["data"][CONF_DISABLED_HOURS] == []
