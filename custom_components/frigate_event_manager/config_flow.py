"""Config flow pour l'intégration Frigate Event Manager."""

from __future__ import annotations

import aiohttp
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from . import DOMAIN

DEFAULT_URL = "http://localhost"
DEFAULT_PORT = 5555

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required("url", default=DEFAULT_URL): str,
        vol.Required("port", default=DEFAULT_PORT): int,
    }
)


class FrigateEventManagerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Gère la configuration de l'intégration Frigate Event Manager."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict | None = None
    ) -> FlowResult:
        """Étape initiale : saisie de l'URL et du port du addon Go."""
        errors: dict[str, str] = {}

        if user_input is not None:
            url = user_input["url"].rstrip("/")
            port = user_input["port"]
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        f"{url}:{port}/api/stats", timeout=aiohttp.ClientTimeout(total=5)
                    ) as resp:
                        if resp.status != 200:
                            errors["base"] = "cannot_connect"
            except aiohttp.ClientError:
                errors["base"] = "cannot_connect"

            if not errors:
                return self.async_create_entry(
                    title="Frigate Event Manager",
                    data={"url": url, "port": port},
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_SCHEMA,
            errors=errors,
        )
