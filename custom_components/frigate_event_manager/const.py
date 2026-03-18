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

# MQTT
DEFAULT_MQTT_TOPIC = "frigate/reviews"

# Subentry type
SUBENTRY_TYPE_CAMERA = "camera"

# Notification spéciale
PERSISTENT_NOTIFICATION = "persistent_notification"

# Throttle
DEFAULT_THROTTLE_COOLDOWN = 60

# Templates de notification
CONF_NOTIF_TITLE = "notification_title"
CONF_NOTIF_MESSAGE = "notification_message"
DEFAULT_NOTIF_TITLE = "Frigate — {{ camera }}"
DEFAULT_NOTIF_MESSAGE = "{{ objects | join(', ') or 'objet inconnu' }} détecté ({{ severity }})"

# Action au tap de la notification
CONF_TAP_ACTION = "tap_action"
TAP_ACTION_CLIP = "clip"
TAP_ACTION_SNAPSHOT = "snapshot"
TAP_ACTION_PREVIEW = "preview"
TAP_ACTION_OPTIONS = [TAP_ACTION_CLIP, TAP_ACTION_SNAPSHOT, TAP_ACTION_PREVIEW]
DEFAULT_TAP_ACTION = TAP_ACTION_CLIP

# Proxy media presigné
PROXY_PATH_PREFIX = "/api/frigate_em/media"
SIGNER_DOMAIN_KEY = "frigate_em_signer"
PROXY_CLIENT_KEY = "frigate_em_proxy_client"
PROXY_VIEW_KEY = "frigate_em_proxy_registered"
MEDIA_URL_TTL = 3600  # secondes
