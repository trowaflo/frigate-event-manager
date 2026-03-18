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
