"""Tests for HANotifier — notifications for Frigate events."""

from __future__ import annotations

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
    """Register mock handlers for all notification services."""
    calls: list[ServiceCall] = []

    async def _handler(call: ServiceCall) -> None:
        calls.append(call)

    hass.services.async_register("persistent_notification", "create", _handler)
    hass.services.async_register("notify", "mobile_app_iphone", _handler)
    hass.services.async_register("notify", "test_service", _handler)
    return calls


# ---------------------------------------------------------------------------
# Basic tests — service routing
# ---------------------------------------------------------------------------


async def test_persistent_notification_appelle_bon_service(hass: HomeAssistant) -> None:
    """persistent_notification → calls persistent_notification.create."""
    calls = _register_mock_services(hass)
    notifier = HANotifier(hass, PERSISTENT_NOTIFICATION)
    await notifier.async_notify(_make_event())

    assert len(calls) == 1
    assert calls[0].domain == "persistent_notification"
    assert calls[0].service == "create"


async def test_notify_service_appelle_notify_xxx(hass: HomeAssistant) -> None:
    """notify.mobile_app_iphone → calls notify.mobile_app_iphone."""
    calls = _register_mock_services(hass)
    notifier = HANotifier(hass, "notify.mobile_app_iphone")
    await notifier.async_notify(_make_event())

    assert len(calls) == 1
    assert calls[0].domain == "notify"
    assert calls[0].service == "mobile_app_iphone"


async def test_target_invalide_ne_crashe_pas(hass: HomeAssistant) -> None:
    """A notify_target without '.' does not crash and calls no service."""
    calls = _register_mock_services(hass)
    notifier = HANotifier(hass, "invalid_target")
    await notifier.async_notify(_make_event())
    assert len(calls) == 0


# ---------------------------------------------------------------------------
# Default template tests
# ---------------------------------------------------------------------------


async def test_message_contient_camera_et_objets(hass: HomeAssistant) -> None:
    """The title includes the camera name, the message includes the objects."""
    calls = _register_mock_services(hass)
    notifier = HANotifier(hass, PERSISTENT_NOTIFICATION)
    await notifier.async_notify(_make_event(camera="garage", objects=["car"]))

    data = calls[0].data
    assert "garage" in data["title"]
    assert "car" in data["message"]


async def test_objects_vide_affiche_inconnu(hass: HomeAssistant) -> None:
    """Empty object list → displays 'objet inconnu' in the message."""
    calls = _register_mock_services(hass)
    notifier = HANotifier(hass, PERSISTENT_NOTIFICATION)
    await notifier.async_notify(_make_event(objects=[]))

    assert "inconnu" in calls[0].data["message"]


async def test_html_escape_sur_camera(hass: HomeAssistant) -> None:
    """Dynamic fields are escaped (XSS injection protection)."""
    calls = _register_mock_services(hass)
    notifier = HANotifier(hass, PERSISTENT_NOTIFICATION)
    await notifier.async_notify(_make_event(camera="<script>alert(1)</script>"))

    title = calls[0].data["title"]
    assert "<script>" not in title
    assert "&lt;script&gt;" in title


async def test_persistent_notification_id_inclut_camera_et_review(hass: HomeAssistant) -> None:
    """notification_id includes the camera name and review_id."""
    calls = _register_mock_services(hass)
    notifier = HANotifier(hass, PERSISTENT_NOTIFICATION)
    await notifier.async_notify(_make_event(camera="jardin", review_id="xyz789"))

    notif_id = calls[0].data["notification_id"]
    assert "jardin" in notif_id
    assert "xyz789" in notif_id


# ---------------------------------------------------------------------------
# Custom template tests
# ---------------------------------------------------------------------------


async def test_template_titre_custom(hass: HomeAssistant) -> None:
    """A custom title template is rendered with event variables."""
    calls = _register_mock_services(hass)
    notifier = HANotifier(
        hass,
        PERSISTENT_NOTIFICATION,
        title_tpl="Alerte {{ camera }} — {{ severity }}",
    )
    await notifier.async_notify(_make_event(camera="jardin", severity="alert"))

    assert calls[0].data["title"] == "Alerte jardin — alert"


