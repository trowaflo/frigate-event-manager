"""Config flow pour l'intégration Frigate Event Manager."""

from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from .const import (
    CONF_COOLDOWN,
    CONF_DISABLE_TIMES,
    CONF_LABELS,
    CONF_MQTT_TOPIC,
    CONF_NOTIFY_TARGET,
    CONF_SEVERITY_FILTER,
    CONF_ZONES,
    DEFAULT_COOLDOWN,
    DEFAULT_MQTT_TOPIC,
    DOMAIN,
)

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_MQTT_TOPIC, default=DEFAULT_MQTT_TOPIC): str,
        vol.Required(CONF_NOTIFY_TARGET): str,
        vol.Optional(CONF_SEVERITY_FILTER, default=[]): vol.All(
            vol.Coerce(list), [str]
        ),
        vol.Optional(CONF_ZONES, default=[]): vol.All(vol.Coerce(list), [str]),
        vol.Optional(CONF_LABELS, default=[]): vol.All(vol.Coerce(list), [str]),
        vol.Optional(CONF_DISABLE_TIMES, default=[]): vol.All(
            vol.Coerce(list), [str]
        ),
        vol.Optional(CONF_COOLDOWN, default=DEFAULT_COOLDOWN): vol.All(
            int, vol.Range(min=0)
        ),
    }
)


class FrigateEventManagerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow — saisie des paramètres MQTT et de notification."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict | None = None
    ) -> FlowResult:
        """Étape unique : formulaire de configuration complet."""
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        errors: dict[str, str] = {}

        if user_input is not None:
            if user_input.get(CONF_COOLDOWN, 0) < 0:
                errors[CONF_COOLDOWN] = "cooldown_invalid"
            else:
                return self.async_create_entry(
                    title="Frigate Event Manager",
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_SCHEMA,
            errors=errors,
        )
