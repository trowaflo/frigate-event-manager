"""Tests du HANotifier — notifications pour les événements Frigate."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from custom_components.frigate_event_manager.domain.model import FrigateEvent
from custom_components.frigate_event_manager.const import PERSISTENT_NOTIFICATION
from custom_components.frigate_event_manager.notifier import HANotifier


def _make_hass() -> MagicMock:
    """Retourne un hass mocké avec services.async_call patchable."""
    hass = MagicMock()
    hass.services.async_call = AsyncMock()
    return hass


def _make_event(**kwargs) -> FrigateEvent:
    defaults = dict(
        type="new",
        camera="entree",
        severity="detection",
        objects=["person"],
        review_id="abc123",
    )
    return FrigateEvent(**{**defaults, **kwargs})


async def test_persistent_notification_appelle_bon_service() -> None:
    """persistent_notification → appelle persistent_notification.create."""
    hass = _make_hass()
    notifier = HANotifier(hass, PERSISTENT_NOTIFICATION)
    await notifier.async_notify(_make_event())

    hass.services.async_call.assert_called_once()
    call_args = hass.services.async_call.call_args
    assert call_args[0][0] == "persistent_notification"
    assert call_args[0][1] == "create"


async def test_notify_service_appelle_notify_xxx() -> None:
    """notify.mobile_app_iphone → appelle notify.mobile_app_iphone."""
    hass = _make_hass()
    notifier = HANotifier(hass, "notify.mobile_app_iphone")
    await notifier.async_notify(_make_event())

    hass.services.async_call.assert_called_once()
    call_args = hass.services.async_call.call_args
    assert call_args[0][0] == "notify"
    assert call_args[0][1] == "mobile_app_iphone"


async def test_message_contient_camera_et_objets() -> None:
    """Le message inclut le nom de la caméra et les objets détectés."""
    hass = _make_hass()
    notifier = HANotifier(hass, PERSISTENT_NOTIFICATION)
    await notifier.async_notify(_make_event(camera="garage", objects=["car"]))

    service_data = hass.services.async_call.call_args[0][2]
    assert "garage" in service_data["title"]
    assert "car" in service_data["message"]


async def test_html_escape_sur_camera() -> None:
    """Les champs dynamiques sont échappés (protection injection)."""
    hass = _make_hass()
    notifier = HANotifier(hass, PERSISTENT_NOTIFICATION)
    await notifier.async_notify(_make_event(camera="<script>alert(1)</script>"))

    service_data = hass.services.async_call.call_args[0][2]
    assert "<script>" not in service_data["title"]
    assert "&lt;script&gt;" in service_data["title"]


async def test_objects_vide_affiche_inconnu() -> None:
    """Liste d'objets vide → affiche 'objet inconnu' dans le message."""
    hass = _make_hass()
    notifier = HANotifier(hass, PERSISTENT_NOTIFICATION)
    await notifier.async_notify(_make_event(objects=[]))

    service_data = hass.services.async_call.call_args[0][2]
    assert "inconnu" in service_data["message"]


async def test_target_invalide_ne_crashe_pas() -> None:
    """Un notify_target sans '.' ne crashe pas et n'appelle aucun service."""
    hass = _make_hass()
    notifier = HANotifier(hass, "invalid_target")
    await notifier.async_notify(_make_event())
    hass.services.async_call.assert_not_called()


async def test_persistent_notification_id_inclut_camera_et_review() -> None:
    """notification_id inclut la caméra et le review_id."""
    hass = _make_hass()
    notifier = HANotifier(hass, PERSISTENT_NOTIFICATION)
    await notifier.async_notify(_make_event(camera="jardin", review_id="xyz789"))

    service_data = hass.services.async_call.call_args[0][2]
    assert "jardin" in service_data["notification_id"]
    assert "xyz789" in service_data["notification_id"]
