"""Tests du client HTTP Frigate."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from custom_components.frigate_event_manager.frigate_client import FrigateClient

# Cible de patch : aiohttp.ClientSession dans le module frigate_client
PATCH_CLIENT_SESSION = (
    "custom_components.frigate_event_manager.frigate_client.aiohttp.ClientSession"
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_response(json_data, status: int = 200) -> MagicMock:
    """Crée un mock de réponse aiohttp avec json() async."""
    response = MagicMock()
    response.status = status
    response.json = AsyncMock(return_value=json_data)
    response.raise_for_status = MagicMock()
    return response


def _make_session(response: MagicMock) -> MagicMock:
    """Crée un mock de ClientSession utilisant un context manager async."""
    session = MagicMock()
    cm_get = MagicMock()
    cm_get.__aenter__ = AsyncMock(return_value=response)
    cm_get.__aexit__ = AsyncMock(return_value=False)
    session.get = MagicMock(return_value=cm_get)

    cm_session = MagicMock()
    cm_session.__aenter__ = AsyncMock(return_value=session)
    cm_session.__aexit__ = AsyncMock(return_value=False)
    return cm_session


# ---------------------------------------------------------------------------
# Tests happy path
# ---------------------------------------------------------------------------


async def test_get_cameras_returns_camera_names() -> None:
    """Happy path : /api/config retourne un dict avec 'cameras' → get_cameras() retourne les noms."""
    api_response = {
        "cameras": {
            "jardin": {"fps": 5},
            "entree": {"fps": 10},
            "garage": {"fps": 5},
        }
    }
    response = _make_response(api_response)
    cm_session = _make_session(response)

    with patch(PATCH_CLIENT_SESSION, return_value=cm_session):
        client = FrigateClient("http://frigate.local:5000")
        cameras = await client.get_cameras()

    assert set(cameras) == {"jardin", "entree", "garage"}
    assert len(cameras) == 3


async def test_get_cameras_single_camera() -> None:
    """Une seule caméra dans la réponse → liste d'un élément."""
    api_response = {"cameras": {"salon": {"fps": 15}}}
    response = _make_response(api_response)
    cm_session = _make_session(response)

    with patch(PATCH_CLIENT_SESSION, return_value=cm_session):
        client = FrigateClient("http://frigate.local")
        cameras = await client.get_cameras()

    assert cameras == ["salon"]


async def test_get_cameras_strips_trailing_slash() -> None:
    """L'URL avec slash final ne duplique pas le séparateur dans le chemin."""
    api_response = {"cam1": {}}
    response = _make_response(api_response)
    captured_url: list[str] = []

    session = MagicMock()
    cm_get = MagicMock()
    cm_get.__aenter__ = AsyncMock(return_value=response)
    cm_get.__aexit__ = AsyncMock(return_value=False)

    def fake_get(url, **kwargs):
        captured_url.append(url)
        return cm_get

    session.get = fake_get
    cm_session = MagicMock()
    cm_session.__aenter__ = AsyncMock(return_value=session)
    cm_session.__aexit__ = AsyncMock(return_value=False)

    with patch(PATCH_CLIENT_SESSION, return_value=cm_session):
        client = FrigateClient("http://frigate.local:5000/")
        await client.get_cameras()

    assert captured_url[0] == "http://frigate.local:5000/api/config"


# ---------------------------------------------------------------------------
# Tests réponse non-dict
# ---------------------------------------------------------------------------


async def test_get_cameras_returns_empty_list_when_response_is_list() -> None:
    """Réponse JSON = liste → retourne [] (pas un dict)."""
    response = _make_response(["cam1", "cam2"])
    cm_session = _make_session(response)

    with patch(PATCH_CLIENT_SESSION, return_value=cm_session):
        client = FrigateClient("http://frigate.local")
        cameras = await client.get_cameras()

    assert cameras == []


async def test_get_cameras_returns_empty_list_when_response_is_string() -> None:
    """Réponse JSON = string → retourne []."""
    response = _make_response("not a dict")
    cm_session = _make_session(response)

    with patch(PATCH_CLIENT_SESSION, return_value=cm_session):
        client = FrigateClient("http://frigate.local")
        cameras = await client.get_cameras()

    assert cameras == []


async def test_get_cameras_returns_empty_list_when_response_is_none() -> None:
    """Réponse JSON = null → retourne []."""
    response = _make_response(None)
    cm_session = _make_session(response)

    with patch(PATCH_CLIENT_SESSION, return_value=cm_session):
        client = FrigateClient("http://frigate.local")
        cameras = await client.get_cameras()

    assert cameras == []


