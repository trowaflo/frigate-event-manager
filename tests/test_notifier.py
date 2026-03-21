"""Tests du HANotifier — notifications pour les événements Frigate."""

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


# ---------------------------------------------------------------------------
# Tests feature companion — image, tap URL, actions
# ---------------------------------------------------------------------------


async def test_companion_image_si_snapshot_url_disponible(hass: HomeAssistant) -> None:
    """companion_data contient 'image' quand snapshot_url est disponible."""
    calls = _register_mock_services(hass)
    notifier = HANotifier(
        hass,
        "notify.mobile_app_iphone",
        frigate_url="http://frigate.local",
    )
    event = _make_event(review_id="rev1", detections=["det1"])
    await notifier.async_notify(event)

    data = calls[0].data["data"]
    assert "image" in data
    assert "det1" in data["image"]


async def test_companion_url_ios_et_clickaction_android(hass: HomeAssistant) -> None:
    """companion_data contient 'url' (iOS) et 'clickAction' (Android) si tap_url disponible."""
    calls = _register_mock_services(hass)
    notifier = HANotifier(
        hass,
        "notify.mobile_app_iphone",
        frigate_url="http://frigate.local",
    )
    event = _make_event(review_id="rev1", detections=["det1"])
    await notifier.async_notify(event)

    data = calls[0].data["data"]
    assert "url" in data
    assert "clickAction" in data