async def test_template_message_custom_avec_liste(hass: HomeAssistant) -> None:
    """The custom message can use the join filter on the objects list."""
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
    """The score variable is accessible in the template."""
    calls = _register_mock_services(hass)
    notifier = HANotifier(
        hass,
        PERSISTENT_NOTIFICATION,
        message_tpl="Score : {{ (score * 100) | round }}%",
    )
    await notifier.async_notify(_make_event(score=0.92))

    assert "92" in calls[0].data["message"]


async def test_template_invalide_fallback_brut(hass: HomeAssistant) -> None:
    """An invalid template does not crash — returns the raw template."""
    calls = _register_mock_services(hass)
    notifier = HANotifier(
        hass,
        PERSISTENT_NOTIFICATION,
        title_tpl="{{ variable_inexistante | filtre_inconnu }}",
    )
    await notifier.async_notify(_make_event())
    assert len(calls) == 1


async def test_template_vide_utilise_defaut(hass: HomeAssistant) -> None:
    """Templates None → default behavior (standard title and message)."""
    calls = _register_mock_services(hass)
    notifier = HANotifier(hass, PERSISTENT_NOTIFICATION, title_tpl=None, message_tpl=None)
    await notifier.async_notify(_make_event(camera="cour", objects=["dog"]))

    data = calls[0].data
    assert "cour" in data["title"]
    assert "dog" in data["message"]


# ---------------------------------------------------------------------------
# Feature 3 tests — group companion_data
# ---------------------------------------------------------------------------


async def test_companion_data_contient_group(hass: HomeAssistant) -> None:
    """companion_data contains 'group' with the camera name."""
    calls = _register_mock_services(hass)
    notifier = HANotifier(hass, "notify.mobile_app_iphone")
    await notifier.async_notify(_make_event(camera="jardin"))

    data = calls[0].data["data"]
    assert "group" in data
    assert data["group"] == "frigate-jardin"


async def test_companion_data_group_escape_camera(hass: HomeAssistant) -> None:
    """The camera name in 'group' is HTML-escaped."""
    calls = _register_mock_services(hass)
    notifier = HANotifier(hass, "notify.mobile_app_iphone")
    await notifier.async_notify(_make_event(camera="<cam>"))

    data = calls[0].data["data"]
    assert "<cam>" not in data["group"]
    assert "&lt;cam&gt;" in data["group"]


# ---------------------------------------------------------------------------
# Feature 7 tests — fix persistent_notification
# ---------------------------------------------------------------------------


async def test_persistent_notification_pas_de_image_ni_url(hass: HomeAssistant) -> None:
    """persistent_notification does not add image/url/clickAction/actions."""
    calls = _register_mock_services(hass)
    notifier = HANotifier(
        hass,
        PERSISTENT_NOTIFICATION,
    )
    event = _make_event(review_id="rev1", detections=["det1"])
    await notifier.async_notify(event)

    # persistent_notification.create only receives title/message/notification_id
    data = calls[0].data
    assert "image" not in data
    assert "url" not in data
    assert "clickAction" not in data
    assert "actions" not in data


async def test_persistent_notification_liens_markdown_dans_message(hass: HomeAssistant) -> None:
    """With signer, persistent_notification inserts markdown links in the message if URLs available."""
    from unittest.mock import MagicMock
    calls = _register_mock_services(hass)
    signer = MagicMock()
    signer.sign_url = MagicMock(side_effect=lambda path: f"https://ha.local{path}")
    notifier = HANotifier(
        hass,
        PERSISTENT_NOTIFICATION,
        signer=signer,
    )
    event = _make_event(review_id="rev1", detections=["det1"])
    await notifier.async_notify(event)

    message = calls[0].data["message"]
    assert "[Clip]" in message or "[Snapshot]" in message


async def test_persistent_notification_sans_urls_pas_de_liens(hass: HomeAssistant) -> None:
    """persistent_notification without available URLs → no links section."""
    calls = _register_mock_services(hass)
    notifier = HANotifier(hass, PERSISTENT_NOTIFICATION)
    event = _make_event(review_id="")  # no review_id → no URLs
    await notifier.async_notify(event)

    message = calls[0].data["message"]
    assert "[Clip]" not in message
    assert "[Snapshot]" not in message


