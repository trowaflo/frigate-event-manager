"""Tests du HANotifier — notifications HA Companion pour les événements Frigate.

Couvre :
- async_notify() appelle hass.services.async_call avec les bons paramètres
- html.escape() appliqué sur les champs dynamiques (camera, severity, objects)
- severity=="alert" → data.push.sound.critical == 1
- severity!="alert" → clé "push" absente du payload data
- thumb_url fourni → data["image"] présent avec la valeur correcte
- thumb_url vide (défaut) → clé "image" absente du payload data
- data["tag"] == "frigate_{camera}"
- Exception dans async_call → catchée silencieusement (pas de remontée)
- review_id fourni → action URI vers le clip
- review_id absent → action URI fallback vers /lovelace/cameras
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.frigate_event_manager.coordinator import FrigateEvent
from custom_components.frigate_event_manager.notifier import HANotifier


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_hass() -> MagicMock:
    """Construit un mock minimal de HomeAssistant avec services.async_call async."""
    hass = MagicMock()
    hass.services.async_call = AsyncMock()
    return hass


def _make_event(
    *,
    camera: str = "jardin",
    severity: str = "alert",
    objects: list[str] | None = None,
    review_id: str = "abc123",
    type: str = "new",
) -> FrigateEvent:
    """Construit un FrigateEvent avec des valeurs par défaut réalistes Frigate."""
    return FrigateEvent(
        type=type,
        camera=camera,
        severity=severity,
        objects=objects if objects is not None else ["person"],
        zones=["cour"],
        score=0.85,
        thumb_path="/media/frigate/abc123/thumbnail.jpg",
        review_id=review_id,
        start_time=1_700_000_000.0,
    )


def _notifier(hass: MagicMock, target: str = "mobile_app_iphone") -> HANotifier:
    """Construit un HANotifier avec le hass mock et la cible donnée."""
    return HANotifier(hass, target)


def _captured_service_data(hass: MagicMock) -> dict:
    """Extrait les service_data passés à hass.services.async_call."""
    # async_call("notify", target, service_data)
    call_args = hass.services.async_call.call_args
    return call_args[0][2]  # troisième argument positionnel


# ---------------------------------------------------------------------------
# async_call invoqué avec les bons arguments de domaine et service
# ---------------------------------------------------------------------------

class TestAsyncCallArguments:
    @pytest.mark.asyncio
    async def test_domaine_notify(self) -> None:
        """async_call doit être appelé avec le domaine 'notify'."""
        hass = _make_hass()
        notifier = _notifier(hass, target="mobile_app_iphone")
        event = _make_event()

        await notifier.async_notify(event)

        domain = hass.services.async_call.call_args[0][0]
        assert domain == "notify"

    @pytest.mark.asyncio
    async def test_service_target(self) -> None:
        """async_call doit être appelé avec le notify_target configuré."""
        hass = _make_hass()
        notifier = _notifier(hass, target="mobile_app_pixel")
        event = _make_event()

        await notifier.async_notify(event)

        service = hass.services.async_call.call_args[0][1]
        assert service == "mobile_app_pixel"

    @pytest.mark.asyncio
    async def test_appel_unique(self) -> None:
        """async_call doit être appelé exactement une fois par async_notify()."""
        hass = _make_hass()
        notifier = _notifier(hass)
        event = _make_event()

        await notifier.async_notify(event)

        hass.services.async_call.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_message_dans_service_data(self) -> None:
        """service_data doit contenir la clé 'message'."""
        hass = _make_hass()
        notifier = _notifier(hass)
        event = _make_event(camera="jardin", severity="detection", objects=["car"])

        await notifier.async_notify(event)

        service_data = _captured_service_data(hass)
        assert "message" in service_data
        assert isinstance(service_data["message"], str)

    @pytest.mark.asyncio
    async def test_titre_dans_service_data(self) -> None:
        """service_data doit contenir la clé 'title'."""
        hass = _make_hass()
        notifier = _notifier(hass)
        event = _make_event(camera="entree")

        await notifier.async_notify(event)

        service_data = _captured_service_data(hass)
        assert "title" in service_data
        assert "entree" in service_data["title"]

    @pytest.mark.asyncio
    async def test_data_dans_service_data(self) -> None:
        """service_data doit contenir la clé 'data' de type dict."""
        hass = _make_hass()
        notifier = _notifier(hass)
        event = _make_event()

        await notifier.async_notify(event)

        service_data = _captured_service_data(hass)
        assert "data" in service_data
        assert isinstance(service_data["data"], dict)


# ---------------------------------------------------------------------------
# html.escape() sur les champs dynamiques
# ---------------------------------------------------------------------------

class TestHtmlEscape:
    @pytest.mark.asyncio
    async def test_escape_camera_dans_message(self) -> None:
        """html.escape() doit être appliqué sur le nom de caméra dans le message."""
        hass = _make_hass()
        notifier = _notifier(hass)
        event = _make_event(camera="<script>alert(1)</script>")

        await notifier.async_notify(event)

        service_data = _captured_service_data(hass)
        assert "<script>" not in service_data["message"]
        assert "&lt;script&gt;" in service_data["message"]

    @pytest.mark.asyncio
    async def test_escape_camera_dans_titre(self) -> None:
        """html.escape() doit être appliqué sur le nom de caméra dans le titre."""
        hass = _make_hass()
        notifier = _notifier(hass)
        event = _make_event(camera="<script>alert(1)</script>")

        await notifier.async_notify(event)

        service_data = _captured_service_data(hass)
        assert "<script>" not in service_data["title"]
        assert "&lt;script&gt;" in service_data["title"]

    @pytest.mark.asyncio
    async def test_escape_camera_dans_tag(self) -> None:
        """html.escape() doit être appliqué sur le nom de caméra dans data['tag']."""
        hass = _make_hass()
        notifier = _notifier(hass)
        event = _make_event(camera='<img src="x" onerror="evil()">')

        await notifier.async_notify(event)

        service_data = _captured_service_data(hass)
        tag = service_data["data"]["tag"]
        assert "<img" not in tag
        assert "&lt;img" in tag

    @pytest.mark.asyncio
    async def test_escape_severity_dans_message(self) -> None:
        """html.escape() doit être appliqué sur le champ severity dans le message."""
        hass = _make_hass()
        notifier = _notifier(hass)
        event = _make_event(severity="<b>alert</b>")

        await notifier.async_notify(event)

        service_data = _captured_service_data(hass)
        assert "<b>" not in service_data["message"]
        assert "&lt;b&gt;" in service_data["message"]

    @pytest.mark.asyncio
    async def test_escape_objects_dans_message(self) -> None:
        """html.escape() doit être appliqué sur les objets détectés dans le message."""
        hass = _make_hass()
        notifier = _notifier(hass)
        event = _make_event(objects=["<person>", "car&truck"])

        await notifier.async_notify(event)

        service_data = _captured_service_data(hass)
        msg = service_data["message"]
        assert "<person>" not in msg
        assert "&lt;person&gt;" in msg
        assert "car&truck" not in msg
        assert "car&amp;truck" in msg

    @pytest.mark.asyncio
    async def test_escape_champs_normaux_inchanges(self) -> None:
        """Des champs normaux sans caractères spéciaux ne doivent pas être altérés."""
        hass = _make_hass()
        notifier = _notifier(hass)
        event = _make_event(camera="jardin", severity="alert", objects=["person"])

        await notifier.async_notify(event)

        service_data = _captured_service_data(hass)
        assert "jardin" in service_data["message"]
        assert "alert" in service_data["message"]
        assert "person" in service_data["message"]


# ---------------------------------------------------------------------------
# severity == "alert" → data.push.sound.critical == 1
# ---------------------------------------------------------------------------

class TestCriticalAlert:
    @pytest.mark.asyncio
    async def test_severity_alert_critical_1(self) -> None:
        """severity='alert' → data['push']['sound']['critical'] == 1."""
        hass = _make_hass()
        notifier = _notifier(hass)
        event = _make_event(severity="alert")

        await notifier.async_notify(event)

        data = _captured_service_data(hass)["data"]
        assert "push" in data
        assert data["push"]["sound"]["critical"] == 1

    @pytest.mark.asyncio
    async def test_severity_alert_sound_name_default(self) -> None:
        """severity='alert' → data['push']['sound']['name'] == 'default'."""
        hass = _make_hass()
        notifier = _notifier(hass)
        event = _make_event(severity="alert")

        await notifier.async_notify(event)

        data = _captured_service_data(hass)["data"]
        assert data["push"]["sound"]["name"] == "default"

    @pytest.mark.asyncio
    async def test_severity_detection_pas_de_push(self) -> None:
        """severity='detection' → clé 'push' absente du payload data."""
        hass = _make_hass()
        notifier = _notifier(hass)
        event = _make_event(severity="detection")

        await notifier.async_notify(event)

        data = _captured_service_data(hass)["data"]
        assert "push" not in data

    @pytest.mark.asyncio
    async def test_severity_vide_pas_de_push(self) -> None:
        """severity='' (cas edge) → clé 'push' absente du payload data."""
        hass = _make_hass()
        notifier = _notifier(hass)
        event = _make_event(severity="")

        await notifier.async_notify(event)

        data = _captured_service_data(hass)["data"]
        assert "push" not in data

    @pytest.mark.asyncio
    async def test_severity_case_sensitive_detection(self) -> None:
        """severity='Detection' (casse différente) → pas de push (comparaison exacte)."""
        hass = _make_hass()
        notifier = _notifier(hass)
        event = _make_event(severity="Detection")

        await notifier.async_notify(event)

        data = _captured_service_data(hass)["data"]
        assert "push" not in data


# ---------------------------------------------------------------------------
# thumb_url → data["image"]
# ---------------------------------------------------------------------------

class TestThumbUrl:
    @pytest.mark.asyncio
    async def test_thumb_url_fourni_image_presente(self) -> None:
        """Quand thumb_url est fourni, data['image'] doit contenir l'URL."""
        hass = _make_hass()
        notifier = _notifier(hass)
        event = _make_event()
        thumb_url = "http://frigate.local/api/events/abc123/thumbnail.jpg"

        await notifier.async_notify(event, thumb_url=thumb_url)

        data = _captured_service_data(hass)["data"]
        assert "image" in data
        assert data["image"] == thumb_url

    @pytest.mark.asyncio
    async def test_thumb_url_vide_image_absente(self) -> None:
        """Quand thumb_url est vide (défaut), data['image'] doit être absent."""
        hass = _make_hass()
        notifier = _notifier(hass)
        event = _make_event()

        await notifier.async_notify(event)

        data = _captured_service_data(hass)["data"]
        assert "image" not in data

    @pytest.mark.asyncio
    async def test_thumb_url_chaine_vide_explicite_image_absente(self) -> None:
        """thumb_url='' explicite → data['image'] absent."""
        hass = _make_hass()
        notifier = _notifier(hass)
        event = _make_event()

        await notifier.async_notify(event, thumb_url="")

        data = _captured_service_data(hass)["data"]
        assert "image" not in data

    @pytest.mark.asyncio
    async def test_thumb_url_avec_chemin_relatif(self) -> None:
        """thumb_url peut être un chemin relatif — transmis tel quel."""
        hass = _make_hass()
        notifier = _notifier(hass)
        event = _make_event()
        thumb_url = "/api/frigate/notifications/abc/thumbnail.jpg"

        await notifier.async_notify(event, thumb_url=thumb_url)

        data = _captured_service_data(hass)["data"]
        assert data["image"] == thumb_url


