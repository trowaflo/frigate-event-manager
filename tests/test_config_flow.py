"""Tests du config flow Frigate Event Manager — subentries (flow multi-écrans T-533)."""

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
    CONF_SILENT_DURATION,
    CONF_TAP_ACTION,
    CONF_URL,
    CONF_USERNAME,
    CONF_ZONES,
    DEFAULT_DEBOUNCE,
    DEFAULT_SEVERITY,
    DEFAULT_SILENT_DURATION,
    DEFAULT_THROTTLE_COOLDOWN,
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

# Réponse par défaut de get_camera_config
CAM_CONFIG_DEFAULT = {"zones": ["jardin", "rue"], "labels": ["person", "car"]}
CAM_CONFIG_EMPTY = {"zones": [], "labels": []}


def _mock_client(cameras: list[str] | None = None):
    """Retourne un mock FrigateClient."""
    m = AsyncMock()
    m.get_cameras = AsyncMock(return_value=cameras or [])
    m.get_camera_config = AsyncMock(return_value=CAM_CONFIG_DEFAULT)
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


async def test_step_user_valide_cree_entry(hass: HomeAssistant) -> None:
    """Connexion valide → entry créée directement (plus d'étape notify)."""
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
    # Pas de notify_target dans l'entry principale (feature 6)
    assert CONF_NOTIFY_TARGET not in result2["data"]


async def test_flow_complet_cree_entry(hass: HomeAssistant) -> None:
    """Flow (user) → entry créée avec les bonnes données."""
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
    """Deuxième tentative de config → abort already_configured."""
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
    """Helper : crée une config entry valide et retourne son entry_id."""
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
    # Récupère l'entry_id réel depuis le registre HA
    entries = hass.config_entries.async_entries(DOMAIN)
    assert entries, "Config entry non créée"
    return entries[0].entry_id


# ---------------------------------------------------------------------------
# Tests subentry — ajout caméra (flow 5 étapes)
# ---------------------------------------------------------------------------


async def test_subentry_affiche_formulaire_camera(hass: HomeAssistant) -> None:
    """Le formulaire d'ajout caméra (step user) s'affiche avec la liste des caméras."""
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
    """Sélection caméra → step configure s'affiche."""
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
    silent_duration: int = DEFAULT_SILENT_DURATION,
    tap_action: str = "clip",
    notif_title: str = "",
    notif_message: str = "",
    critical_template: str = "false",
) -> dict:
    """Helper : complète les étapes 2 à 5 du subentry flow."""
    # Étape 2 — configure (service de notification)
    r = await hass.config_entries.subentries.async_configure(
        flow_id,
        user_input={CONF_NOTIFY_TARGET: notify_target},
    )
    assert r["step_id"] == "configure_filters"

    # Étape 3 — configure_filters
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

    # Étape 4 — configure_behavior
    r = await hass.config_entries.subentries.async_configure(
        flow_id,
        user_input={
            CONF_COOLDOWN: cooldown,
            CONF_DEBOUNCE: debounce,
            CONF_SILENT_DURATION: silent_duration,
            CONF_TAP_ACTION: tap_action,
        },
    )
    assert r["step_id"] == "configure_notifications"

    # Étape 5 — configure_notifications (dernière)
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
    """Ajout d'une caméra en 5 étapes → subentry créée avec les bonnes données."""
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
        # Étape 1 : choisir la caméra
        r2 = await hass.config_entries.subentries.async_configure(
            r["flow_id"],
            user_input={CONF_CAMERA: "entree"},
        )
        assert r2["step_id"] == "configure"
        # Étapes 2 à 5
        r_final = await _complete_subentry_flow(hass, r2["flow_id"])

    assert r_final["type"] == FlowResultType.CREATE_ENTRY
    assert r_final["title"] == "Caméra entree"