async def test_companion_pas_persistent_notification_contient_tag(hass: HomeAssistant) -> None:
    """For a Companion target, companion_data contains tag."""
    calls = _register_mock_services(hass)
    notifier = HANotifier(hass, "notify.mobile_app_iphone")
    await notifier.async_notify(_make_event(camera="entree", review_id="abc"))

    data = calls[0].data["data"]
    assert "tag" in data
    assert "entree" in data["tag"]
    assert "abc" in data["tag"]


# ---------------------------------------------------------------------------
# Companion feature tests — image, tap URL, actions
# ---------------------------------------------------------------------------


async def test_companion_image_si_snapshot_url_disponible(hass: HomeAssistant) -> None:
    """companion_data contains 'image' when snapshot_url is available."""
    from unittest.mock import MagicMock
    calls = _register_mock_services(hass)
    signer = MagicMock()
    signer.sign_url = MagicMock(side_effect=lambda path: f"https://ha.local{path}")
    notifier = HANotifier(
        hass,
        "notify.mobile_app_iphone",
        signer=signer,
    )
    event = _make_event(review_id="rev1", detections=["det1"])
    await notifier.async_notify(event)

    data = calls[0].data["data"]
    assert "image" in data
    assert "det1" in data["image"]


async def test_companion_url_ios_et_clickaction_android(hass: HomeAssistant) -> None:
    """companion_data contains 'url' (iOS) and 'clickAction' (Android) if tap_url available."""
    from unittest.mock import MagicMock
    calls = _register_mock_services(hass)
    signer = MagicMock()
    signer.sign_url = MagicMock(side_effect=lambda path: f"https://ha.local{path}")
    notifier = HANotifier(
        hass,
        "notify.mobile_app_iphone",
        signer=signer,
    )
    event = _make_event(review_id="rev1", detections=["det1"])
    await notifier.async_notify(event)

    data = calls[0].data["data"]
    assert "url" in data
    assert "clickAction" in data


async def test_companion_actions_boutons_uri(hass: HomeAssistant) -> None:
    """Without configured buttons, only the silence button is displayed."""
    calls = _register_mock_services(hass)
    notifier = HANotifier(
        hass,
        "notify.mobile_app_iphone",
    )
    event = _make_event(review_id="rev1", detections=["det1"])
    await notifier.async_notify(event)

    data = calls[0].data["data"]
    assert "actions" in data
    assert len(data["actions"]) == 1
    assert data["actions"][0]["title"] == "Silence 30 min"
    assert data["actions"][0]["icon"] == "sfsymbols:speaker.zzz"
    assert data["actions"][0]["destructive"] is True


async def test_companion_pas_de_actions_sans_urls(hass: HomeAssistant) -> None:
    """Without media URLs and without configured buttons, the silence button is displayed."""
    calls = _register_mock_services(hass)
    notifier = HANotifier(hass, "notify.mobile_app_iphone")
    event = _make_event(review_id="")  # no review_id → no URLs
    await notifier.async_notify(event)

    data = calls[0].data["data"]
    assert "actions" in data
    assert data["actions"][0]["title"] == "Silence 30 min"
    assert "image" not in data


async def test_companion_tap_action_snapshot(hass: HomeAssistant) -> None:
    """With tap_action='snapshot', 'url' points to snapshot_url."""
    from unittest.mock import MagicMock
    from custom_components.frigate_event_manager.const import TAP_ACTION_SNAPSHOT
    calls = _register_mock_services(hass)
    signer = MagicMock()
    signer.sign_url = MagicMock(side_effect=lambda path: f"https://ha.local{path}")
    notifier = HANotifier(
        hass,
        "notify.mobile_app_iphone",
        signer=signer,
        tap_action=TAP_ACTION_SNAPSHOT,
    )
    event = _make_event(review_id="rev1", detections=["det1"])
    await notifier.async_notify(event)

    data = calls[0].data["data"]
    assert "snapshot" in data.get("url", "")


