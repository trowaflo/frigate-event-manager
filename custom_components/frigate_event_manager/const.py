"""Constantes pour l'intégration Frigate Event Manager."""

DOMAIN = "frigate_event_manager"

# Clés de configuration
CONF_URL = "url"
CONF_NOTIFY_TARGET = "notify_target"
CONF_CAMERA = "camera"

# Constantes conservées — encore utilisées par coordinator.py et __init__.py (T-508 les migrera)
CONF_MQTT_TOPIC = "mqtt_topic"
DEFAULT_MQTT_TOPIC = "frigate/reviews"