async def test_subentry_cree_camera_avec_zones_labels_multiselect(hass: HomeAssistant) -> None:
    """Zones et labels sélectionnés via multi-select → stockés comme list[str]."""
    entry_id = await _create_entry(hass)

    # _mock_client retourne déjà CAM_CONFIG_DEFAULT pour get_camera_config
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
    """Si Frigate retourne zones/labels vides → champ texte libre (CSV)."""
    entry_id = await _create_entry(hass)

    # Mock client qui retourne CAM_CONFIG_EMPTY pour get_camera_config
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
        # Étape 2 — configure
        r3 = await hass.config_entries.subentries.async_configure(
            r2["flow_id"],
            user_input={CONF_NOTIFY_TARGET: PERSISTENT_NOTIFICATION},
        )
        assert r3["step_id"] == "configure_filters"
        # Étape 3 — configure_filters avec champs texte libre (zones/labels vides → str)
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
        # Étapes 4 et 5
        r5 = await hass.config_entries.subentries.async_configure(
            r4["flow_id"],
            user_input={
                CONF_COOLDOWN: DEFAULT_THROTTLE_COOLDOWN,
                CONF_DEBOUNCE: DEFAULT_DEBOUNCE,
                CONF_SILENT_DURATION: DEFAULT_SILENT_DURATION,
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
    """Sans filtres, les listes sont vides (tout accepter)."""
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


async def test_subentry_cree_camera_avec_silent_duration(hass: HomeAssistant) -> None:
    """Ajout d'une caméra avec silent_duration → données correctes."""
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
            user_input={CONF_CAMERA: "jardin"},
        )
        r_final = await _complete_subentry_flow(hass, r2["flow_id"], silent_duration=60)

    assert r_final["type"] == FlowResultType.CREATE_ENTRY
    assert r_final["data"][CONF_SILENT_DURATION] == 60


async def test_subentry_silent_duration_valeur_defaut(hass: HomeAssistant) -> None:
    """Sans silent_duration dans l'input → valeur par défaut appliquée."""
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
            user_input={CONF_CAMERA: "garage"},
        )
        r_final = await _complete_subentry_flow(hass, r2["flow_id"])

    assert r_final["type"] == FlowResultType.CREATE_ENTRY
    assert r_final["data"][CONF_SILENT_DURATION] == DEFAULT_SILENT_DURATION


async def test_subentry_cameras_deja_configurees_exclues(hass: HomeAssistant) -> None:
    """Les caméras déjà configurées n'apparaissent plus dans la liste."""
    entry_id = await _create_entry(hass)

    # Ajouter entree (5 étapes)
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
# Tests _detect_frigate_config
# ---------------------------------------------------------------------------


async def test_detect_frigate_config_retourne_url_si_integration_presente(
    hass: HomeAssistant,
) -> None:
    """_detect_frigate_config retourne url/user/password si intégration Frigate présente."""
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
    """_detect_frigate_config retourne dict vide si aucune intégration Frigate."""
    from custom_components.frigate_event_manager.config_flow import _detect_frigate_config

    with patch.object(hass.config_entries, "async_entries", return_value=[]):
        result = _detect_frigate_config(hass)

    assert result == {}


async def test_detect_frigate_config_utilise_host_si_url_absent(
    hass: HomeAssistant,
) -> None:
    """_detect_frigate_config utilise 'host' si 'url' absent."""
    from custom_components.frigate_event_manager.config_flow import _detect_frigate_config

    mock_entry = MagicMock()
    mock_entry.data = {"host": "http://frigate.lan:5000"}

    with patch.object(hass.config_entries, "async_entries", return_value=[mock_entry]):
        result = _detect_frigate_config(hass)

    assert result["url"] == "http://frigate.lan:5000"


# ---------------------------------------------------------------------------
# Tests _get_notify_options
# ---------------------------------------------------------------------------


