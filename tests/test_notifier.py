"""Tests du HANotifier — notifications pour les événements Frigate."""

from __future__ import annotations

import pytest
from homeassistant.core import HomeAssistant, ServiceCall

from custom_components.frigate_event_manager.const import PERSISTENT_NOTIFICATION
from custom_components.frigate_event_manager.domain.model import FrigateEvent
from custom_components.frigate_event_manager.notifier import HANotifier


def _make_event(**kwargs) -> FrigateEvent:
    defaults = dict(
        type="new",
        camera="entree",
        severity="detection",
        objects=["person"],
        zones=["jardin"],
        score=0.9,
        review_id="abc123",
    )
    return FrigateEvent(**{**defaults, **kwargs})


def _register_mock_services(hass: HomeAssistant) -> list[ServiceCall]:
    """Enregistre des handlers mock pour tous les services de notification."""
    calls: list[ServiceCall] = []

    async def _handler(call: ServiceCall) -> None:
        calls.append(call)

    hass.services.async_register("persistent_notification", "create", _handler)
    hass.services.async_register("notify", "mobile_app_iphone", _handler)
    hass.services.async_register("notify", "test_service", _handler)
    return calls


# ---------------------------------------------------------------------------
# Tests de base — routing des services
# ---------------------------------------------------------------------------


async def test_persistent_notification_appelle_bon_service(hass: HomeAssistant) -> None:
    """persistent_notification → appelle persistent_notification.create."""
    calls = _register_mock_services(hass)
    notifier = HANotifier(hass, PERSISTENT_NOTIFICATION)
    await notifier.async_notify(_make_event())

    assert len(calls) == 1
    assert calls[0].domain == "persistent_notification"
    assert calls[0].service == "create"


async def test_notify_service_appelle_notify_xxx(hass: HomeAssistant) -> None:
    """notify.mobile_app_iphone → appelle notify.mobile_app_iphone."""
    calls = _register_mock_services(hass)
    notifier = HANotifier(hass, "notify.mobile_app_iphone")
    await notifier.async_notify(_make_event())

    assert len(calls) == 1
    assert calls[0].domain == "notify"
    assert calls[0].service == "mobile_app_iphone"


async def test_target_invalide_ne_crashe_pas(hass: HomeAssistant) -> None:
    """Un notify_target sans '.' ne crashe pas et n'appelle aucun service."""
    calls = _register_mock_services(hass)
    notifier = HANotifier(hass, "invalid_target")
    await notifier.async_notify(_make_event())
    assert len(calls) == 0


# ---------------------------------------------------------------------------
# Tests templates par défaut
# ---------------------------------------------------------------------------


async def test_message_contient_camera_et_objets(hass: HomeAssistant) -> None:
    """Le titre inclut la caméra, le message inclut les objets."""
    calls = _register_mock_services(hass)
    notifier = HANotifier(hass, PERSISTENT_NOTIFICATION)
    await notifier.async_notify(_make_event(camera="garage", objects=["car"]))

    data = calls[0].data
    assert "garage" in data["title"]
    assert "car" in data["message"]


async def test_objects_vide_affiche_inconnu(hass: HomeAssistant) -> None:
    """Liste d'objets vide → affiche 'objet inconnu' dans le message."""
    calls = _register_mock_services(hass)
    notifier = HANotifier(hass, PERSISTENT_NOTIFICATION)
    await notifier.async_notify(_make_event(objects=[]))

    assert "inconnu" in calls[0].data["message"]


async def test_html_escape_sur_camera(hass: HomeAssistant) -> None:
    """Les champs dynamiques sont échappés (protection injection XSS)."""
    calls = _register_mock_services(hass)
    notifier = HANotifier(hass, PERSISTENT_NOTIFICATION)
    await notifier.async_notify(_make_event(camera="<script>alert(1)</script>"))

    title = calls[0].data["title"]
    assert "<script>" not in title
    assert "&lt;script&gt;" in title


async def test_persistent_notification_id_inclut_camera_et_review(hass: HomeAssistant) -> None:
    """notification_id inclut la caméra et le review_id."""
    calls = _register_mock_services(hass)
    notifier = HANotifier(hass, PERSISTENT_NOTIFICATION)
    await notifier.async_notify(_make_event(camera="jardin", review_id="xyz789"))

    notif_id = calls[0].data["notification_id"]
    assert "jardin" in notif_id
    assert "xyz789" in notif_id


# ---------------------------------------------------------------------------
# Tests templates custom
# ---------------------------------------------------------------------------


async def test_template_titre_custom(hass: HomeAssistant) -> None:
    """Un titre template custom est rendu avec les variables de l'événement."""
    calls = _register_mock_services(hass)
    notifier = HANotifier(
        hass,
        PERSISTENT_NOTIFICATION,
        title_tpl="Alerte {{ camera }} — {{ severity }}",
    )
    await notifier.async_notify(_make_event(camera="jardin", severity="alert"))

    assert calls[0].data["title"] == "Alerte jardin — alert"