# ---------------------------------------------------------------------------
# data["tag"] = "frigate_{camera}"
# ---------------------------------------------------------------------------

class TestTag:
    @pytest.mark.asyncio
    async def test_tag_format_nominal(self) -> None:
        """data['tag'] doit valoir 'frigate_{camera}' pour une caméra normale."""
        hass = _make_hass()
        notifier = _notifier(hass)
        event = _make_event(camera="jardin")

        await notifier.async_notify(event)

        data = _captured_service_data(hass)["data"]
        assert data["tag"] == "frigate_jardin"

    @pytest.mark.asyncio
    async def test_tag_autre_camera(self) -> None:
        """data['tag'] prend bien le nom de la caméra passée dans l'événement."""
        hass = _make_hass()
        notifier = _notifier(hass)
        event = _make_event(camera="parking_souterrain")

        await notifier.async_notify(event)

        data = _captured_service_data(hass)["data"]
        assert data["tag"] == "frigate_parking_souterrain"

    @pytest.mark.asyncio
    async def test_tag_camera_avec_caracteres_speciaux_echappes(self) -> None:
        """data['tag'] utilise la version html-escapée du nom de caméra."""
        hass = _make_hass()
        notifier = _notifier(hass)
        event = _make_event(camera="cam&1")

        await notifier.async_notify(event)

        data = _captured_service_data(hass)["data"]
        assert data["tag"] == "frigate_cam&amp;1"


