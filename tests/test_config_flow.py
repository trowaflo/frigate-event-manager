"""Tests du config flow Frigate Event Manager — subentries."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.frigate_event_manager.const import (
    CONF_CAMERA,
    CONF_COOLDOWN,
    CONF_DEBOUNCE,
    CONF_DISABLED_HOURS,
    CONF_LABELS,
    CONF_NOTIFY_TARGET,
    CONF_PASSWORD,
    CONF_SILENT_DURATION,
    CONF_URL,
    CONF_USERNAME,
    CONF_ZONES,
    DEFAULT_DEBOUNCE,
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


async def test_subentry_cree_camera_avec_cooldown_debounce_silent(hass: HomeAssistant) -> None:
    """Ajout d'une caméra avec cooldown, debounce, silent_duration → données correctes."""
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
                CONF_CAMERA: "jardin",
                CONF_NOTIFY_TARGET: PERSISTENT_NOTIFICATION,
                CONF_COOLDOWN: 120,
                CONF_DEBOUNCE: 5,
                CONF_SILENT_DURATION: 60,
            },
        )

    assert r2["type"] == FlowResultType.CREATE_ENTRY
    assert r2["data"][CONF_COOLDOWN] == 120
    assert r2["data"][CONF_DEBOUNCE] == 5
    assert r2["data"][CONF_SILENT_DURATION] == 60


async def test_subentry_cooldown_debounce_valeurs_defaut(hass: HomeAssistant) -> None:
    """Sans cooldown/debounce/silent dans l'input → valeurs par défaut appliquées."""
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
                CONF_CAMERA: "garage",
                CONF_NOTIFY_TARGET: PERSISTENT_NOTIFICATION,
            },
        )

    assert r2["type"] == FlowResultType.CREATE_ENTRY
    assert r2["data"][CONF_COOLDOWN] == DEFAULT_THROTTLE_COOLDOWN
    assert r2["data"][CONF_DEBOUNCE] == DEFAULT_DEBOUNCE
    assert r2["data"][CONF_SILENT_DURATION] == DEFAULT_SILENT_DURATION


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


# ---------------------------------------------------------------------------
# Tests _parse_csv_int — edge cases
# ---------------------------------------------------------------------------


async def test_parse_csv_int_valeurs_invalides_retourne_liste_vide() -> None:
    """_parse_csv_int avec valeurs non-entières retourne liste vide."""
    from custom_components.frigate_event_manager.config_flow import _parse_csv_int

    result = _parse_csv_int("abc,xyz")
    assert result == []


async def test_parse_csv_int_chaine_vide_retourne_liste_vide() -> None:
    """_parse_csv_int avec chaîne vide retourne liste vide."""
    from custom_components.frigate_event_manager.config_flow import _parse_csv_int

    assert _parse_csv_int("") == []
    assert _parse_csv_int("   ") == []


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
# Tests subentry — async_step_reconfigure
# ---------------------------------------------------------------------------


def _get_subentry_id(hass: HomeAssistant, entry_id: str) -> str:
    """Récupère le subentry_id de la première subentry de l'entry."""
    entry = hass.config_entries.async_get_entry(entry_id)
    assert entry is not None
    subentry_ids = list(entry.subentries.keys())
    assert subentry_ids, "Aucune subentry trouvée"
    return subentry_ids[0]


async def test_subentry_reconfigure_affiche_formulaire(hass: HomeAssistant) -> None:
    """Reconfigure subentry caméra affiche le formulaire pré-rempli."""
    entry_id = await _create_entry(hass)

    # D'abord créer une subentry
    with (
        patch(PATCH_CLIENT, return_value=_mock_client(CAMERAS_LIST)),
        patch(PATCH_NOTIFY, return_value=[PERSISTENT_NOTIFICATION]),
        patch(PATCH_SETUP, return_value=True),
    ):
        r = await hass.config_entries.subentries.async_init(
            (entry_id, SUBENTRY_TYPE_CAMERA), context={"source": config_entries.SOURCE_USER}
        )
        r2 = await hass.config_entries.subentries.async_configure(
            r["flow_id"],
            user_input={CONF_CAMERA: "entree", CONF_NOTIFY_TARGET: PERSISTENT_NOTIFICATION},
        )
    assert r2["type"] == FlowResultType.CREATE_ENTRY

    # Récupérer l'id depuis le registre HA
    subentry_id = _get_subentry_id(hass, entry_id)

    # Reconfigurer la subentry
    with patch(PATCH_NOTIFY, return_value=[PERSISTENT_NOTIFICATION]):
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

    # Créer une subentry
    with (
        patch(PATCH_CLIENT, return_value=_mock_client(CAMERAS_LIST)),
        patch(PATCH_NOTIFY, return_value=[PERSISTENT_NOTIFICATION]),
        patch(PATCH_SETUP, return_value=True),
    ):
        r = await hass.config_entries.subentries.async_init(
            (entry_id, SUBENTRY_TYPE_CAMERA), context={"source": config_entries.SOURCE_USER}
        )
        r2 = await hass.config_entries.subentries.async_configure(
            r["flow_id"],
            user_input={CONF_CAMERA: "entree", CONF_NOTIFY_TARGET: PERSISTENT_NOTIFICATION},
        )
    assert r2["type"] == FlowResultType.CREATE_ENTRY
    subentry_id = _get_subentry_id(hass, entry_id)

    # Reconfigurer
    with (
        patch(PATCH_NOTIFY, return_value=[PERSISTENT_NOTIFICATION]),
        patch(PATCH_SETUP, return_value=True),
    ):
        r3 = await hass.config_entries.subentries.async_init(
            (entry_id, SUBENTRY_TYPE_CAMERA),
            context={
                "source": config_entries.SOURCE_RECONFIGURE,
                "subentry_id": subentry_id,
            },
        )
        r4 = await hass.config_entries.subentries.async_configure(
            r3["flow_id"],
            user_input={
                CONF_NOTIFY_TARGET: PERSISTENT_NOTIFICATION,
                CONF_ZONES: "jardin,rue",
                CONF_LABELS: "person",
                CONF_DISABLED_HOURS: "0,1",
                CONF_COOLDOWN: 90,
                CONF_DEBOUNCE: 3,
                CONF_SILENT_DURATION: 20,
            },
        )

    assert r4["type"] == FlowResultType.ABORT
    assert r4["reason"] == "reconfigure_successful"