async def test_get_cameras_returns_empty_list_for_empty_dict() -> None:
    """Réponse JSON = dict vide → retourne liste vide."""
    response = _make_response({})
    cm_session = _make_session(response)

    with patch(PATCH_CLIENT_SESSION, return_value=cm_session):
        client = FrigateClient("http://frigate.local")
        cameras = await client.get_cameras()

    assert cameras == []


# ---------------------------------------------------------------------------
# Tests erreur réseau
# ---------------------------------------------------------------------------


async def test_get_cameras_propagates_client_connection_error() -> None:
    """aiohttp.ClientConnectionError (sous-classe ClientError) doit être propagée."""
    session = MagicMock()
    cm_get = MagicMock()
    cm_get.__aenter__ = AsyncMock(
        side_effect=aiohttp.ClientConnectionError("connexion refusée")
    )
    cm_get.__aexit__ = AsyncMock(return_value=False)
    session.get = MagicMock(return_value=cm_get)

    cm_session = MagicMock()
    cm_session.__aenter__ = AsyncMock(return_value=session)
    cm_session.__aexit__ = AsyncMock(return_value=False)

    with patch(PATCH_CLIENT_SESSION, return_value=cm_session):
        client = FrigateClient("http://frigate.local")
        with pytest.raises(aiohttp.ClientError):
            await client.get_cameras()


async def test_get_cameras_propagates_server_connection_error() -> None:
    """ServerConnectionError (sous-classe de ClientError) doit être propagée."""
    session = MagicMock()
    cm_get = MagicMock()
    cm_get.__aenter__ = AsyncMock(
        side_effect=aiohttp.ServerConnectionError("timeout")
    )
    cm_get.__aexit__ = AsyncMock(return_value=False)
    session.get = MagicMock(return_value=cm_get)

    cm_session = MagicMock()
    cm_session.__aenter__ = AsyncMock(return_value=session)
    cm_session.__aexit__ = AsyncMock(return_value=False)

    with patch(PATCH_CLIENT_SESSION, return_value=cm_session):
        client = FrigateClient("http://frigate.local")
        with pytest.raises(aiohttp.ClientError):
            await client.get_cameras()


async def test_get_cameras_propagates_raise_for_status_error() -> None:
    """raise_for_status() levant ClientResponseError doit être propagée."""
    response = MagicMock()
    response.raise_for_status = MagicMock(
        side_effect=aiohttp.ClientResponseError(MagicMock(), (), status=404)
    )
    response.json = AsyncMock(return_value={})
    cm_session = _make_session(response)

    with patch(PATCH_CLIENT_SESSION, return_value=cm_session):
        client = FrigateClient("http://frigate.local")
        with pytest.raises(aiohttp.ClientError):
            await client.get_cameras()


# ---------------------------------------------------------------------------
# Tests construction URL
# ---------------------------------------------------------------------------


async def test_get_cameras_correct_endpoint() -> None:
    """Le client appelle bien /api/config sur le bon host."""
    api_response = {"cameras": {"cam": {}}}
    response = _make_response(api_response)
    captured_url: list[str] = []

    session = MagicMock()
    cm_get = MagicMock()
    cm_get.__aenter__ = AsyncMock(return_value=response)
    cm_get.__aexit__ = AsyncMock(return_value=False)

    def fake_get(url, **kwargs):
        captured_url.append(url)
        return cm_get

    session.get = fake_get
    cm_session = MagicMock()
    cm_session.__aenter__ = AsyncMock(return_value=session)
    cm_session.__aexit__ = AsyncMock(return_value=False)

    with patch(PATCH_CLIENT_SESSION, return_value=cm_session):
        client = FrigateClient("http://192.168.1.100:5000")
        await client.get_cameras()

    assert captured_url[0] == "http://192.168.1.100:5000/api/config"


# ---------------------------------------------------------------------------
# Tests authentification — get_cameras avec credentials
# ---------------------------------------------------------------------------


def _make_session_with_login(
    login_response: MagicMock, config_response: MagicMock
) -> MagicMock:
    """Crée un mock de session qui renvoie login_response pour POST et config_response pour GET."""
    session = MagicMock()

    cm_login = MagicMock()
    cm_login.__aenter__ = AsyncMock(return_value=login_response)
    cm_login.__aexit__ = AsyncMock(return_value=False)
    session.post = MagicMock(return_value=cm_login)

    cm_config = MagicMock()
    cm_config.__aenter__ = AsyncMock(return_value=config_response)
    cm_config.__aexit__ = AsyncMock(return_value=False)
    session.get = MagicMock(return_value=cm_config)

    cm_session = MagicMock()
    cm_session.__aenter__ = AsyncMock(return_value=session)
    cm_session.__aexit__ = AsyncMock(return_value=False)
    return cm_session


