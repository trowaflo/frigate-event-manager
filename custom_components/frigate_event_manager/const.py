"""Constantes pour Frigate Event Manager."""

DOMAIN = "frigate_event_manager"

# Clés config entry
CONF_URL = "url"
CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_NOTIFY_TARGET = "notify_target"
CONF_CAMERA = "camera"

# Clés filtres subentry
CONF_ZONES = "zones"
CONF_LABELS = "labels"
CONF_DISABLED_HOURS = "disabled_hours"
CONF_SEVERITY = "severity"

# Severity Frigate
SEVERITY_OPTIONS = ["alert", "detection"]
DEFAULT_SEVERITY = ["alert", "detection"]

# MQTT
DEFAULT_MQTT_TOPIC = "frigate/reviews"

# Subentry type
SUBENTRY_TYPE_CAMERA = "camera"

# Notification spéciale
PERSISTENT_NOTIFICATION = "persistent_notification"

# Throttle
DEFAULT_THROTTLE_COOLDOWN = 60
CONF_COOLDOWN = "cooldown"

# Debounce
CONF_DEBOUNCE = "debounce"
DEFAULT_DEBOUNCE = 0

# Silent mode
CONF_SILENT_DURATION = "silent_duration"
DEFAULT_SILENT_DURATION = 30

# Templates de notification
CONF_NOTIF_TITLE = "notification_title"
CONF_NOTIF_MESSAGE = "notification_message"
CONF_CRITICAL_TEMPLATE = "critical_template"
DEFAULT_NOTIF_TITLE = "Frigate — {{ camera }}"
DEFAULT_NOTIF_MESSAGE = "{{ objects | join(', ') or 'objet inconnu' }} détecté ({{ severity }})"

# Son des notifications critiques (iOS Companion)
CONF_CRITICAL_SOUND = "critical_sound"
CONF_CRITICAL_VOLUME = "critical_volume"
DEFAULT_CRITICAL_SOUND = "default"
DEFAULT_CRITICAL_VOLUME = 1.0

# Action au tap de la notification
CONF_TAP_ACTION = "tap_action"
TAP_ACTION_CLIP = "clip"
TAP_ACTION_SNAPSHOT = "snapshot"
TAP_ACTION_PREVIEW = "preview"
TAP_ACTION_OPTIONS = [TAP_ACTION_CLIP, TAP_ACTION_SNAPSHOT, TAP_ACTION_PREVIEW]
DEFAULT_TAP_ACTION = TAP_ACTION_CLIP

# Boutons d'action notification (select par caméra)
CONF_ACTION_BTN1 = "action_btn1"
CONF_ACTION_BTN2 = "action_btn2"
CONF_ACTION_BTN3 = "action_btn3"
DEFAULT_ACTION_BTN = "none"
ACTION_BTN_OPTIONS = ["none", "clip", "snapshot", "preview", "silent_30min", "silent_1h", "dismiss"]

# Event HA mobile app — action sur notification
EVENT_MOBILE_APP_NOTIFICATION_ACTION = "mobile_app_notification_action"

# Proxy media presigné
PROXY_PATH_PREFIX = "/api/frigate_em/media"
SIGNER_DOMAIN_KEY = "frigate_em_signer"
PROXY_CLIENT_KEY = "frigate_em_proxy_client"
PROXY_VIEW_KEY = "frigate_em_proxy_registered"
MEDIA_URL_TTL = 3600  # secondes