async def test_get_notify_options_contient_persistent_notification(
    hass: HomeAssistant,
) -> None:
    """_get_notify_options retourne toujours persistent_notification en premier."""
    from custom_components.frigate_event_manager.config_flow import _get_notify_options

    # Créer un objet hass-like avec async_services_for_domain mockable
    mock_hass = MagicMock()
    mock_hass.services.async_services_for_domain.return_value = {
        "mobile_app_iphone": {},
        "persistent_notification": {},
    }

    options = _get_notify_options(mock_hass)

    assert options[0] == PERSISTENT_NOTIFICATION
    assert "notify.mobile_app_iphone" in options
    # persistent_notification doit être exclu du suffixe "notify."
    assert "notify.persistent_notification" not in options


async def test_get_notify_options_sans_services_retourne_persistent(
    hass: HomeAssistant,
) -> None:
    """Sans services notify → seulement persistent_notification."""
    from custom_components.frigate_event_manager.config_flow import _get_notify_options

    mock_hass = MagicMock()
    mock_hass.services.async_services_for_domain.return_value = {}

    options = _get_notify_options(mock_hass)

    assert options == [PERSISTENT_NOTIFICATION]


# ---------------------------------------------------------------------------
# Tests step_user — invalid_auth (401)
# ---------------------------------------------------------------------------


async def test_step_user_invalid_auth(hass: HomeAssistant) -> None:
    """Erreur 401 → invalid_auth dans errors."""
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
# Tests async_step_reconfigure (flow principal)
# ---------------------------------------------------------------------------


async def test_step_reconfigure_affiche_formulaire(hass: HomeAssistant) -> None:
    """Reconfigure affiche un formulaire avec les données actuelles."""
    entry_id = await _create_entry(hass)
    with patch(PATCH_CLIENT, return_value=_mock_client([])):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_RECONFIGURE, "entry_id": entry_id},
        )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "reconfigure"


async def test_step_reconfigure_met_a_jour_entry(hass: HomeAssistant) -> None:
    """Reconfigure avec input valide met à jour l'entry."""
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
    """Reconfigure avec Frigate inaccessible → cannot_connect."""
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
    """Reconfigure avec erreur 401 → invalid_auth."""
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
    """Erreur 401 lors de l'ajout de caméra → invalid_auth."""
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
# Tests subentry — async_step_reconfigure (multi-étapes)
# ---------------------------------------------------------------------------


def _get_subentry_id(hass: HomeAssistant, entry_id: str) -> str:
    """Récupère le subentry_id de la première subentry de l'entry."""
    entry = hass.config_entries.async_get_entry(entry_id)
    assert entry is not None
    subentry_ids = list(entry.subentries.keys())
    assert subentry_ids, "Aucune subentry trouvée"
    return subentry_ids[0]


async def _create_subentry(hass: HomeAssistant, entry_id: str, camera: str = "entree") -> str:
    """Helper : crée une subentry caméra et retourne son subentry_id."""
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
    silent_duration: int = DEFAULT_SILENT_DURATION,
    tap_action: str = "clip",
    notif_title: str = "",
    notif_message: str = "",
    critical_template: str = "false",
) -> dict:
    """Helper : complète les étapes de reconfiguration."""
    # Étape 1 reconfigure — notify_target
    r = await hass.config_entries.subentries.async_configure(
        flow_id,
        user_input={CONF_NOTIFY_TARGET: notify_target},
    )
    assert r["step_id"] == "reconfigure_filters"

    # Étape 2 reconfigure — filtres
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

    # Étape 3 reconfigure — comportement
    r = await hass.config_entries.subentries.async_configure(
        flow_id,
        user_input={
            CONF_COOLDOWN: cooldown,
            CONF_DEBOUNCE: debounce,
            CONF_SILENT_DURATION: silent_duration,
            CONF_TAP_ACTION: tap_action,
        },
    )
    assert r["step_id"] == "reconfigure_notifications"

    # Étape 4 reconfigure — notifications (dernière)
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
    """Erreur réseau sur get_camera_config en step_configure → fallback champ texte, formulaire affiché."""
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

    # Le formulaire configure s'affiche quand même (fallback zones/labels vides)
    assert r2["type"] == FlowResultType.FORM
    assert r2["step_id"] == "configure"