# ---------------------------------------------------------------------------
# Actions — review_id fourni vs absent
# ---------------------------------------------------------------------------

class TestActions:
    @pytest.mark.asyncio
    async def test_action_avec_review_id_pointe_clip(self) -> None:
        """review_id fourni → l'URI de l'action pointe vers le clip Frigate."""
        hass = _make_hass()
        notifier = _notifier(hass)
        event = _make_event(review_id="review42")

        await notifier.async_notify(event)

        data = _captured_service_data(hass)["data"]
        actions = data["actions"]
        assert len(actions) == 1
        assert "review42" in actions[0]["uri"]
        assert actions[0]["action"] == "URI"

    @pytest.mark.asyncio
    async def test_action_sans_review_id_fallback_lovelace(self) -> None:
        """review_id vide → l'URI de l'action utilise le fallback /lovelace/cameras."""
        hass = _make_hass()
        notifier = _notifier(hass)
        event = _make_event(review_id="")

        await notifier.async_notify(event)

        data = _captured_service_data(hass)["data"]
        actions = data["actions"]
        assert actions[0]["uri"] == "/lovelace/cameras"


# ---------------------------------------------------------------------------
# Exception dans async_call → catchée silencieusement
# ---------------------------------------------------------------------------

class TestExceptionCatchee:
    @pytest.mark.asyncio
    async def test_exception_ne_remonte_pas(self) -> None:
        """Si async_call lève une Exception, async_notify ne doit pas la propager."""
        hass = _make_hass()
        hass.services.async_call = AsyncMock(side_effect=Exception("service indisponible"))
        notifier = _notifier(hass)
        event = _make_event()

        # Ne doit pas lever d'exception
        await notifier.async_notify(event)

    @pytest.mark.asyncio
    async def test_exception_runtime_error_ne_remonte_pas(self) -> None:
        """RuntimeError dans async_call doit aussi être catchée silencieusement."""
        hass = _make_hass()
        hass.services.async_call = AsyncMock(side_effect=RuntimeError("timeout"))
        notifier = _notifier(hass)
        event = _make_event()

        await notifier.async_notify(event)

    @pytest.mark.asyncio
    async def test_exception_loggee(self) -> None:
        """Une exception dans async_call doit être loggée (test via patch logger)."""
        hass = _make_hass()
        hass.services.async_call = AsyncMock(side_effect=Exception("erreur réseau"))
        notifier = _notifier(hass)
        event = _make_event()

        with patch(
            "custom_components.frigate_event_manager.notifier._LOGGER"
        ) as mock_logger:
            await notifier.async_notify(event)
            mock_logger.error.assert_called_once()

    @pytest.mark.asyncio
    async def test_sans_exception_pas_de_log_error(self) -> None:
        """Sans exception, _LOGGER.error ne doit pas être appelé."""
        hass = _make_hass()
        notifier = _notifier(hass)
        event = _make_event()

        with patch(
            "custom_components.frigate_event_manager.notifier._LOGGER"
        ) as mock_logger:
            await notifier.async_notify(event)
            mock_logger.error.assert_not_called()


# ---------------------------------------------------------------------------
# Objects vide → fallback "inconnu"
# ---------------------------------------------------------------------------

class TestObjectsVide:
    @pytest.mark.asyncio
    async def test_objects_vide_fallback_inconnu(self) -> None:
        """Quand objects est une liste vide, le message doit contenir 'inconnu'."""
        hass = _make_hass()
        notifier = _notifier(hass)
        event = _make_event(objects=[])

        await notifier.async_notify(event)

        service_data = _captured_service_data(hass)
        assert "inconnu" in service_data["message"]

    @pytest.mark.asyncio
    async def test_objects_multiples_joints_virgule(self) -> None:
        """Quand plusieurs objets sont détectés, ils doivent être joints par ', '."""
        hass = _make_hass()
        notifier = _notifier(hass)
        event = _make_event(objects=["person", "car", "dog"])

        await notifier.async_notify(event)

        service_data = _captured_service_data(hass)
        assert "person" in service_data["message"]
        assert "car" in service_data["message"]
        assert "dog" in service_data["message"]
