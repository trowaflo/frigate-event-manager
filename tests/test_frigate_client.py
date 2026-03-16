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
