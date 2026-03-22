"""Tests for the Frigate HTTP client."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from custom_components.frigate_event_manager.frigate_client import FrigateClient

# Patch target: aiohttp.ClientSession in the frigate_client module
PATCH_CLIENT_SESSION = (
    "custom_components.frigate_event_manager.frigate_client.aiohttp.ClientSession"
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_response(json_data, status: int = 200) -> MagicMock:
    """Create a mock aiohttp response with async json()."""
    response = MagicMock()
    response.status = status
    response.json = AsyncMock(return_value=json_data)
    response.raise_for_status = MagicMock()
    return response


def _make_session(response: MagicMock) -> MagicMock:
    """Create a mock ClientSession using an async context manager."""
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
# Happy path tests
# ---------------------------------------------------------------------------


async def test_get_cameras_returns_camera_names() -> None:
    """Happy path: /api/config returns a dict with 'cameras' → get_cameras() returns names."""
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
    """Single camera in response → list of one element."""
    api_response = {"cameras": {"salon": {"fps": 15}}}
    response = _make_response(api_response)
    cm_session = _make_session(response)

    with patch(PATCH_CLIENT_SESSION, return_value=cm_session):
        client = FrigateClient("http://frigate.local")
        cameras = await client.get_cameras()

    assert cameras == ["salon"]


async def test_get_cameras_strips_trailing_slash() -> None:
    """URL with trailing slash does not duplicate the separator in the path."""
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
# Non-dict response tests
# ---------------------------------------------------------------------------


async def test_get_cameras_returns_empty_list_when_response_is_list() -> None:
    """JSON response = list → returns [] (not a dict)."""
    response = _make_response(["cam1", "cam2"])
    cm_session = _make_session(response)

    with patch(PATCH_CLIENT_SESSION, return_value=cm_session):
        client = FrigateClient("http://frigate.local")
        cameras = await client.get_cameras()

    assert cameras == []


async def test_get_cameras_returns_empty_list_when_response_is_string() -> None:
    """JSON response = string → returns []."""
    response = _make_response("not a dict")
    cm_session = _make_session(response)

    with patch(PATCH_CLIENT_SESSION, return_value=cm_session):
        client = FrigateClient("http://frigate.local")
        cameras = await client.get_cameras()

    assert cameras == []


async def test_get_cameras_returns_empty_list_when_response_is_none() -> None:
    """JSON response = null → returns []."""
    response = _make_response(None)
    cm_session = _make_session(response)

    with patch(PATCH_CLIENT_SESSION, return_value=cm_session):
        client = FrigateClient("http://frigate.local")
        cameras = await client.get_cameras()

    assert cameras == []


async def test_get_cameras_returns_empty_list_for_empty_dict() -> None:
    """JSON response = empty dict → returns empty list."""
    response = _make_response({})
    cm_session = _make_session(response)

    with patch(PATCH_CLIENT_SESSION, return_value=cm_session):
        client = FrigateClient("http://frigate.local")
        cameras = await client.get_cameras()

    assert cameras == []


# ---------------------------------------------------------------------------
# Network error tests
# ---------------------------------------------------------------------------


async def test_get_cameras_propagates_client_connection_error() -> None:
    """aiohttp.ClientConnectionError (subclass of ClientError) must be propagated."""
    session = MagicMock()
    cm_get = MagicMock()
    cm_get.__aenter__ = AsyncMock(
        side_effect=aiohttp.ClientConnectionError("connection refused")
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
    """ServerConnectionError (subclass of ClientError) must be propagated."""
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
    """raise_for_status() raising ClientResponseError must be propagated."""
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
# URL construction tests
# ---------------------------------------------------------------------------


async def test_get_cameras_correct_endpoint() -> None:
    """Client calls /api/config on the correct host."""
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
# Authentication tests — get_cameras with credentials
# ---------------------------------------------------------------------------


def _make_session_with_login(
    login_response: MagicMock, config_response: MagicMock
) -> MagicMock:
    """Create a mock session that returns login_response for POST and config_response for GET."""
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
    """With username, get_cameras() calls POST /api/login before GET /api/config."""
    # Login response with cookie
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
    """With username but no cookie returned → no Cookie header added."""
    login_resp = MagicMock()
    login_resp.raise_for_status = MagicMock()
    login_resp.cookies = {}  # no frigate_token

    config_resp = _make_response({"cameras": {"jardin": {}}})
    cm_session = _make_session_with_login(login_resp, config_resp)

    with patch(PATCH_CLIENT_SESSION, return_value=cm_session):
        client = FrigateClient("http://frigate.local", username="admin", password="pass")
        cameras = await client.get_cameras()

    assert cameras == ["jardin"]


async def test_get_cameras_login_erreur_401_leve_client_response_error() -> None:
    """Login returns 401 → raise_for_status raises ClientResponseError."""
    login_resp = MagicMock()
    login_resp.raise_for_status = MagicMock(
        side_effect=aiohttp.ClientResponseError(MagicMock(), (), status=401)
    )
    login_resp.cookies = {}

    config_resp = _make_response({})
    cm_session = _make_session_with_login(login_resp, config_resp)

    with patch(PATCH_CLIENT_SESSION, return_value=cm_session):
        client = FrigateClient("http://frigate.local", username="admin", password="wrong")
        with pytest.raises(aiohttp.ClientError):
            await client.get_cameras()


# ---------------------------------------------------------------------------
# Tests get_media
# ---------------------------------------------------------------------------


def _make_media_response(content: bytes = b"data", content_type: str = "image/jpeg") -> MagicMock:
    """Create a mock response for get_media."""
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.headers = {"Content-Type": content_type}
    resp.read = AsyncMock(return_value=content)
    return resp


def _make_session_for_media(resp: MagicMock) -> MagicMock:
    """Create a mock ClientSession for get_media (without login)."""
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
    """get_media() returns (bytes, content_type) on a valid response."""
    cm_session = _make_session_for_media(_make_media_response(b"image_data", "image/jpeg"))

    with patch(PATCH_CLIENT_SESSION, return_value=cm_session):
        client = FrigateClient("http://frigate.local")
        data, ct = await client.get_media("/api/events/abc/snapshot.jpg")

    assert data == b"image_data"
    assert ct == "image/jpeg"


async def test_get_media_content_type_defaut_si_absent() -> None:
    """get_media() returns application/octet-stream if Content-Type is absent."""
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.headers = {}  # no Content-Type
    resp.read = AsyncMock(return_value=b"binary")
    cm_session = _make_session_for_media(resp)

    with patch(PATCH_CLIENT_SESSION, return_value=cm_session):
        client = FrigateClient("http://frigate.local")
        data, ct = await client.get_media("/api/events/abc/clip.mp4")

    assert ct == "application/octet-stream"
    assert data == b"binary"


async def test_get_media_avec_credentials_appelle_login() -> None:
    """get_media() with credentials calls POST /api/login."""
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
    """get_media() propagates aiohttp.ClientError on network error."""
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
    """Happy path: returns zones and labels for a camera from /api/config."""
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
    """Camera absent from Frigate config → returns empty zones and labels."""
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
    """Network error on get_camera_config → raises aiohttp.ClientError."""
    session = MagicMock()
    cm_get = MagicMock()
    cm_get.__aenter__ = AsyncMock(
        side_effect=aiohttp.ClientConnectionError("connection refused")
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


async def test_get_camera_config_reponse_non_dict_retourne_vide() -> None:
    """Non-dict JSON response on get_camera_config → returns empty zones and labels."""
    response = _make_response(["not", "a", "dict"])
    cm_session = _make_session(response)

    with patch(PATCH_CLIENT_SESSION, return_value=cm_session):
        client = FrigateClient("http://frigate.local")
        result = await client.get_camera_config("jardin")

    assert result == {"zones": [], "labels": []}


async def test_get_camera_config_avec_credentials_appelle_login() -> None:
    """get_camera_config() with credentials → POST /api/login before GET /api/config."""
    login_resp = MagicMock()
    login_resp.raise_for_status = MagicMock()
    token_cookie = MagicMock()
    token_cookie.value = "jwt_token_xyz"
    login_resp.cookies = {"frigate_token": token_cookie}

    config_resp = _make_response({
        "cameras": {
            "jardin": {
                "zones": {"jardin_zone": {}},
                "objects": {"track": ["person"]},
            }
        }
    })
    cm_session = _make_session_with_login(login_resp, config_resp)

    with patch(PATCH_CLIENT_SESSION, return_value=cm_session):
        client = FrigateClient("http://frigate.local", username="admin", password="secret")
        result = await client.get_camera_config("jardin")

    assert result["zones"] == ["jardin_zone"]
    assert result["labels"] == ["person"]
    cm_session.__aenter__.return_value.post.assert_called_once()