async def test_companion_tap_action_preview(hass: HomeAssistant) -> None:
    """With tap_action='preview', 'url' points to preview_url."""
    from unittest.mock import MagicMock
    from custom_components.frigate_event_manager.const import TAP_ACTION_PREVIEW
    calls = _register_mock_services(hass)
    signer = MagicMock()
    signer.sign_url = MagicMock(side_effect=lambda path: f"https://ha.local{path}")
    notifier = HANotifier(
        hass,
        "notify.mobile_app_iphone",
        signer=signer,
        tap_action=TAP_ACTION_PREVIEW,
    )
    event = _make_event(review_id="rev1", detections=["det1"])
    await notifier.async_notify(event)

    data = calls[0].data["data"]
    assert "preview" in data.get("url", "")


# ---------------------------------------------------------------------------
# Signer feature tests — presigned URLs
# ---------------------------------------------------------------------------


async def test_build_media_urls_avec_signer(hass: HomeAssistant) -> None:
    """With a signer, URLs are presigned."""
    from unittest.mock import MagicMock

    calls = _register_mock_services(hass)

    signer = MagicMock()
    signer.sign_url = MagicMock(side_effect=lambda path: f"https://signed{path}")

    notifier = HANotifier(
        hass,
        "notify.mobile_app_iphone",
        signer=signer,
    )
    event = _make_event(review_id="rev1", detections=["det1"])
    await notifier.async_notify(event)

    data = calls[0].data["data"]
    # The signer was called → URLs contain "signed"
    assert signer.sign_url.called
    if "image" in data:
        assert "signed" in data["image"]


async def test_build_media_urls_sans_review_id_retourne_vide(hass: HomeAssistant) -> None:
    """Without review_id, all media URLs are empty."""
    from unittest.mock import MagicMock

    _register_mock_services(hass)
    signer = MagicMock()
    signer.sign_url = MagicMock(return_value="https://signed/path")

    notifier = HANotifier(hass, PERSISTENT_NOTIFICATION, signer=signer)
    event = _make_event(review_id="")
    await notifier.async_notify(event)

    # Signer not called if no review_id
    signer.sign_url.assert_not_called()


async def test_persistent_notification_avec_signer_liens_markdown(hass: HomeAssistant) -> None:
    """With signer, persistent_notification inserts presigned links in the message."""
    from unittest.mock import MagicMock

    calls = _register_mock_services(hass)
    signer = MagicMock()
    signer.sign_url = MagicMock(side_effect=lambda path: f"https://signed{path}")

    notifier = HANotifier(hass, PERSISTENT_NOTIFICATION, signer=signer)
    event = _make_event(review_id="rev1", detections=["det1"])
    await notifier.async_notify(event)

    message = calls[0].data["message"]
    assert "[Clip]" in message or "[Snapshot]" in message
    assert "signed" in message


# ---------------------------------------------------------------------------
# Critical notification tests (critical=True)
# ---------------------------------------------------------------------------


async def test_critical_true_ajoute_push_sound_et_channel(hass: HomeAssistant) -> None:
    """critical=True → companion_data contains push.sound.critical=1 and channel."""
    calls = _register_mock_services(hass)
    notifier = HANotifier(hass, "notify.mobile_app_iphone")
    await notifier.async_notify(_make_event(), critical=True)

    data = calls[0].data["data"]
    assert data["push"]["sound"]["critical"] == 1
    assert data["channel"] == "frigate_critical"


async def test_critical_false_pas_de_push_sound(hass: HomeAssistant) -> None:
    """critical=False (default) → no push.sound or channel in companion_data."""
    calls = _register_mock_services(hass)
    notifier = HANotifier(hass, "notify.mobile_app_iphone")
    await notifier.async_notify(_make_event(), critical=False)

    data = calls[0].data["data"]
    assert "push" not in data
    assert "channel" not in data


async def test_critical_true_persistent_notification_pas_de_push(hass: HomeAssistant) -> None:
    """critical=True with persistent_notification → no push (not applicable)."""
    calls = _register_mock_services(hass)
    notifier = HANotifier(hass, PERSISTENT_NOTIFICATION)
    await notifier.async_notify(_make_event(), critical=True)

    # persistent_notification.create does not receive a "push" field
    assert calls[0].domain == "persistent_notification"
    assert "push" not in calls[0].data


# ---------------------------------------------------------------------------
# Notification action button tests (T-532)
# ---------------------------------------------------------------------------