async def test_get_cameras_avec_credentials_appelle_login() -> None:
    """Avec username, get_cameras() appelle POST /api/login avant GET /api/config."""
    # Réponse login avec cookie
    login_resp = MagicMock()
    login_resp.raise_for_status = MagicMock()
    token_cookie = MagicMock()
    token_cookie.value = "jwt_token_abc"
    login_resp.cookies = {"frigate_token": token_cookie}

    config_resp = _make_response({"cameras": {"cam": {}}})
    cm_session = _make_session_with_login(login_resp, config_resp)

    with patch(PATCH_CLIENT_SESSION, return_value=cm_session):
        client = FrigateClient("http://frigate.local", username="admin", password="secret")
        cameras = await client.get_cameras()

    assert cameras == ["cam"]
    cm_session.__aenter__.return_value.post.assert_called_once()


async def test_get_cameras_avec_credentials_sans_cookie_token() -> None:
    """Avec username mais sans cookie retourné → pas de header Cookie ajouté."""
    login_resp = MagicMock()
    login_resp.raise_for_status = MagicMock()
    login_resp.cookies = {}  # pas de frigate_token

    config_resp = _make_response({"cameras": {"jardin": {}}})
    cm_session = _make_session_with_login(login_resp, config_resp)

    with patch(PATCH_CLIENT_SESSION, return_value=cm_session):
        client = FrigateClient("http://frigate.local", username="admin", password="pass")
        cameras = await client.get_cameras()

    assert cameras == ["jardin"]


async def test_get_cameras_login_erreur_401_leve_client_response_error() -> None:
    """Login retourne 401 → raise_for_status lève ClientResponseError."""
    login_resp = MagicMock()
    login_resp.raise_for_status = MagicMock(
        side_effect=aiohttp.ClientResponseError(MagicMock(), (), status=401)
    )
    login_resp.cookies = {}

    config_resp = _make_response({})
    cm_session = _make_session_with_login(login_resp, config_resp)

    with patch(PATCH_CLIENT_SESSION, return_value=cm_session):
        client = FrigateClient("http://frigate.local", username="admin", password="mauvais")
        with pytest.raises(aiohttp.ClientError):
            await client.get_cameras()


# ---------------------------------------------------------------------------
# Tests get_media
# ---------------------------------------------------------------------------


def _make_media_response(content: bytes = b"data", content_type: str = "image/jpeg") -> MagicMock:
    """Crée un mock de réponse pour get_media."""
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.headers = {"Content-Type": content_type}
    resp.read = AsyncMock(return_value=content)
    return resp


def _make_session_for_media(resp: MagicMock) -> MagicMock:
    """Crée un mock de ClientSession pour get_media (sans login)."""
    session = MagicMock()
    cm_get = MagicMock()
    cm_get.__aenter__ = AsyncMock(return_value=resp)
    cm_get.__aexit__ = AsyncMock(return_value=False)
    session.get = MagicMock(return_value=cm_get)

    cm_session = MagicMock()
    cm_session.__aenter__ = AsyncMock(return_value=session)
    cm_session.__aexit__ = AsyncMock(return_value=False)
    return cm_session


async def test_get_media_retourne_contenu_et_content_type() -> None:
    """get_media() retourne (bytes, content_type) sur une réponse valide."""
    cm_session = _make_session_for_media(_make_media_response(b"image_data", "image/jpeg"))

    with patch(PATCH_CLIENT_SESSION, return_value=cm_session):
        client = FrigateClient("http://frigate.local")
        data, ct = await client.get_media("/api/events/abc/snapshot.jpg")

    assert data == b"image_data"
    assert ct == "image/jpeg"


async def test_get_media_content_type_defaut_si_absent() -> None:
    """get_media() retourne application/octet-stream si Content-Type absent."""
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.headers = {}  # pas de Content-Type
    resp.read = AsyncMock(return_value=b"binary")
    cm_session = _make_session_for_media(resp)

    with patch(PATCH_CLIENT_SESSION, return_value=cm_session):
        client = FrigateClient("http://frigate.local")
        data, ct = await client.get_media("/api/events/abc/clip.mp4")

    assert ct == "application/octet-stream"
    assert data == b"binary"


