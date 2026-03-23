"""Tests for the Frigate Event Manager config flow — subentries (multi-screen flow T-533)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.frigate_event_manager.const import (
    CONF_CAMERA,
    CONF_COOLDOWN,
    CONF_CRITICAL_TEMPLATE,
    CONF_DEBOUNCE,
    CONF_DISABLED_HOURS,
    CONF_LABELS,
    CONF_NOTIF_MESSAGE,
    CONF_NOTIF_TITLE,
    CONF_NOTIFY_TARGET,
    CONF_PASSWORD,
    CONF_SEVERITY,
    CONF_TAP_ACTION,
    CONF_URL,
    CONF_USERNAME,
    CONF_ZONES,
    DEFAULT_DEBOUNCE,
    DEFAULT_SEVERITY,
    DEFAULT_THROTTLE_COOLDOWN,
    DOMAIN,
    PERSISTENT_NOTIFICATION,
    SUBENTRY_TYPE_CAMERA,
)

# ---------------------------------------------------------------------------
# Valid data
# ---------------------------------------------------------------------------

VALID_URL = "http://frigate.local:5000"
VALID_USER_INPUT = {
    CONF_URL: VALID_URL,
    CONF_USERNAME: "",
    CONF_PASSWORD: "",
}
CAMERAS_LIST = ["entree", "garage", "jardin"]

# ---------------------------------------------------------------------------
# Patches
# ---------------------------------------------------------------------------

PATCH_DETECT = "custom_components.frigate_event_manager.config_flow._detect_frigate_config"
PATCH_CLIENT = "custom_components.frigate_event_manager.config_flow.FrigateClient"
PATCH_SETUP = "custom_components.frigate_event_manager.async_setup_entry"
PATCH_NOTIFY = "custom_components.frigate_event_manager.config_flow._get_notify_options"
PATCH_GET_CAM_CONFIG = (
    "custom_components.frigate_event_manager.config_flow.FrigateClient.get_camera_config"
)

# Default response from get_camera_config
CAM_CONFIG_DEFAULT = {"zones": ["jardin", "rue"], "labels": ["person", "car"]}
CAM_CONFIG_EMPTY = {"zones": [], "labels": []}


def _mock_client(cameras: list[str] | None = None):
    """Return a mock FrigateClient."""
    m = AsyncMock()
    m.get_cameras = AsyncMock(return_value=cameras or [])
    m.get_camera_config = AsyncMock(return_value=CAM_CONFIG_DEFAULT)
    return m


# ---------------------------------------------------------------------------
# Main config flow tests
# ---------------------------------------------------------------------------


async def test_step_user_affiche_formulaire(hass: HomeAssistant) -> None:
    """The user form is displayed correctly."""
    with patch(PATCH_DETECT, return_value={}):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_step_user_preremplit_depuis_frigate(hass: HomeAssistant) -> None:
    """Fields are pre-filled if the Frigate integration is present."""
    with patch(PATCH_DETECT, return_value={"url": VALID_URL, "username": "admin", "password": None}):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
    assert result["type"] == FlowResultType.FORM


async def test_step_user_cannot_connect(hass: HomeAssistant) -> None:
    """cannot_connect error if Frigate is unreachable."""
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


async def test_step_user_valide_cree_entry(hass: HomeAssistant) -> None:
    """Valid connection → entry created directly (no more notify step)."""
    with (
        patch(PATCH_DETECT, return_value={}),
        patch(PATCH_CLIENT, return_value=_mock_client([])),
        patch(PATCH_SETUP, return_value=True),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=VALID_USER_INPUT
        )
    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["data"][CONF_URL] == VALID_URL
    # No notify_target in the main entry (feature 6)
    assert CONF_NOTIFY_TARGET not in result2["data"]


async def test_flow_complet_cree_entry(hass: HomeAssistant) -> None:
    """Flow (user) → entry created with the correct data."""
    with (
        patch(PATCH_DETECT, return_value={}),
        patch(PATCH_CLIENT, return_value=_mock_client([])),
        patch(PATCH_SETUP, return_value=True),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result_final = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=VALID_USER_INPUT
        )

    assert result_final["type"] == FlowResultType.CREATE_ENTRY
    assert result_final["data"][CONF_URL] == VALID_URL


async def test_flow_already_configured(hass: HomeAssistant) -> None:
    """Second config attempt → abort already_configured."""
    with (
        patch(PATCH_DETECT, return_value={}),
        patch(PATCH_CLIENT, return_value=_mock_client([])),
        patch(PATCH_SETUP, return_value=True),
    ):
        r1 = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        await hass.config_entries.flow.async_configure(
            r1["flow_id"], user_input=VALID_USER_INPUT
        )

    r2 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert r2["type"] == FlowResultType.ABORT
    assert r2["reason"] == "already_configured"


async def _create_entry(hass: HomeAssistant) -> str:
    """Helper: create a valid config entry and return its entry_id."""
    with (
        patch(PATCH_DETECT, return_value={}),
        patch(PATCH_CLIENT, return_value=_mock_client(CAMERAS_LIST)),
        patch(PATCH_SETUP, return_value=True),
    ):
        r = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        await hass.config_entries.flow.async_configure(
            r["flow_id"], user_input=VALID_USER_INPUT
        )
    # Get the real entry_id from the HA registry
    entries = hass.config_entries.async_entries(DOMAIN)
    assert entries, "Config entry not created"
    return entries[0].entry_id


# ---------------------------------------------------------------------------
# Subentry tests — add camera (5-step flow)
# ---------------------------------------------------------------------------


async def test_subentry_affiche_formulaire_camera(hass: HomeAssistant) -> None:
    """The camera add form (step user) is displayed with the camera list."""
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


async def test_subentry_step_user_mene_a_configure(hass: HomeAssistant) -> None:
    """Camera selection → step configure is displayed."""
    entry_id = await _create_entry(hass)

    with (
        patch(PATCH_CLIENT, return_value=_mock_client(CAMERAS_LIST)),
        patch(PATCH_NOTIFY, return_value=[PERSISTENT_NOTIFICATION]),
        patch(PATCH_GET_CAM_CONFIG, new_callable=AsyncMock, return_value=CAM_CONFIG_DEFAULT),
    ):
        r = await hass.config_entries.subentries.async_init(
            (entry_id, SUBENTRY_TYPE_CAMERA),
            context={"source": config_entries.SOURCE_USER},
        )
        assert r["step_id"] == "user"
        r2 = await hass.config_entries.subentries.async_configure(
            r["flow_id"],
            user_input={CONF_CAMERA: "entree"},
        )

    assert r2["type"] == FlowResultType.FORM
    assert r2["step_id"] == "configure"


async def _complete_subentry_flow(
    hass: HomeAssistant,
    flow_id: str,
    *,
    notify_target: str = PERSISTENT_NOTIFICATION,
    zones: list[str] | None = None,
    labels: list[str] | None = None,
    disabled_hours: list[str] | None = None,
    severity: list[str] | None = None,
    cooldown: int = DEFAULT_THROTTLE_COOLDOWN,
    debounce: int = DEFAULT_DEBOUNCE,
    tap_action: str = "clip",
    notif_title: str = "",
    notif_message: str = "",
    critical_template: str = "false",
) -> dict:
    """Helper: complete steps 2 to 5 of the subentry flow."""
    # Step 2 — configure (notification service)
    r = await hass.config_entries.subentries.async_configure(
        flow_id,
        user_input={CONF_NOTIFY_TARGET: notify_target},
    )
    assert r["step_id"] == "configure_filters"

    # Step 3 — configure_filters
    r = await hass.config_entries.subentries.async_configure(
        flow_id,
        user_input={
            CONF_ZONES: zones or [],
            CONF_LABELS: labels or [],
            CONF_DISABLED_HOURS: disabled_hours or [],
            CONF_SEVERITY: severity or DEFAULT_SEVERITY,
        },
    )
    assert r["step_id"] == "configure_behavior"

    # Step 4 — configure_behavior
    r = await hass.config_entries.subentries.async_configure(
        flow_id,
        user_input={
            CONF_COOLDOWN: cooldown,
            CONF_DEBOUNCE: debounce,
            CONF_TAP_ACTION: tap_action,
        },
    )
    assert r["step_id"] == "configure_notifications"

    # Step 5 — configure_notifications (last)
    return await hass.config_entries.subentries.async_configure(
        flow_id,
        user_input={
            CONF_NOTIF_TITLE: notif_title,
            CONF_NOTIF_MESSAGE: notif_message,
            CONF_CRITICAL_TEMPLATE: critical_template,
            "critical_template_custom": "",
        },
    )


async def test_subentry_cree_camera(hass: HomeAssistant) -> None:
    """Adding a camera in 5 steps → subentry created with the correct data."""
    entry_id = await _create_entry(hass)

    with (
        patch(PATCH_CLIENT, return_value=_mock_client(CAMERAS_LIST)),
        patch(PATCH_NOTIFY, return_value=[PERSISTENT_NOTIFICATION]),
        patch(PATCH_GET_CAM_CONFIG, new_callable=AsyncMock, return_value=CAM_CONFIG_DEFAULT),
        patch(PATCH_SETUP, return_value=True),
    ):
        r = await hass.config_entries.subentries.async_init(
            (entry_id, SUBENTRY_TYPE_CAMERA),
            context={"source": config_entries.SOURCE_USER},
        )
        # Step 1: choose the camera
        r2 = await hass.config_entries.subentries.async_configure(
            r["flow_id"],
            user_input={CONF_CAMERA: "entree"},
        )
        assert r2["step_id"] == "configure"
        # Steps 2 to 5
        r_final = await _complete_subentry_flow(hass, r2["flow_id"])

    assert r_final["type"] == FlowResultType.CREATE_ENTRY
    assert r_final["title"] == "Caméra entree"


async def test_subentry_cree_camera_avec_zones_labels_multiselect(hass: HomeAssistant) -> None:
    """Zones and labels selected via multi-select → stored as list[str]."""
    entry_id = await _create_entry(hass)

    # _mock_client already returns CAM_CONFIG_DEFAULT for get_camera_config
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
            user_input={CONF_CAMERA: "entree"},
        )
        r_final = await _complete_subentry_flow(
            hass, r2["flow_id"],
            zones=["jardin", "rue"],
            labels=["person"],
            disabled_hours=["0", "1", "2"],
        )

    assert r_final["type"] == FlowResultType.CREATE_ENTRY
    assert r_final["data"][CONF_ZONES] == ["jardin", "rue"]
    assert r_final["data"][CONF_LABELS] == ["person"]
    assert r_final["data"][CONF_DISABLED_HOURS] == [0, 1, 2]


async def test_subentry_cree_camera_fallback_zones_vides(hass: HomeAssistant) -> None:
    """If Frigate returns empty zones/labels → free text field (CSV)."""
    entry_id = await _create_entry(hass)

    # Mock client that returns CAM_CONFIG_EMPTY for get_camera_config
    mock_empty = _mock_client(CAMERAS_LIST)
    mock_empty.get_camera_config = AsyncMock(return_value=CAM_CONFIG_EMPTY)

    with (
        patch(PATCH_CLIENT, return_value=mock_empty),
        patch(PATCH_NOTIFY, return_value=[PERSISTENT_NOTIFICATION]),
        patch(PATCH_SETUP, return_value=True),
    ):
        r = await hass.config_entries.subentries.async_init(
            (entry_id, SUBENTRY_TYPE_CAMERA),
            context={"source": config_entries.SOURCE_USER},
        )
        r2 = await hass.config_entries.subentries.async_configure(
            r["flow_id"],
            user_input={CONF_CAMERA: "entree"},
        )
        # Step 2 — configure
        r3 = await hass.config_entries.subentries.async_configure(
            r2["flow_id"],
            user_input={CONF_NOTIFY_TARGET: PERSISTENT_NOTIFICATION},
        )
        assert r3["step_id"] == "configure_filters"
        # Step 3 — configure_filters with free text fields (empty zones/labels → str)
        r4 = await hass.config_entries.subentries.async_configure(
            r3["flow_id"],
            user_input={
                CONF_ZONES: "jardin,rue",
                CONF_LABELS: "person,car",
                CONF_DISABLED_HOURS: [],
                CONF_SEVERITY: DEFAULT_SEVERITY,
            },
        )
        assert r4["step_id"] == "configure_behavior"
        # Steps 4 and 5
        r5 = await hass.config_entries.subentries.async_configure(
            r4["flow_id"],
            user_input={
                CONF_COOLDOWN: DEFAULT_THROTTLE_COOLDOWN,
                CONF_DEBOUNCE: DEFAULT_DEBOUNCE,
                CONF_TAP_ACTION: "clip",
            },
        )
        r_final = await hass.config_entries.subentries.async_configure(
            r5["flow_id"],
            user_input={
                CONF_NOTIF_TITLE: "",
                CONF_NOTIF_MESSAGE: "",
                CONF_CRITICAL_TEMPLATE: "false",
                "critical_template_custom": "",
            },
        )

    assert r_final["type"] == FlowResultType.CREATE_ENTRY
    assert r_final["data"][CONF_ZONES] == ["jardin", "rue"]
    assert r_final["data"][CONF_LABELS] == ["person", "car"]


async def test_subentry_cree_camera_sans_filtres(hass: HomeAssistant) -> None:
    """Without filters, the lists are empty (accept everything)."""
    entry_id = await _create_entry(hass)

    with (
        patch(PATCH_CLIENT, return_value=_mock_client(CAMERAS_LIST)),
        patch(PATCH_NOTIFY, return_value=[PERSISTENT_NOTIFICATION]),
        patch(PATCH_GET_CAM_CONFIG, new_callable=AsyncMock, return_value=CAM_CONFIG_DEFAULT),
        patch(PATCH_SETUP, return_value=True),
    ):
        r = await hass.config_entries.subentries.async_init(
            (entry_id, SUBENTRY_TYPE_CAMERA),
            context={"source": config_entries.SOURCE_USER},
        )
        r2 = await hass.config_entries.subentries.async_configure(
            r["flow_id"],
            user_input={CONF_CAMERA: "entree"},
        )
        r_final = await _complete_subentry_flow(
            hass, r2["flow_id"],
            zones=[],
            labels=[],
            disabled_hours=[],
        )

    assert r_final["type"] == FlowResultType.CREATE_ENTRY
    assert r_final["data"][CONF_ZONES] == []
    assert r_final["data"][CONF_LABELS] == []
    assert r_final["data"][CONF_DISABLED_HOURS] == []


async def test_subentry_cameras_deja_configurees_exclues(hass: HomeAssistant) -> None:
    """Already configured cameras no longer appear in the list."""
    entry_id = await _create_entry(hass)

    # Add entree (5 steps)
    with (
        patch(PATCH_CLIENT, return_value=_mock_client(CAMERAS_LIST)),
        patch(PATCH_NOTIFY, return_value=[PERSISTENT_NOTIFICATION]),
        patch(PATCH_GET_CAM_CONFIG, new_callable=AsyncMock, return_value=CAM_CONFIG_DEFAULT),
        patch(PATCH_SETUP, return_value=True),
    ):
        r1 = await hass.config_entries.subentries.async_init(
            (entry_id, SUBENTRY_TYPE_CAMERA), context={"source": config_entries.SOURCE_USER}
        )
        r1b = await hass.config_entries.subentries.async_configure(
            r1["flow_id"],
            user_input={CONF_CAMERA: "entree"},
        )
        await _complete_subentry_flow(hass, r1b["flow_id"])

    # Try to add all cameras when they are all already configured
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
    """Network error when adding a camera → error displayed."""
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
# Constants tests
# ---------------------------------------------------------------------------


async def test_const_domain() -> None:
    """DOMAIN matches the folder name."""
    assert DOMAIN == "frigate_event_manager"


async def test_const_conf_url() -> None:
    assert CONF_URL == "url"


async def test_const_conf_camera() -> None:
    assert CONF_CAMERA == "camera"


async def test_const_persistent_notification() -> None:
    assert PERSISTENT_NOTIFICATION == "persistent_notification"




# ---------------------------------------------------------------------------
# Tests for _detect_frigate_config
# ---------------------------------------------------------------------------


async def test_detect_frigate_config_retourne_url_si_integration_presente(
    hass: HomeAssistant,
) -> None:
    """_detect_frigate_config returns url/user/password if Frigate integration is present."""
    from custom_components.frigate_event_manager.config_flow import _detect_frigate_config

    mock_entry = MagicMock()
    mock_entry.data = {"url": "http://frigate.local:5000", "username": "admin", "password": "secret"}

    with patch.object(hass.config_entries, "async_entries", return_value=[mock_entry]):
        result = _detect_frigate_config(hass)

    assert result["url"] == "http://frigate.local:5000"
    assert result["username"] == "admin"
    assert result["password"] == "secret"


async def test_detect_frigate_config_retourne_vide_si_absent(
    hass: HomeAssistant,
) -> None:
    """_detect_frigate_config returns empty dict if no Frigate integration is found."""
    from custom_components.frigate_event_manager.config_flow import _detect_frigate_config

    with patch.object(hass.config_entries, "async_entries", return_value=[]):
        result = _detect_frigate_config(hass)

    assert result == {}


async def test_detect_frigate_config_utilise_host_si_url_absent(
    hass: HomeAssistant,
) -> None:
    """_detect_frigate_config uses 'host' if 'url' is absent."""
    from custom_components.frigate_event_manager.config_flow import _detect_frigate_config

    mock_entry = MagicMock()
    mock_entry.data = {"host": "http://frigate.lan:5000"}

    with patch.object(hass.config_entries, "async_entries", return_value=[mock_entry]):
        result = _detect_frigate_config(hass)

    assert result["url"] == "http://frigate.lan:5000"


# ---------------------------------------------------------------------------
# Tests for _get_notify_options
# ---------------------------------------------------------------------------


async def test_get_notify_options_contient_persistent_notification(
    hass: HomeAssistant,
) -> None:
    """_get_notify_options always returns persistent_notification first."""
    from custom_components.frigate_event_manager.config_flow import _get_notify_options

    # Create a hass-like object with a mockable async_services_for_domain
    mock_hass = MagicMock()
    mock_hass.services.async_services_for_domain.return_value = {
        "mobile_app_iphone": {},
        "persistent_notification": {},
    }

    options = _get_notify_options(mock_hass)

    assert options[0] == PERSISTENT_NOTIFICATION
    assert "notify.mobile_app_iphone" in options
    # persistent_notification must be excluded from the "notify." prefix
    assert "notify.persistent_notification" not in options


async def test_get_notify_options_sans_services_retourne_persistent(
    hass: HomeAssistant,
) -> None:
    """Without notify services → only persistent_notification."""
    from custom_components.frigate_event_manager.config_flow import _get_notify_options

    mock_hass = MagicMock()
    mock_hass.services.async_services_for_domain.return_value = {}

    options = _get_notify_options(mock_hass)

    assert options == [PERSISTENT_NOTIFICATION]


# ---------------------------------------------------------------------------
# Tests step_user — invalid_auth (401)
# ---------------------------------------------------------------------------


async def test_step_user_invalid_auth(hass: HomeAssistant) -> None:
    """401 error → invalid_auth in errors."""
    import aiohttp

    err = aiohttp.ClientResponseError(request_info=MagicMock(), history=(), status=401)
    mock = _mock_client()
    mock.get_cameras.side_effect = err

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
    assert result2["errors"]["base"] == "invalid_auth"


# ---------------------------------------------------------------------------
# Tests async_step_reconfigure (main flow)
# ---------------------------------------------------------------------------


async def test_step_reconfigure_affiche_formulaire(hass: HomeAssistant) -> None:
    """Reconfigure displays a form with the current data."""
    entry_id = await _create_entry(hass)
    with patch(PATCH_CLIENT, return_value=_mock_client([])):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_RECONFIGURE, "entry_id": entry_id},
        )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "reconfigure"


async def test_step_reconfigure_met_a_jour_entry(hass: HomeAssistant) -> None:
    """Reconfigure with valid input updates the entry."""
    entry_id = await _create_entry(hass)

    new_url = "http://frigate-new.local:5000"
    with (
        patch(PATCH_CLIENT, return_value=_mock_client([])),
        patch(PATCH_SETUP, return_value=True),
    ):
        r = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_RECONFIGURE, "entry_id": entry_id},
        )
        r2 = await hass.config_entries.flow.async_configure(
            r["flow_id"],
            user_input={CONF_URL: new_url, CONF_USERNAME: "", CONF_PASSWORD: ""},
        )

    assert r2["type"] == FlowResultType.ABORT
    assert r2["reason"] == "reconfigure_successful"


async def test_step_reconfigure_cannot_connect(hass: HomeAssistant) -> None:
    """Reconfigure with Frigate unreachable → cannot_connect."""
    import aiohttp

    entry_id = await _create_entry(hass)

    mock = _mock_client()
    mock.get_cameras.side_effect = aiohttp.ClientError

    with patch(PATCH_CLIENT, return_value=mock):
        r = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_RECONFIGURE, "entry_id": entry_id},
        )
        r2 = await hass.config_entries.flow.async_configure(
            r["flow_id"],
            user_input={CONF_URL: VALID_URL, CONF_USERNAME: "", CONF_PASSWORD: ""},
        )

    assert r2["type"] == FlowResultType.FORM
    assert r2["errors"]["base"] == "cannot_connect"


async def test_step_reconfigure_invalid_auth(hass: HomeAssistant) -> None:
    """Reconfigure with 401 error → invalid_auth."""
    import aiohttp

    entry_id = await _create_entry(hass)

    err = aiohttp.ClientResponseError(request_info=MagicMock(), history=(), status=401)
    mock = _mock_client()
    mock.get_cameras.side_effect = err

    with patch(PATCH_CLIENT, return_value=mock):
        r = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_RECONFIGURE, "entry_id": entry_id},
        )
        r2 = await hass.config_entries.flow.async_configure(
            r["flow_id"],
            user_input={CONF_URL: VALID_URL, CONF_USERNAME: "", CONF_PASSWORD: ""},
        )

    assert r2["type"] == FlowResultType.FORM
    assert r2["errors"]["base"] == "invalid_auth"


# ---------------------------------------------------------------------------
# Tests subentry — invalid_auth (401)
# ---------------------------------------------------------------------------


async def test_subentry_invalid_auth(hass: HomeAssistant) -> None:
    """401 error when adding a camera → invalid_auth."""
    import aiohttp

    entry_id = await _create_entry(hass)

    err = aiohttp.ClientResponseError(request_info=MagicMock(), history=(), status=401)
    mock = _mock_client()
    mock.get_cameras.side_effect = err

    with (
        patch(PATCH_CLIENT, return_value=mock),
        patch(PATCH_NOTIFY, return_value=[PERSISTENT_NOTIFICATION]),
    ):
        result = await hass.config_entries.subentries.async_init(
            (entry_id, SUBENTRY_TYPE_CAMERA), context={"source": config_entries.SOURCE_USER}
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["base"] == "invalid_auth"


# ---------------------------------------------------------------------------
# Tests subentry — async_step_reconfigure (multi-step)
# ---------------------------------------------------------------------------


def _get_subentry_id(hass: HomeAssistant, entry_id: str) -> str:
    """Return the subentry_id of the first subentry of the entry."""
    entry = hass.config_entries.async_get_entry(entry_id)
    assert entry is not None
    subentry_ids = list(entry.subentries.keys())
    assert subentry_ids, "No subentry found"
    return subentry_ids[0]


async def _create_subentry(hass: HomeAssistant, entry_id: str, camera: str = "entree") -> str:
    """Helper: create a camera subentry and return its subentry_id."""
    with (
        patch(PATCH_CLIENT, return_value=_mock_client(CAMERAS_LIST)),
        patch(PATCH_NOTIFY, return_value=[PERSISTENT_NOTIFICATION]),
        patch(PATCH_GET_CAM_CONFIG, new_callable=AsyncMock, return_value=CAM_CONFIG_DEFAULT),
        patch(PATCH_SETUP, return_value=True),
    ):
        r = await hass.config_entries.subentries.async_init(
            (entry_id, SUBENTRY_TYPE_CAMERA), context={"source": config_entries.SOURCE_USER}
        )
        r2 = await hass.config_entries.subentries.async_configure(
            r["flow_id"],
            user_input={CONF_CAMERA: camera},
        )
        r_final = await _complete_subentry_flow(hass, r2["flow_id"])
    assert r_final["type"] == FlowResultType.CREATE_ENTRY
    return _get_subentry_id(hass, entry_id)


async def _complete_reconfigure_flow(
    hass: HomeAssistant,
    flow_id: str,
    *,
    notify_target: str = PERSISTENT_NOTIFICATION,
    zones: list[str] | None = None,
    labels: list[str] | None = None,
    disabled_hours: list[str] | None = None,
    severity: list[str] | None = None,
    cooldown: int = DEFAULT_THROTTLE_COOLDOWN,
    debounce: int = DEFAULT_DEBOUNCE,
    tap_action: str = "clip",
    notif_title: str = "",
    notif_message: str = "",
    critical_template: str = "false",
) -> dict:
    """Helper: complete the reconfiguration steps."""
    # Step 1 reconfigure — notify_target
    r = await hass.config_entries.subentries.async_configure(
        flow_id,
        user_input={CONF_NOTIFY_TARGET: notify_target},
    )
    assert r["step_id"] == "reconfigure_filters"

    # Step 2 reconfigure — filters
    r = await hass.config_entries.subentries.async_configure(
        flow_id,
        user_input={
            CONF_ZONES: zones or [],
            CONF_LABELS: labels or [],
            CONF_DISABLED_HOURS: disabled_hours or [],
            CONF_SEVERITY: severity or DEFAULT_SEVERITY,
        },
    )
    assert r["step_id"] == "reconfigure_behavior"

    # Step 3 reconfigure — behavior
    r = await hass.config_entries.subentries.async_configure(
        flow_id,
        user_input={
            CONF_COOLDOWN: cooldown,
            CONF_DEBOUNCE: debounce,
            CONF_TAP_ACTION: tap_action,
        },
    )
    assert r["step_id"] == "reconfigure_notifications"

    # Step 4 reconfigure — notifications (last)
    return await hass.config_entries.subentries.async_configure(
        flow_id,
        user_input={
            CONF_NOTIF_TITLE: notif_title,
            CONF_NOTIF_MESSAGE: notif_message,
            CONF_CRITICAL_TEMPLATE: critical_template,
            "critical_template_custom": "",
        },
    )


async def test_subentry_erreur_reseau_sur_step_configure_fallback(hass: HomeAssistant) -> None:
    """Network error on get_camera_config in step_configure → text field fallback, form displayed."""
    import aiohttp

    entry_id = await _create_entry(hass)

    mock = _mock_client(CAMERAS_LIST)
    mock.get_camera_config = AsyncMock(side_effect=aiohttp.ClientError)

    with (
        patch(PATCH_CLIENT, return_value=mock),
        patch(PATCH_NOTIFY, return_value=[PERSISTENT_NOTIFICATION]),
        patch(PATCH_SETUP, return_value=True),
    ):
        r = await hass.config_entries.subentries.async_init(
            (entry_id, SUBENTRY_TYPE_CAMERA),
            context={"source": config_entries.SOURCE_USER},
        )
        r2 = await hass.config_entries.subentries.async_configure(
            r["flow_id"],
            user_input={CONF_CAMERA: "entree"},
        )

    # The configure form is displayed anyway (fallback empty zones/labels)
    assert r2["type"] == FlowResultType.FORM
    assert r2["step_id"] == "configure"


async def test_subentry_reconfigure_affiche_formulaire(hass: HomeAssistant) -> None:
    """Reconfigure camera subentry displays the pre-filled form."""
    entry_id = await _create_entry(hass)
    subentry_id = await _create_subentry(hass, entry_id)

    with (
        patch(PATCH_NOTIFY, return_value=[PERSISTENT_NOTIFICATION]),
        patch(PATCH_GET_CAM_CONFIG, new_callable=AsyncMock, return_value=CAM_CONFIG_DEFAULT),
    ):
        r3 = await hass.config_entries.subentries.async_init(
            (entry_id, SUBENTRY_TYPE_CAMERA),
            context={
                "source": config_entries.SOURCE_RECONFIGURE,
                "subentry_id": subentry_id,
            },
        )

    assert r3["type"] == FlowResultType.FORM
    assert r3["step_id"] == "reconfigure"


async def test_subentry_reconfigure_met_a_jour_donnees(hass: HomeAssistant) -> None:
    """Reconfigure subentry with valid input → data updated."""
    entry_id = await _create_entry(hass)
    subentry_id = await _create_subentry(hass, entry_id)

    with (
        patch(PATCH_NOTIFY, return_value=[PERSISTENT_NOTIFICATION]),
        patch(PATCH_GET_CAM_CONFIG, new_callable=AsyncMock, return_value=CAM_CONFIG_DEFAULT),
        patch(PATCH_SETUP, return_value=True),
    ):
        r3 = await hass.config_entries.subentries.async_init(
            (entry_id, SUBENTRY_TYPE_CAMERA),
            context={
                "source": config_entries.SOURCE_RECONFIGURE,
                "subentry_id": subentry_id,
            },
        )
        r_final = await _complete_reconfigure_flow(
            hass, r3["flow_id"],
            zones=["jardin", "rue"],
            labels=["person"],
            disabled_hours=["0", "1"],
        )

    assert r_final["type"] == FlowResultType.ABORT
    assert r_final["reason"] == "reconfigure_successful"


async def test_subentry_reconfigure_met_a_jour_avec_zones_vides(hass: HomeAssistant) -> None:
    """Reconfigure with empty Frigate zones → free CSV text field."""
    entry_id = await _create_entry(hass)
    subentry_id = await _create_subentry(hass, entry_id)

    with (
        patch(PATCH_NOTIFY, return_value=[PERSISTENT_NOTIFICATION]),
        patch(PATCH_GET_CAM_CONFIG, new_callable=AsyncMock, return_value=CAM_CONFIG_EMPTY),
        patch(PATCH_SETUP, return_value=True),
    ):
        r3 = await hass.config_entries.subentries.async_init(
            (entry_id, SUBENTRY_TYPE_CAMERA),
            context={
                "source": config_entries.SOURCE_RECONFIGURE,
                "subentry_id": subentry_id,
            },
        )
        # Step 1 reconfigure
        r4 = await hass.config_entries.subentries.async_configure(
            r3["flow_id"],
            user_input={CONF_NOTIFY_TARGET: PERSISTENT_NOTIFICATION},
        )
        assert r4["step_id"] == "reconfigure_filters"
        # Step 2 reconfigure — free text fields (empty zones/labels)
        r5 = await hass.config_entries.subentries.async_configure(
            r4["flow_id"],
            user_input={
                CONF_ZONES: "jardin",
                CONF_LABELS: "person,car",
                CONF_DISABLED_HOURS: [],
                CONF_SEVERITY: DEFAULT_SEVERITY,
            },
        )
        assert r5["step_id"] == "reconfigure_behavior"
        r6 = await hass.config_entries.subentries.async_configure(
            r5["flow_id"],
            user_input={
                CONF_COOLDOWN: DEFAULT_THROTTLE_COOLDOWN,
                CONF_DEBOUNCE: DEFAULT_DEBOUNCE,
                CONF_TAP_ACTION: "clip",
            },
        )
        r_final = await hass.config_entries.subentries.async_configure(
            r6["flow_id"],
            user_input={
                CONF_NOTIF_TITLE: "",
                CONF_NOTIF_MESSAGE: "",
                CONF_CRITICAL_TEMPLATE: "false",
                "critical_template_custom": "",
            },
        )

    assert r_final["type"] == FlowResultType.ABORT
    assert r_final["reason"] == "reconfigure_successful"


async def test_subentry_reconfigure_erreur_reseau_get_camera_config(hass: HomeAssistant) -> None:
    """Network error on get_camera_config → silent fallback, form displayed."""
    import aiohttp

    entry_id = await _create_entry(hass)
    subentry_id = await _create_subentry(hass, entry_id)

    with (
        patch(PATCH_NOTIFY, return_value=[PERSISTENT_NOTIFICATION]),
        patch(
            PATCH_GET_CAM_CONFIG,
            new_callable=AsyncMock,
            side_effect=aiohttp.ClientError,
        ),
    ):
        r3 = await hass.config_entries.subentries.async_init(
            (entry_id, SUBENTRY_TYPE_CAMERA),
            context={
                "source": config_entries.SOURCE_RECONFIGURE,
                "subentry_id": subentry_id,
            },
        )

    # The form is displayed anyway (text field fallback)
    assert r3["type"] == FlowResultType.FORM
    assert r3["step_id"] == "reconfigure"


# ---------------------------------------------------------------------------
# Tests subentry — multi-screen config flow T-533
# ---------------------------------------------------------------------------


async def test_subentry_cree_camera_champs_config_flow(hass: HomeAssistant) -> None:
    """The severity, cooldown, debounce, tap_action, templates fields are in the flow (T-533).

    These parameters are now managed in the multi-screen config flow.
    """
    entry_id = await _create_entry(hass)

    with (
        patch(PATCH_CLIENT, return_value=_mock_client(CAMERAS_LIST)),
        patch(PATCH_NOTIFY, return_value=[PERSISTENT_NOTIFICATION]),
        patch(PATCH_GET_CAM_CONFIG, new_callable=AsyncMock, return_value=CAM_CONFIG_DEFAULT),
        patch(PATCH_SETUP, return_value=True),
    ):
        r = await hass.config_entries.subentries.async_init(
            (entry_id, SUBENTRY_TYPE_CAMERA),
            context={"source": config_entries.SOURCE_USER},
        )
        r2 = await hass.config_entries.subentries.async_configure(
            r["flow_id"],
            user_input={CONF_CAMERA: "entree"},
        )
        r_final = await _complete_subentry_flow(
            hass, r2["flow_id"],
            severity=["alert"],
            cooldown=120,
            debounce=5,
            tap_action="snapshot",
            notif_title="Alerte {{ camera }}",
            notif_message="{{ objects | join(', ') }}",
            critical_template="true",
        )

    assert r_final["type"] == FlowResultType.CREATE_ENTRY
    # The fields are now in the flow data (T-533)
    assert r_final["data"][CONF_SEVERITY] == ["alert"]
    assert r_final["data"][CONF_COOLDOWN] == 120
    assert r_final["data"][CONF_DEBOUNCE] == 5
    assert r_final["data"][CONF_TAP_ACTION] == "snapshot"
    assert r_final["data"][CONF_NOTIF_TITLE] == "Alerte {{ camera }}"
    assert r_final["data"][CONF_NOTIF_MESSAGE] == "{{ objects | join(', ') }}"
    assert r_final["data"][CONF_CRITICAL_TEMPLATE] == "true"


async def test_subentry_cree_camera_avec_severity_alert(hass: HomeAssistant) -> None:
    """Adding a camera with alert severity only."""
    entry_id = await _create_entry(hass)

    with (
        patch(PATCH_CLIENT, return_value=_mock_client(CAMERAS_LIST)),
        patch(PATCH_NOTIFY, return_value=[PERSISTENT_NOTIFICATION]),
        patch(PATCH_GET_CAM_CONFIG, new_callable=AsyncMock, return_value=CAM_CONFIG_DEFAULT),
        patch(PATCH_SETUP, return_value=True),
    ):
        r = await hass.config_entries.subentries.async_init(
            (entry_id, SUBENTRY_TYPE_CAMERA),
            context={"source": config_entries.SOURCE_USER},
        )
        r2 = await hass.config_entries.subentries.async_configure(
            r["flow_id"],
            user_input={CONF_CAMERA: "entree"},
        )
        r_final = await _complete_subentry_flow(hass, r2["flow_id"], severity=["alert"])

    assert r_final["type"] == FlowResultType.CREATE_ENTRY
    assert r_final["data"][CONF_SEVERITY] == ["alert"]


async def test_subentry_cree_camera_severity_defaut(hass: HomeAssistant) -> None:
    """Without severity in the input → default value (alert + detection)."""
    entry_id = await _create_entry(hass)

    with (
        patch(PATCH_CLIENT, return_value=_mock_client(CAMERAS_LIST)),
        patch(PATCH_NOTIFY, return_value=[PERSISTENT_NOTIFICATION]),
        patch(PATCH_GET_CAM_CONFIG, new_callable=AsyncMock, return_value=CAM_CONFIG_DEFAULT),
        patch(PATCH_SETUP, return_value=True),
    ):
        r = await hass.config_entries.subentries.async_init(
            (entry_id, SUBENTRY_TYPE_CAMERA),
            context={"source": config_entries.SOURCE_USER},
        )
        r2 = await hass.config_entries.subentries.async_configure(
            r["flow_id"],
            user_input={CONF_CAMERA: "entree"},
        )
        r_final = await _complete_subentry_flow(hass, r2["flow_id"])

    assert r_final["type"] == FlowResultType.CREATE_ENTRY
    assert sorted(r_final["data"][CONF_SEVERITY]) == sorted(DEFAULT_SEVERITY)


async def test_subentry_critical_template_preset_nuit(hass: HomeAssistant) -> None:
    """CONF_CRITICAL_TEMPLATE with night preset → Jinja2 template stored in subentry.data."""
    entry_id = await _create_entry(hass)

    night_jinja = "{{'false' if now().hour in [8,9,10,11,12,13,14,15,16,17,18] else 'true'}}"

    with (
        patch(PATCH_CLIENT, return_value=_mock_client(CAMERAS_LIST)),
        patch(PATCH_NOTIFY, return_value=[PERSISTENT_NOTIFICATION]),
        patch(PATCH_GET_CAM_CONFIG, new_callable=AsyncMock, return_value=CAM_CONFIG_DEFAULT),
        patch(PATCH_SETUP, return_value=True),
    ):
        r = await hass.config_entries.subentries.async_init(
            (entry_id, SUBENTRY_TYPE_CAMERA),
            context={"source": config_entries.SOURCE_USER},
        )
        r2 = await hass.config_entries.subentries.async_configure(
            r["flow_id"],
            user_input={CONF_CAMERA: "entree"},
        )
        r_final = await _complete_subentry_flow(hass, r2["flow_id"], critical_template="night_only")

    assert r_final["type"] == FlowResultType.CREATE_ENTRY
    assert r_final["data"][CONF_CRITICAL_TEMPLATE] == night_jinja


async def test_subentry_critical_template_custom(hass: HomeAssistant) -> None:
    """CONF_CRITICAL_TEMPLATE with custom option → uses critical_template_custom."""
    entry_id = await _create_entry(hass)

    with (
        patch(PATCH_CLIENT, return_value=_mock_client(CAMERAS_LIST)),
        patch(PATCH_NOTIFY, return_value=[PERSISTENT_NOTIFICATION]),
        patch(PATCH_GET_CAM_CONFIG, new_callable=AsyncMock, return_value=CAM_CONFIG_DEFAULT),
        patch(PATCH_SETUP, return_value=True),
    ):
        r = await hass.config_entries.subentries.async_init(
            (entry_id, SUBENTRY_TYPE_CAMERA),
            context={"source": config_entries.SOURCE_USER},
        )
        r2 = await hass.config_entries.subentries.async_configure(
            r["flow_id"],
            user_input={CONF_CAMERA: "entree"},
        )
        # Steps 2 to 4
        r3 = await hass.config_entries.subentries.async_configure(
            r2["flow_id"],
            user_input={CONF_NOTIFY_TARGET: PERSISTENT_NOTIFICATION},
        )
        r4 = await hass.config_entries.subentries.async_configure(
            r3["flow_id"],
            user_input={
                CONF_ZONES: [],
                CONF_LABELS: [],
                CONF_DISABLED_HOURS: [],
                CONF_SEVERITY: DEFAULT_SEVERITY,
            },
        )
        r5 = await hass.config_entries.subentries.async_configure(
            r4["flow_id"],
            user_input={
                CONF_COOLDOWN: DEFAULT_THROTTLE_COOLDOWN,
                CONF_DEBOUNCE: DEFAULT_DEBOUNCE,
                CONF_TAP_ACTION: "clip",
            },
        )
        # Step 5 — custom template
        r_final = await hass.config_entries.subentries.async_configure(
            r5["flow_id"],
            user_input={
                CONF_NOTIF_TITLE: "",
                CONF_NOTIF_MESSAGE: "",
                CONF_CRITICAL_TEMPLATE: "custom",
                "critical_template_custom": "{{ severity == 'alert' }}",
            },
        )

    assert r_final["type"] == FlowResultType.CREATE_ENTRY
    assert r_final["data"][CONF_CRITICAL_TEMPLATE] == "{{ severity == 'alert' }}"


async def test_subentry_reconfigure_sans_champs_entites(hass: HomeAssistant) -> None:
    """The multi-step reconfigure updates all configuration data."""
    entry_id = await _create_entry(hass)
    subentry_id = await _create_subentry(hass, entry_id)

    with (
        patch(PATCH_NOTIFY, return_value=[PERSISTENT_NOTIFICATION]),
        patch(PATCH_GET_CAM_CONFIG, new_callable=AsyncMock, return_value=CAM_CONFIG_DEFAULT),
        patch(PATCH_SETUP, return_value=True),
    ):
        r3 = await hass.config_entries.subentries.async_init(
            (entry_id, SUBENTRY_TYPE_CAMERA),
            context={
                "source": config_entries.SOURCE_RECONFIGURE,
                "subentry_id": subentry_id,
            },
        )
        r_final = await _complete_reconfigure_flow(
            hass, r3["flow_id"]
        )

    assert r_final["type"] == FlowResultType.ABORT
    assert r_final["reason"] == "reconfigure_successful"


async def test_subentry_reconfigure_critical_template_custom(hass: HomeAssistant) -> None:
    """Reconfigure with custom preset → uses critical_template_custom."""
    entry_id = await _create_entry(hass)
    subentry_id = await _create_subentry(hass, entry_id)

    with (
        patch(PATCH_NOTIFY, return_value=[PERSISTENT_NOTIFICATION]),
        patch(PATCH_GET_CAM_CONFIG, new_callable=AsyncMock, return_value=CAM_CONFIG_DEFAULT),
        patch(PATCH_SETUP, return_value=True),
    ):
        r3 = await hass.config_entries.subentries.async_init(
            (entry_id, SUBENTRY_TYPE_CAMERA),
            context={
                "source": config_entries.SOURCE_RECONFIGURE,
                "subentry_id": subentry_id,
            },
        )
        # Steps 1 to 3
        r4 = await hass.config_entries.subentries.async_configure(
            r3["flow_id"],
            user_input={CONF_NOTIFY_TARGET: PERSISTENT_NOTIFICATION},
        )
        r5 = await hass.config_entries.subentries.async_configure(
            r4["flow_id"],
            user_input={
                CONF_ZONES: [],
                CONF_LABELS: [],
                CONF_DISABLED_HOURS: [],
                CONF_SEVERITY: DEFAULT_SEVERITY,
            },
        )
        r6 = await hass.config_entries.subentries.async_configure(
            r5["flow_id"],
            user_input={
                CONF_COOLDOWN: DEFAULT_THROTTLE_COOLDOWN,
                CONF_DEBOUNCE: DEFAULT_DEBOUNCE,
                CONF_TAP_ACTION: "clip",
            },
        )
        # Step 4 reconfigure — notifications with custom preset
        r_final = await hass.config_entries.subentries.async_configure(
            r6["flow_id"],
            user_input={
                CONF_NOTIF_TITLE: "",
                CONF_NOTIF_MESSAGE: "",
                CONF_CRITICAL_TEMPLATE: "custom",
                "critical_template_custom": "{{ severity == 'alert' }}",
            },
        )

    assert r_final["type"] == FlowResultType.ABORT
    assert r_final["reason"] == "reconfigure_successful"


async def test_subentry_reconfigure_critical_template_preset_nuit(hass: HomeAssistant) -> None:
    """Reconfigure with night_only UI key → Jinja2 template stored."""
    entry_id = await _create_entry(hass)
    subentry_id = await _create_subentry(hass, entry_id)

    with (
        patch(PATCH_NOTIFY, return_value=[PERSISTENT_NOTIFICATION]),
        patch(PATCH_GET_CAM_CONFIG, new_callable=AsyncMock, return_value=CAM_CONFIG_DEFAULT),
        patch(PATCH_SETUP, return_value=True),
    ):
        r3 = await hass.config_entries.subentries.async_init(
            (entry_id, SUBENTRY_TYPE_CAMERA),
            context={
                "source": config_entries.SOURCE_RECONFIGURE,
                "subentry_id": subentry_id,
            },
        )
        r_final = await _complete_reconfigure_flow(
            hass, r3["flow_id"], critical_template="night_only"
        )

    assert r_final["type"] == FlowResultType.ABORT
    assert r_final["reason"] == "reconfigure_successful"


async def test_critical_template_to_preset_retourne_tpl_si_preset_connu() -> None:
    """_critical_template_to_preset maps night Jinja2 template → 'night_only' UI key."""
    from custom_components.frigate_event_manager.config_flow import (
        _critical_template_to_preset,
    )

    night_jinja = "{{'false' if now().hour in [8,9,10,11,12,13,14,15,16,17,18] else 'true'}}"
    assert _critical_template_to_preset(night_jinja) == "night_only"
    assert _critical_template_to_preset("true") == "true"