def _make_notifier(hass: HomeAssistant, target: str = "notify.test_service") -> HANotifier:
    return HANotifier(hass, target)


_MEDIA_URLS = {
    "clip_url": "http://frigate:5000/api/events/evt1/clip.mp4",
    "snapshot_url": "http://frigate:5000/api/events/evt1/snapshot.jpg",
    "preview_url": "http://frigate:5000/api/review/rev1/preview",
    "thumbnail_url": "http://frigate:5000/api/events/evt1/thumbnail.jpg",
}
_EMPTY_URLS: dict = {k: "" for k in _MEDIA_URLS}


async def test_action_btns_tous_none_retourne_none(hass: HomeAssistant) -> None:
    """By default (all 'none'), _build_actions_from_btns returns None → auto-generation."""
    notifier = _make_notifier(hass)
    result = notifier._build_actions_from_btns(_MEDIA_URLS, "jardin")
    assert result is None


async def test_action_btns_clip_construit_action_uri(hass: HomeAssistant) -> None:
    """btn1=clip → URI action with the clip URL."""
    notifier = _make_notifier(hass)
    notifier.set_action_buttons("clip", "none", "none")
    result = notifier._build_actions_from_btns(_MEDIA_URLS, "jardin")
    assert result is not None
    assert len(result) == 1
    assert result[0]["action"] == "URI"
    assert result[0]["uri"] == _MEDIA_URLS["clip_url"]
    assert result[0]["title"] == "Clip"


async def test_action_btns_snapshot_construit_action_uri(hass: HomeAssistant) -> None:
    """btn1=snapshot → URI action with the snapshot URL."""
    notifier = _make_notifier(hass)
    notifier.set_action_buttons("snapshot", "none", "none")
    result = notifier._build_actions_from_btns(_MEDIA_URLS, "jardin")
    assert result is not None
    assert result[0]["uri"] == _MEDIA_URLS["snapshot_url"]


async def test_action_btns_preview_construit_action_uri(hass: HomeAssistant) -> None:
    """btn1=preview → URI action with the preview URL."""
    notifier = _make_notifier(hass)
    notifier.set_action_buttons("preview", "none", "none")
    result = notifier._build_actions_from_btns(_MEDIA_URLS, "jardin")
    assert result is not None
    assert result[0]["uri"] == _MEDIA_URLS["preview_url"]


async def test_action_btns_silent_30min_construit_action_specifique(hass: HomeAssistant) -> None:
    """btn1=silent_30min → action fem_silent_30min_{camera}."""
    notifier = _make_notifier(hass)
    notifier.set_action_buttons("silent_30min", "none", "none")
    result = notifier._build_actions_from_btns(_EMPTY_URLS, "jardin")
    assert result is not None
    assert len(result) == 1
    assert result[0]["action"] == "fem_silent_30min_jardin"
    assert result[0]["title"] == "Silence 30 min"


async def test_action_btns_silent_1h_construit_action_specifique(hass: HomeAssistant) -> None:
    """btn2=silent_1h → action fem_silent_1h_{camera}."""
    notifier = _make_notifier(hass)
    notifier.set_action_buttons("none", "silent_1h", "none")
    result = notifier._build_actions_from_btns(_EMPTY_URLS, "jardin")
    assert result is not None
    assert len(result) == 1
    assert result[0]["action"] == "fem_silent_1h_jardin"
    assert result[0]["title"] == "Silence 1h"


async def test_action_btns_dismiss_construit_action_dismiss(hass: HomeAssistant) -> None:
    """btn3=dismiss → action DISMISS_NOTIFICATION."""
    notifier = _make_notifier(hass)
    notifier.set_action_buttons("none", "none", "dismiss")
    result = notifier._build_actions_from_btns(_EMPTY_URLS, "jardin")
    assert result is not None
    assert len(result) == 1
    assert result[0]["action"] == "DISMISS_NOTIFICATION"
    assert result[0]["title"] == "Ignorer"


async def test_action_btns_clip_sans_url_omis(hass: HomeAssistant) -> None:
    """btn1=clip but empty URL → the button is omitted from the list."""
    notifier = _make_notifier(hass)
    notifier.set_action_buttons("clip", "none", "none")
    result = notifier._build_actions_from_btns(_EMPTY_URLS, "jardin")
    assert result is not None
    assert len(result) == 0  # clip without URL → omitted


