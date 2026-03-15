"""Config flow pour l'intégration Frigate Event Manager."""

from __future__ import annotations

import aiohttp
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from .const import ADDON_PORT, DOMAIN
from . import get_addon_url

STEP_MANUAL_SCHEMA = vol.Schema(
    {
        vol.Required("url", default="http://192.168.1.x"): str,
        vol.Required("port", default=ADDON_PORT): int,
    }
)


async def _test_connection(url: str) -> bool:
    """Vérifie que l'addon Go répond sur /api/stats."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{url}/api/stats",
                timeout=aiohttp.ClientTimeout(total=5),
            ) as resp:
                return resp.status == 200
    except aiohttp.ClientError:
        return False


class FrigateEventManagerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow — tente l'auto-découverte Supervisor, sinon saisie manuelle."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict | None = None
    ) -> FlowResult:
        """Étape 1 : tentative d'auto-découverte via Supervisor."""
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        # Auto-découverte via Supervisor (HA OS / Supervised)
        addon_url = await get_addon_url()
        if addon_url and await _test_connection(addon_url):
            return self.async_create_entry(
                title="Frigate Event Manager",
                data={"url": addon_url},
            )

        # Fallback : saisie manuelle
        return await self.async_step_manual(user_input)

    async def async_step_manual(
        self, user_input: dict | None = None
    ) -> FlowResult:
        """Étape 2 (fallback) : saisie manuelle de l'URL et du port."""
        errors: dict[str, str] = {}

        if user_input is not None:
            url = f"{user_input['url'].rstrip('/')}:{user_input['port']}"
            if await _test_connection(url):
                return self.async_create_entry(
                    title="Frigate Event Manager",
                    data={"url": url},
                )
            errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="manual",
            data_schema=STEP_MANUAL_SCHEMA,
            errors=errors,
        )