async def test_template_message_custom_avec_liste(hass: HomeAssistant) -> None:
    """Le message custom peut utiliser le filtre join sur la liste objects."""
    calls = _register_mock_services(hass)
    notifier = HANotifier(
        hass,
        PERSISTENT_NOTIFICATION,
        message_tpl="{{ objects | join(' et ') }} dans {{ zones | join(', ') }}",
    )
    await notifier.async_notify(
        _make_event(objects=["person", "car"], zones=["entree", "rue"])
    )

    assert calls[0].data["message"] == "person et car dans entree, rue"


async def test_template_score_disponible(hass: HomeAssistant) -> None:
    """La variable score est accessible dans le template."""
    calls = _register_mock_services(hass)
    notifier = HANotifier(
        hass,
        PERSISTENT_NOTIFICATION,
        message_tpl="Score : {{ (score * 100) | round }}%",
    )
    await notifier.async_notify(_make_event(score=0.92))

    assert "92" in calls[0].data["message"]


async def test_template_invalide_fallback_brut(hass: HomeAssistant) -> None:
    """Un template invalide ne crashe pas — retourne le template brut."""
    calls = _register_mock_services(hass)
    notifier = HANotifier(
        hass,
        PERSISTENT_NOTIFICATION,
        title_tpl="{{ variable_inexistante | filtre_inconnu }}",
    )
    await notifier.async_notify(_make_event())
    assert len(calls) == 1


async def test_template_vide_utilise_defaut(hass: HomeAssistant) -> None:
    """Templates None → comportement par défaut (titre et message standard)."""
    calls = _register_mock_services(hass)
    notifier = HANotifier(hass, PERSISTENT_NOTIFICATION, title_tpl=None, message_tpl=None)
    await notifier.async_notify(_make_event(camera="cour", objects=["dog"]))

    data = calls[0].data
    assert "cour" in data["title"]
    assert "dog" in data["message"]


# ---------------------------------------------------------------------------
# Tests feature 3 — group companion_data
# ---------------------------------------------------------------------------


async def test_companion_data_contient_group(hass: HomeAssistant) -> None:
    """companion_data contient 'group' avec le nom de la caméra."""
    calls = _register_mock_services(hass)
    notifier = HANotifier(hass, "notify.mobile_app_iphone")
    await notifier.async_notify(_make_event(camera="jardin"))

    data = calls[0].data["data"]
    assert "group" in data
    assert data["group"] == "frigate-jardin"


async def test_companion_data_group_escape_camera(hass: HomeAssistant) -> None:
    """Le nom de caméra dans 'group' est HTML-escaped."""
    calls = _register_mock_services(hass)
    notifier = HANotifier(hass, "notify.mobile_app_iphone")
    await notifier.async_notify(_make_event(camera="<cam>"))

    data = calls[0].data["data"]
    assert "<cam>" not in data["group"]
    assert "&lt;cam&gt;" in data["group"]


# ---------------------------------------------------------------------------
# Tests feature 7 — fix persistent_notification
# ---------------------------------------------------------------------------


async def test_persistent_notification_pas_de_image_ni_url(hass: HomeAssistant) -> None:
    """persistent_notification n'ajoute pas image/url/clickAction/actions."""
    calls = _register_mock_services(hass)
    notifier = HANotifier(
        hass,
        PERSISTENT_NOTIFICATION,
        frigate_url="http://frigate.local",
    )
    event = _make_event(review_id="rev1", detections=["det1"])
    await notifier.async_notify(event)

    # persistent_notification.create reçoit seulement title/message/notification_id
    data = calls[0].data
    assert "image" not in data
    assert "url" not in data
    assert "clickAction" not in data
    assert "actions" not in data


async def test_persistent_notification_liens_markdown_dans_message(hass: HomeAssistant) -> None:
    """persistent_notification ajoute des liens markdown dans le message si URLs disponibles."""
    calls = _register_mock_services(hass)
    notifier = HANotifier(
        hass,
        PERSISTENT_NOTIFICATION,
        frigate_url="http://frigate.local",
    )
    event = _make_event(review_id="rev1", detections=["det1"])
    await notifier.async_notify(event)

    message = calls[0].data["message"]
    assert "[Clip]" in message or "[Snapshot]" in message


async def test_persistent_notification_sans_urls_pas_de_liens(hass: HomeAssistant) -> None:
    """persistent_notification sans URLs disponibles → pas de section liens."""
    calls = _register_mock_services(hass)
    notifier = HANotifier(hass, PERSISTENT_NOTIFICATION)
    event = _make_event(review_id="")  # pas de review_id → pas d'URLs
    await notifier.async_notify(event)

    message = calls[0].data["message"]
    assert "[Clip]" not in message
    assert "[Snapshot]" not in message


async def test_companion_pas_persistent_notification_contient_tag(hass: HomeAssistant) -> None:
    """Pour un target Companion, companion_data contient tag."""
    calls = _register_mock_services(hass)
    notifier = HANotifier(hass, "notify.mobile_app_iphone")
    await notifier.async_notify(_make_event(camera="entree", review_id="abc"))

    data = calls[0].data["data"]
    assert "tag" in data
    assert "entree" in data["tag"]
    assert "abc" in data["tag"]
