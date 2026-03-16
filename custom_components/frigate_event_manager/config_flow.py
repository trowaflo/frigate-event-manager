"""Config flow pour l'intégration Frigate Event Manager."""

from __future__ import annotations

import aiohttp
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from .const import CONF_CAMERA, CONF_NOTIFY_TARGET, CONF_URL, DOMAIN
from .frigate_client import FrigateClient

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_URL): str,
        vol.Required(CONF_NOTIFY_TARGET): str,
    }
)


class FrigateEventManagerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow — étape 1 globale, étape 2 par caméra."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict | None = None
    ) -> FlowResult:
        """Étape 1 : configuration globale (URL Frigate + notify_target)."""
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        errors: dict[str, str] = {}

        if user_input is not None:
            url = user_input[CONF_URL]
            try:
                await FrigateClient(url).get_cameras()
            except aiohttp.ClientError:
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(
                    title="Frigate Event Manager",
                    data={
                        CONF_URL: url,
                        CONF_NOTIFY_TARGET: user_input[CONF_NOTIFY_TARGET],
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_SCHEMA,
            errors=errors,
        )

    async def async_step_camera(
        self, user_input: dict | None = None
    ) -> FlowResult:
        """Étape 2 : ajout d'une caméra (répétable via async_init source='camera').

        Ce step est déclenché depuis l'orchestrateur, pas depuis l'UI utilisateur.
        """
        errors: dict[str, str] = {}

        # Récupère l'URL depuis l'entrée globale déjà configurée
        global_entry = self.hass.config_entries.async_entry_for_domain_unique_id(
            DOMAIN, DOMAIN
        )
        if global_entry is None:
            return self.async_abort(reason="missing_global_entry")

        frigate_url: str = global_entry.data[CONF_URL]

        # Récupère la liste des caméras disponibles
        camera_names: list[str] = []
        if frigate_url:
            try:
                camera_names = await FrigateClient(frigate_url).get_cameras()
            except aiohttp.ClientError:
                errors["base"] = "cannot_connect"

        if user_input is not None and not errors:
            camera_name: str = user_input[CONF_CAMERA]
            notify_target: str | None = user_input.get(CONF_NOTIFY_TARGET) or None

            await self.async_set_unique_id(f"fem_{camera_name}")
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=f"Caméra {camera_name}",
                data={
                    CONF_CAMERA: camera_name,
                    CONF_NOTIFY_TARGET: notify_target,
                },
            )

        camera_selector = vol.In(camera_names) if camera_names else str
        step_schema = vol.Schema(
            {
                vol.Required(CONF_CAMERA): camera_selector,
                vol.Optional(CONF_NOTIFY_TARGET, default=""): str,
            }
        )

        return self.async_show_form(
            step_id="camera",
            data_schema=step_schema,
            errors=errors,
        )
