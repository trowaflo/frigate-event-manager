"""Constantes pour l'intégration Frigate Event Manager."""

DOMAIN = "frigate_event_manager"

# Clés de configuration
CONF_MQTT_TOPIC = "mqtt_topic"
CONF_NOTIFY_TARGET = "notify_target"
CONF_SEVERITY_FILTER = "severity_filter"
CONF_ZONES = "zones"
CONF_LABELS = "labels"
CONF_DISABLE_TIMES = "disable_times"
CONF_COOLDOWN = "cooldown"

# Valeurs par défaut
DEFAULT_MQTT_TOPIC = "frigate/reviews"
DEFAULT_COOLDOWN = 60
DEFAULT_SEVERITY_FILTER: list[str] = []  # liste vide = tout accepter
DEFAULT_ZONES: list[str] = []
DEFAULT_LABELS: list[str] = []
DEFAULT_DISABLE_TIMES: list[str] = []