async def test_action_btns_trois_boutons_differents(hass: HomeAssistant) -> None:
    """3 configured buttons → 3 actions built."""
    notifier = _make_notifier(hass)
    notifier.set_action_buttons("silent_30min", "dismiss", "silent_1h")
    result = notifier._build_actions_from_btns(_EMPTY_URLS, "entree")
    assert result is not None
    assert len(result) == 3
    assert result[0]["action"] == "fem_silent_30min_entree"
    assert result[1]["action"] == "DISMISS_NOTIFICATION"
    assert result[2]["action"] == "fem_silent_1h_entree"


async def test_action_btns_configures_utilisees_dans_notification(hass: HomeAssistant) -> None:
    """With configured _action_btns, async_notify uses the configured actions."""
    calls = _register_mock_services(hass)
    notifier = HANotifier(hass, "notify.test_service")
    notifier.set_action_buttons("silent_30min", "dismiss", "none")

    await notifier.async_notify(_make_event(review_id=""))  # no media URLs

    data = calls[0].data["data"]
    assert "actions" in data
    assert any(a["action"] == "fem_silent_30min_entree" for a in data["actions"])
    assert any(a["action"] == "DISMISS_NOTIFICATION" for a in data["actions"])


async def test_action_btns_tous_none_affiche_silence(hass: HomeAssistant) -> None:
    """With all buttons set to 'none', only the silence button is displayed."""
    calls = _register_mock_services(hass)
    notifier = HANotifier(hass, "notify.test_service")
    await notifier.async_notify(_make_event(review_id="", camera="jardin"))
    data = calls[0].data["data"]
    assert len(data["actions"]) == 1
    assert data["actions"][0]["action"] == "fem_silent_30min_jardin"
    assert data["actions"][0]["destructive"] is True


async def test_set_action_buttons_met_a_jour_action_btns(hass: HomeAssistant) -> None:
    """set_action_buttons updates _action_btns."""
    notifier = _make_notifier(hass)
    notifier.set_action_buttons("clip", "silent_30min", "dismiss")
    assert notifier._action_btns == ["clip", "silent_30min", "dismiss"]


# ---------------------------------------------------------------------------
# Live setters tests (T-532c)
# ---------------------------------------------------------------------------


def test_set_title_template_met_a_jour_template(hass: HomeAssistant) -> None:
    """set_title_template updates _title_tpl."""
    notifier = _make_notifier(hass)
    notifier.set_title_template("Nouvelle alerte {{ camera }}")
    assert notifier._title_tpl == "Nouvelle alerte {{ camera }}"


def test_set_title_template_none_restaure_defaut(hass: HomeAssistant) -> None:
    """set_title_template(None) restores the default template."""
    from custom_components.frigate_event_manager.const import DEFAULT_NOTIF_TITLE

    notifier = _make_notifier(hass)
    notifier.set_title_template(None)
    assert notifier._title_tpl == DEFAULT_NOTIF_TITLE


def test_set_message_template_met_a_jour_template(hass: HomeAssistant) -> None:
    """set_message_template updates _message_tpl."""
    notifier = _make_notifier(hass)
    notifier.set_message_template("Objet: {{ label }}")
    assert notifier._message_tpl == "Objet: {{ label }}"


def test_set_message_template_none_restaure_defaut(hass: HomeAssistant) -> None:
    """set_message_template(None) restores the default message."""
    from custom_components.frigate_event_manager.const import DEFAULT_NOTIF_MESSAGE

    notifier = _make_notifier(hass)
    notifier.set_message_template(None)
    assert notifier._message_tpl == DEFAULT_NOTIF_MESSAGE


def test_set_tap_action_met_a_jour_tap_action(hass: HomeAssistant) -> None:
    """set_tap_action updates _tap_action."""
    notifier = _make_notifier(hass)
    notifier.set_tap_action("snapshot")
    assert notifier._tap_action == "snapshot"


def test_set_tap_action_clip(hass: HomeAssistant) -> None:
    """set_tap_action('clip') is correctly stored."""
    notifier = _make_notifier(hass)
    notifier.set_tap_action("clip")
    assert notifier._tap_action == "clip"
