"""Config flow pour l'intégration Frigate Event Manager."""

from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from .const import CONF_CAMERA, CONF_NOTIFY_TARGET, CONF_URL, DOMAIN


def _detect_frigate_url(hass: object) -> str | None:
    """Retourne l'URL Frigate depuis l'intégration HA si présente."""
    for entry in hass.config_entries.async_entries("frigate"):  # type: ignore[union-attr]
        url = entry.data.get("url") or entry.data.get("host")
        if url:
            return url
    return None


def _discover_frigate_cameras(hass: object) -> list[str]:
    """Retourne les noms de caméras depuis les entités camera.frigate_* de HA."""
    return sorted(
        eid.removeprefix("camera.frigate_")
        for eid in hass.states.async_entity_ids("camera")  # type: ignore[union-attr]
        if eid.startswith("camera.frigate_")
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

        # URL pré-remplie depuis l'intégration Frigate (modifiable)
        detected_url = _detect_frigate_url(self.hass)

        # Sélecteur notify dynamique
        notify_services = sorted(
            f"notify.{svc}"
            for svc in self.hass.services.async_services_for_domain("notify")
            if svc != "persistent_notification"
        )
        notify_field: object = (
            selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=notify_services,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            )
            if notify_services
            else str
        )

        url_kwargs = {"default": detected_url} if detected_url else {}
        step_schema = vol.Schema(
            {
                vol.Required(CONF_URL, **url_kwargs): str,
                vol.Required(CONF_NOTIFY_TARGET): notify_field,
            }
        )

        if user_input is not None:
            return self.async_create_entry(
                title="Frigate Event Manager",
                data={
                    CONF_URL: user_input[CONF_URL],
                    CONF_NOTIFY_TARGET: user_input[CONF_NOTIFY_TARGET],
                },
            )

        return self.async_show_form(
            step_id="user",
            data_schema=step_schema,
            errors={},
        )

    async def async_step_camera(
        self, user_input: dict | None = None
    ) -> FlowResult:
        """Étape 2 : ajout d'une caméra (répétable via async_init source='camera')."""
        global_entry = self.hass.config_entries.async_entry_for_domain_unique_id(
            DOMAIN, DOMAIN
        )
        if global_entry is None:
            return self.async_abort(reason="missing_global_entry")

        camera_names = _discover_frigate_cameras(self.hass)

        if user_input is not None:
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

        camera_field: object = (
            selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=camera_names,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            )
            if camera_names
            else str
        )
        step_schema = vol.Schema(
            {
                vol.Required(CONF_CAMERA): camera_field,
                vol.Optional(CONF_NOTIFY_TARGET, default=""): str,
            }
        )

        return self.async_show_form(
            step_id="camera",
            data_schema=step_schema,
            errors={},
        )
