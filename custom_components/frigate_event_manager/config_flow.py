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


def _notify_field(hass: object, current: str | None = None) -> object:
    """Retourne un SelectSelector notify ou str selon les services disponibles."""
    notify_services = sorted(
        f"notify.{svc}"
        for svc in hass.services.async_services_for_domain("notify")  # type: ignore[union-attr]
        if svc != "persistent_notification"
    )
    if notify_services:
        return selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=notify_services,
                mode=selector.SelectSelectorMode.DROPDOWN,
            )
        )
    return str


class FrigateEventManagerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow — étape 1 globale, étape 2 par caméra."""

    VERSION = 1

    @staticmethod
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> "FrigateEventManagerOptionsFlow":
        """Retourne le handler d'options flow pour cet entry."""
        return FrigateEventManagerOptionsFlow(config_entry)

    async def async_step_user(
        self, user_input: dict | None = None
    ) -> FlowResult:
        """Étape 1 : configuration globale (URL Frigate + notify_target)."""
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        detected_url = _detect_frigate_url(self.hass)
        url_kwargs = {"default": detected_url} if detected_url else {}
        step_schema = vol.Schema(
            {
                vol.Required(CONF_URL, **url_kwargs): str,
                vol.Required(CONF_NOTIFY_TARGET): _notify_field(self.hass),
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


class FrigateEventManagerOptionsFlow(config_entries.OptionsFlow):
    """Options flow — édition d'un entry existant via le bouton Configurer."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialise avec l'entry existant."""
        self._entry = config_entry

    async def async_step_init(
        self, user_input: dict | None = None
    ) -> FlowResult:
        """Formulaire d'édition pré-rempli avec les valeurs courantes."""
        data = self._entry.data
        is_camera = CONF_CAMERA in data

        if user_input is not None:
            # Merge les nouvelles valeurs dans entry.data et recharge
            new_data = {**data, **user_input}
            if is_camera:
                new_data[CONF_NOTIFY_TARGET] = user_input.get(CONF_NOTIFY_TARGET) or None
            self.hass.config_entries.async_update_entry(self._entry, data=new_data)
            return self.async_create_entry(title="", data={})

        if is_camera:
            # Entrée caméra : seul notify_target est modifiable
            current_notify = data.get(CONF_NOTIFY_TARGET) or ""
            schema = vol.Schema(
                {
                    vol.Optional(CONF_NOTIFY_TARGET, default=current_notify): str,
                }
            )
        else:
            # Entrée globale : URL + notify_target
            schema = vol.Schema(
                {
                    vol.Required(CONF_URL, default=data.get(CONF_URL, "")): str,
                    vol.Required(
                        CONF_NOTIFY_TARGET, default=data.get(CONF_NOTIFY_TARGET, "")
                    ): _notify_field(self.hass),
                }
            )

        return self.async_show_form(step_id="init", data_schema=schema, errors={})