async def test_get_media_avec_credentials_appelle_login() -> None:
    """get_media() avec credentials appelle POST /api/login."""
    login_resp = MagicMock()
    login_resp.raise_for_status = MagicMock()
    token_cookie = MagicMock()
    token_cookie.value = "jwt_abc"
    login_resp.cookies = {"frigate_token": token_cookie}

    media_resp = _make_media_response(b"clip_data", "video/mp4")

    session = MagicMock()
    cm_login = MagicMock()
    cm_login.__aenter__ = AsyncMock(return_value=login_resp)
    cm_login.__aexit__ = AsyncMock(return_value=False)
    session.post = MagicMock(return_value=cm_login)

    cm_get = MagicMock()
    cm_get.__aenter__ = AsyncMock(return_value=media_resp)
    cm_get.__aexit__ = AsyncMock(return_value=False)
    session.get = MagicMock(return_value=cm_get)

    cm_session = MagicMock()
    cm_session.__aenter__ = AsyncMock(return_value=session)
    cm_session.__aexit__ = AsyncMock(return_value=False)

    with patch(PATCH_CLIENT_SESSION, return_value=cm_session):
        client = FrigateClient("http://frigate.local", username="admin", password="pass")
        data, ct = await client.get_media("/api/events/abc/clip.mp4")

    assert data == b"clip_data"
    assert ct == "video/mp4"
    session.post.assert_called_once()


async def test_get_media_erreur_reseau_propage_client_error() -> None:
    """get_media() propage aiohttp.ClientError en cas d'erreur réseau."""
    session = MagicMock()
    cm_get = MagicMock()
    cm_get.__aenter__ = AsyncMock(side_effect=aiohttp.ClientConnectionError("timeout"))
    cm_get.__aexit__ = AsyncMock(return_value=False)
    session.get = MagicMock(return_value=cm_get)

    cm_session = MagicMock()
    cm_session.__aenter__ = AsyncMock(return_value=session)
    cm_session.__aexit__ = AsyncMock(return_value=False)

    with patch(PATCH_CLIENT_SESSION, return_value=cm_session):
        client = FrigateClient("http://frigate.local")
        with pytest.raises(aiohttp.ClientError):
            await client.get_media("/api/events/abc/snapshot.jpg")


# ---------------------------------------------------------------------------
# Tests get_camera_config
# ---------------------------------------------------------------------------


async def test_get_camera_config_happy_path() -> None:
    """Happy path : retourne zones et labels de la caméra depuis /api/config."""
    api_response = {
        "cameras": {
            "jardin": {
                "zones": {"jardin_zone": {}, "rue": {}},
                "objects": {"track": ["person", "car"]},
            }
        }
    }
    response = _make_response(api_response)
    cm_session = _make_session(response)

    with patch(PATCH_CLIENT_SESSION, return_value=cm_session):
        client = FrigateClient("http://frigate.local:5000")
        result = await client.get_camera_config("jardin")

    assert set(result["zones"]) == {"jardin_zone", "rue"}
    assert result["labels"] == ["person", "car"]


async def test_get_camera_config_camera_absente_retourne_vide() -> None:
    """Caméra absente de la config Frigate → retourne zones et labels vides."""
    api_response = {
        "cameras": {
            "entree": {"zones": {}, "objects": {"track": ["person"]}},
        }
    }
    response = _make_response(api_response)
    cm_session = _make_session(response)

    with patch(PATCH_CLIENT_SESSION, return_value=cm_session):
        client = FrigateClient("http://frigate.local:5000")
        result = await client.get_camera_config("jardin")

    assert result == {"zones": [], "labels": []}


async def test_get_camera_config_erreur_reseau_leve_client_error() -> None:
    """Erreur réseau sur get_camera_config → lève aiohttp.ClientError."""
    session = MagicMock()
    cm_get = MagicMock()
    cm_get.__aenter__ = AsyncMock(
        side_effect=aiohttp.ClientConnectionError("connexion refusée")
    )
    cm_get.__aexit__ = AsyncMock(return_value=False)
    session.get = MagicMock(return_value=cm_get)

    cm_session = MagicMock()
    cm_session.__aenter__ = AsyncMock(return_value=session)
    cm_session.__aexit__ = AsyncMock(return_value=False)

    with patch(PATCH_CLIENT_SESSION, return_value=cm_session):
        client = FrigateClient("http://frigate.local")
        with pytest.raises(aiohttp.ClientError):
            await client.get_camera_config("jardin")