async def test_companion_actions_boutons_uri(hass: HomeAssistant) -> None:
    """Sans boutons configurés, affiche uniquement le bouton silence."""
    calls = _register_mock_services(hass)
    notifier = HANotifier(
        hass,
        "notify.mobile_app_iphone",
        frigate_url="http://frigate.local",
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
    """Sans URLs médias et sans boutons configurés, affiche le bouton silence."""
    calls = _register_mock_services(hass)
    notifier = HANotifier(hass, "notify.mobile_app_iphone")
    event = _make_event(review_id="")  # pas de review_id → pas d'URLs
    await notifier.async_notify(event)

    data = calls[0].data["data"]
    assert "actions" in data
    assert data["actions"][0]["title"] == "Silence 30 min"
    assert "image" not in data


async def test_companion_tap_action_snapshot(hass: HomeAssistant) -> None:
    """Avec tap_action='snapshot', 'url' pointe vers snapshot_url."""
    from custom_components.frigate_event_manager.const import TAP_ACTION_SNAPSHOT
    calls = _register_mock_services(hass)
    notifier = HANotifier(
        hass,
        "notify.mobile_app_iphone",
        frigate_url="http://frigate.local",
        tap_action=TAP_ACTION_SNAPSHOT,
    )
    event = _make_event(review_id="rev1", detections=["det1"])
    await notifier.async_notify(event)

    data = calls[0].data["data"]
    assert "snapshot" in data.get("url", "")


async def test_companion_tap_action_preview(hass: HomeAssistant) -> None:
    """Avec tap_action='preview', 'url' pointe vers preview_url."""
    from custom_components.frigate_event_manager.const import TAP_ACTION_PREVIEW
    calls = _register_mock_services(hass)
    notifier = HANotifier(
        hass,
        "notify.mobile_app_iphone",
        frigate_url="http://frigate.local",
        tap_action=TAP_ACTION_PREVIEW,
    )
    event = _make_event(review_id="rev1", detections=["det1"])
    await notifier.async_notify(event)

    data = calls[0].data["data"]
    assert "preview" in data.get("url", "")


# ---------------------------------------------------------------------------
# Tests feature signer — presigned URLs
# ---------------------------------------------------------------------------


async def test_build_media_urls_avec_signer(hass: HomeAssistant) -> None:
    """Avec un signer, les URLs sont presignées."""
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
    # Le signer a été appelé → les URLs contiennent "signed"
    assert signer.sign_url.called
    if "image" in data:
        assert "signed" in data["image"]


async def test_build_media_urls_sans_review_id_retourne_vide(hass: HomeAssistant) -> None:
    """Sans review_id, toutes les URLs médias sont vides."""
    from unittest.mock import MagicMock

    _register_mock_services(hass)
    signer = MagicMock()
    signer.sign_url = MagicMock(return_value="https://signed/path")

    notifier = HANotifier(hass, PERSISTENT_NOTIFICATION, signer=signer)
    event = _make_event(review_id="")
    await notifier.async_notify(event)

    # Signer non appelé si pas de review_id
    signer.sign_url.assert_not_called()


async def test_persistent_notification_avec_signer_liens_markdown(hass: HomeAssistant) -> None:
    """Avec signer, persistent_notification insère les liens presignés dans le message."""
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
# Tests notification critique (critical=True)
# ---------------------------------------------------------------------------


async def test_critical_true_ajoute_push_sound_et_channel(hass: HomeAssistant) -> None:
    """critical=True → companion_data contient push.sound.critical=1 et channel."""
    calls = _register_mock_services(hass)
    notifier = HANotifier(hass, "notify.mobile_app_iphone")
    await notifier.async_notify(_make_event(), critical=True)

    data = calls[0].data["data"]
    assert data["push"]["sound"]["critical"] == 1
    assert data["channel"] == "frigate_critical"


async def test_critical_false_pas_de_push_sound(hass: HomeAssistant) -> None:
    """critical=False (défaut) → pas de push.sound ni channel dans companion_data."""
    calls = _register_mock_services(hass)
    notifier = HANotifier(hass, "notify.mobile_app_iphone")
    await notifier.async_notify(_make_event(), critical=False)

    data = calls[0].data["data"]
    assert "push" not in data
    assert "channel" not in data


async def test_critical_true_persistent_notification_pas_de_push(hass: HomeAssistant) -> None:
    """critical=True avec persistent_notification → pas de push (non applicable)."""
    calls = _register_mock_services(hass)
    notifier = HANotifier(hass, PERSISTENT_NOTIFICATION)
    await notifier.async_notify(_make_event(), critical=True)

    # persistent_notification.create ne reçoit pas de champ "push"
    assert calls[0].domain == "persistent_notification"
    assert "push" not in calls[0].data


# ---------------------------------------------------------------------------
# Tests boutons d'action notification (T-532)
# ---------------------------------------------------------------------------


def _make_notifier(hass: HomeAssistant, target: str = "notify.test_service") -> HANotifier:
    return HANotifier(hass, target, frigate_url="http://frigate:5000")


_MEDIA_URLS = {
    "clip_url": "http://frigate:5000/api/events/evt1/clip.mp4",
    "snapshot_url": "http://frigate:5000/api/events/evt1/snapshot.jpg",
    "preview_url": "http://frigate:5000/api/review/rev1/preview",
    "thumbnail_url": "http://frigate:5000/api/events/evt1/thumbnail.jpg",
}
_EMPTY_URLS: dict = {k: "" for k in _MEDIA_URLS}


async def test_action_btns_tous_none_retourne_none(hass: HomeAssistant) -> None:
    """Par défaut (tous 'none'), _build_actions_from_btns retourne None → auto-génération."""
    notifier = _make_notifier(hass)
    result = notifier._build_actions_from_btns(_MEDIA_URLS, "jardin")
    assert result is None


async def test_action_btns_clip_construit_action_uri(hass: HomeAssistant) -> None:
    """btn1=clip → action URI avec l'URL clip."""
    notifier = _make_notifier(hass)
    notifier.set_action_buttons("clip", "none", "none")
    result = notifier._build_actions_from_btns(_MEDIA_URLS, "jardin")
    assert result is not None
    assert len(result) == 1
    assert result[0]["action"] == "URI"
    assert result[0]["uri"] == _MEDIA_URLS["clip_url"]
    assert result[0]["title"] == "Clip"


async def test_action_btns_snapshot_construit_action_uri(hass: HomeAssistant) -> None:
    """btn1=snapshot → action URI avec l'URL snapshot."""
    notifier = _make_notifier(hass)
    notifier.set_action_buttons("snapshot", "none", "none")
    result = notifier._build_actions_from_btns(_MEDIA_URLS, "jardin")
    assert result is not None
    assert result[0]["uri"] == _MEDIA_URLS["snapshot_url"]


async def test_action_btns_preview_construit_action_uri(hass: HomeAssistant) -> None:
    """btn1=preview → action URI avec l'URL preview."""
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
    """btn1=clip mais URL vide → le bouton est omis de la liste."""
    notifier = _make_notifier(hass)
    notifier.set_action_buttons("clip", "none", "none")
    result = notifier._build_actions_from_btns(_EMPTY_URLS, "jardin")
    assert result is not None
    assert len(result) == 0  # clip sans URL → omis


async def test_action_btns_trois_boutons_differents(hass: HomeAssistant) -> None:
    """3 boutons configurés → 3 actions construites."""
    notifier = _make_notifier(hass)
    notifier.set_action_buttons("silent_30min", "dismiss", "silent_1h")
    result = notifier._build_actions_from_btns(_EMPTY_URLS, "entree")
    assert result is not None
    assert len(result) == 3
    assert result[0]["action"] == "fem_silent_30min_entree"
    assert result[1]["action"] == "DISMISS_NOTIFICATION"
    assert result[2]["action"] == "fem_silent_1h_entree"


async def test_action_btns_configures_utilisees_dans_notification(hass: HomeAssistant) -> None:
    """Avec _action_btns configurés, async_notify utilise les actions configurées."""
    calls = _register_mock_services(hass)
    notifier = HANotifier(hass, "notify.test_service")
    notifier.set_action_buttons("silent_30min", "dismiss", "none")

    await notifier.async_notify(_make_event(review_id=""))  # pas d'URLs médias

    data = calls[0].data["data"]
    assert "actions" in data
    assert any(a["action"] == "fem_silent_30min_entree" for a in data["actions"])
    assert any(a["action"] == "DISMISS_NOTIFICATION" for a in data["actions"])


async def test_action_btns_tous_none_affiche_silence(hass: HomeAssistant) -> None:
    """Avec tous les boutons à 'none', affiche uniquement le bouton silence."""
    calls = _register_mock_services(hass)
    notifier = HANotifier(hass, "notify.test_service", frigate_url="http://frigate:5000")
    await notifier.async_notify(_make_event(review_id="", camera="jardin"))
    data = calls[0].data["data"]
    assert len(data["actions"]) == 1
    assert data["actions"][0]["action"] == "fem_silent_30min_jardin"
    assert data["actions"][0]["destructive"] is True


async def test_set_action_buttons_met_a_jour_action_btns(hass: HomeAssistant) -> None:
    """set_action_buttons met à jour _action_btns."""
    notifier = _make_notifier(hass)
    notifier.set_action_buttons("clip", "silent_30min", "dismiss")
    assert notifier._action_btns == ["clip", "silent_30min", "dismiss"]


# ---------------------------------------------------------------------------
# Tests setters live (T-532c)
# ---------------------------------------------------------------------------


def test_set_title_template_met_a_jour_template(hass: HomeAssistant) -> None:
    """set_title_template met à jour _title_tpl."""
    notifier = _make_notifier(hass)
    notifier.set_title_template("Nouvelle alerte {{ camera }}")
    assert notifier._title_tpl == "Nouvelle alerte {{ camera }}"


def test_set_title_template_none_restaure_defaut(hass: HomeAssistant) -> None:
    """set_title_template(None) restaure le template par défaut."""
    from custom_components.frigate_event_manager.const import DEFAULT_NOTIF_TITLE

    notifier = _make_notifier(hass)
    notifier.set_title_template(None)
    assert notifier._title_tpl == DEFAULT_NOTIF_TITLE


def test_set_message_template_met_a_jour_template(hass: HomeAssistant) -> None:
    """set_message_template met à jour _message_tpl."""
    notifier = _make_notifier(hass)
    notifier.set_message_template("Objet: {{ label }}")
    assert notifier._message_tpl == "Objet: {{ label }}"


def test_set_message_template_none_restaure_defaut(hass: HomeAssistant) -> None:
    """set_message_template(None) restaure le message par défaut."""
    from custom_components.frigate_event_manager.const import DEFAULT_NOTIF_MESSAGE

    notifier = _make_notifier(hass)
    notifier.set_message_template(None)
    assert notifier._message_tpl == DEFAULT_NOTIF_MESSAGE


def test_set_tap_action_met_a_jour_tap_action(hass: HomeAssistant) -> None:
    """set_tap_action met à jour _tap_action."""
    notifier = _make_notifier(hass)
    notifier.set_tap_action("snapshot")
    assert notifier._tap_action == "snapshot"


def test_set_tap_action_clip(hass: HomeAssistant) -> None:
    """set_tap_action('clip') est correctement stocké."""
    notifier = _make_notifier(hass)
    notifier.set_tap_action("clip")
    assert notifier._tap_action == "clip"
