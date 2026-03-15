"""Constantes pour l'intégration Frigate Event Manager."""

DOMAIN = "frigate_event_manager"

# Slug de l'addon Go dans HA Supervisor (local_ + slug du config.yaml)
ADDON_SLUG = "local_frigate-event-manager"

# URL interne du Supervisor (accessible depuis HA Core)
SUPERVISOR_URL = "http://supervisor"

# Port HTTP du addon Go
ADDON_PORT = 5555