async def test_subentry_reconfigure_affiche_formulaire(hass: HomeAssistant) -> None:
    """Reconfigure subentry caméra affiche le formulaire pré-rempli."""
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
    """Reconfigure subentry avec input valide → données mises à jour."""
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
            silent_duration=20,
        )

    assert r_final["type"] == FlowResultType.ABORT
    assert r_final["reason"] == "reconfigure_successful"


async def test_subentry_reconfigure_met_a_jour_avec_zones_vides(hass: HomeAssistant) -> None:
    """Reconfigure avec zones Frigate vides → champ texte libre CSV."""
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
        # Étape 1 reconfigure
        r4 = await hass.config_entries.subentries.async_configure(
            r3["flow_id"],
            user_input={CONF_NOTIFY_TARGET: PERSISTENT_NOTIFICATION},
        )
        assert r4["step_id"] == "reconfigure_filters"
        # Étape 2 reconfigure — champs texte libre (zones/labels vides)
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
                CONF_SILENT_DURATION: 30,
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
    """Erreur réseau sur get_camera_config → fallback silencieux, formulaire affiché."""
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

    # Le formulaire s'affiche quand même (fallback champ texte)
    assert r3["type"] == FlowResultType.FORM
    assert r3["step_id"] == "reconfigure"


# ---------------------------------------------------------------------------
# Tests subentry — config flow multi-écrans T-533
# ---------------------------------------------------------------------------


async def test_subentry_cree_camera_champs_config_flow(hass: HomeAssistant) -> None:
    """Les champs severity, cooldown, debounce, tap_action, templates sont dans le flow (T-533).

    Ces paramètres sont désormais gérés dans le config flow multi-écrans.
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
    # Les champs sont maintenant dans les données du flow (T-533)
    assert r_final["data"][CONF_SEVERITY] == ["alert"]
    assert r_final["data"][CONF_COOLDOWN] == 120
    assert r_final["data"][CONF_DEBOUNCE] == 5
    assert r_final["data"][CONF_TAP_ACTION] == "snapshot"
    assert r_final["data"][CONF_NOTIF_TITLE] == "Alerte {{ camera }}"
    assert r_final["data"][CONF_NOTIF_MESSAGE] == "{{ objects | join(', ') }}"
    assert r_final["data"][CONF_CRITICAL_TEMPLATE] == "true"


async def test_subentry_cree_camera_avec_severity_alert(hass: HomeAssistant) -> None:
    """Ajout d'une caméra avec severity alert uniquement."""
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
    """Sans severity dans l'input → valeur par défaut (alert + detection)."""
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
    """CONF_CRITICAL_TEMPLATE avec preset nuit → stocké dans subentry.data."""
    entry_id = await _create_entry(hass)

    night_preset = "{{'false' if now().hour in [8,9,10,11,12,13,14,15,16,17,18] else 'true'}}"

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
        r_final = await _complete_subentry_flow(hass, r2["flow_id"], critical_template=night_preset)

    assert r_final["type"] == FlowResultType.CREATE_ENTRY
    assert r_final["data"][CONF_CRITICAL_TEMPLATE] == night_preset


async def test_subentry_critical_template_custom(hass: HomeAssistant) -> None:
    """CONF_CRITICAL_TEMPLATE avec option custom → utilise critical_template_custom."""
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
        # Étapes 2 à 4
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
                CONF_SILENT_DURATION: DEFAULT_SILENT_DURATION,
                CONF_TAP_ACTION: "clip",
            },
        )
        # Étape 5 — custom template
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
    """La reconfigure multi-étapes met à jour toutes les données de configuration."""
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
            hass, r3["flow_id"], silent_duration=30
        )

    assert r_final["type"] == FlowResultType.ABORT
    assert r_final["reason"] == "reconfigure_successful"
