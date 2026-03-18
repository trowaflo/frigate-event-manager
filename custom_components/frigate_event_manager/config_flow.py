"""Config flow pour Frigate Event Manager."""

from __future__ import annotations

from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    SubentryFlowResult,
)
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    CONF_CAMERA,
    CONF_DISABLED_HOURS,
    CONF_LABELS,
    CONF_NOTIFY_TARGET,
    CONF_PASSWORD,
    CONF_URL,
    CONF_USERNAME,
    CONF_ZONES,
    DOMAIN,
    PERSISTENT_NOTIFICATION,
    SUBENTRY_TYPE_CAMERA,
)
from .frigate_client import FrigateClient


def _parse_csv_str(value: str) -> list[str]:
    """Parse une string CSV en liste de strings."""
    return [x.strip() for x in value.split(",") if x.strip()]


def _parse_csv_int(value: str) -> list[int]:
    """Parse une string CSV en liste d'entiers (ex: '0,1,2' → [0,1,2])."""
    if not value.strip():
        return []
    try:
        return [int(x.strip()) for x in value.split(",") if x.strip()]
    except ValueError:
        return []


def _detect_frigate_config(hass: object) -> dict[str, str | None]:
    """Retourne url/username/password depuis l'intégration Frigate HA si présente."""
    for entry in hass.config_entries.async_entries("frigate"):  # type: ignore[union-attr]
        url = entry.data.get("url") or entry.data.get("host")
        if url:
            return {
                "url": url,
                "username": entry.data.get("username"),
                "password": entry.data.get("password"),
            }
    return {}


def _get_notify_options(hass: object) -> list[str]:
    """Retourne la liste des services notify disponibles + persistent_notification."""
    services = sorted(
        f"notify.{svc}"
        for svc in hass.services.async_services_for_domain("notify")  # type: ignore[union-attr]
        if svc != "persistent_notification"
    )
    # persistent_notification toujours disponible en premier
    return [PERSISTENT_NOTIFICATION] + services


def _configured_cameras(entry: ConfigEntry) -> set[str]:
    """Retourne les noms de caméras déjà configurées dans les subentries."""
    return {
        subentry.data[CONF_CAMERA]
        for subentry in entry.subentries.values()
        if CONF_CAMERA in subentry.data
    }


class FrigateEventManagerConfigFlow(ConfigFlow, domain=DOMAIN):
    """Config flow — 2 étapes : connexion Frigate + notification par défaut."""

    VERSION = 2
    MINOR_VERSION = 1

    def __init__(self) -> None:
        """Initialise le flow."""
        self._url: str = ""
        self._username: str | None = None
        self._password: str | None = None

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Retourne les types de subentry supportés (caméras)."""
        return {SUBENTRY_TYPE_CAMERA: CameraSubentryFlow}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Étape 1 : connexion Frigate (URL + credentials)."""
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        frigate = _detect_frigate_config(self.hass)
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                await FrigateClient(
                    user_input[CONF_URL],
                    user_input.get(CONF_USERNAME) or None,
                    user_input.get(CONF_PASSWORD) or None,
                ).get_cameras()
            except aiohttp.ClientResponseError as err:
                errors["base"] = "invalid_auth" if err.status == 401 else "cannot_connect"
            except (aiohttp.ClientError, TimeoutError, ValueError):
                errors["base"] = "cannot_connect"
            else:
                self._url = user_input[CONF_URL]
                self._username = user_input.get(CONF_USERNAME) or None
                self._password = user_input.get(CONF_PASSWORD) or None
                return await self.async_step_notify()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_URL, default=frigate.get("url", "")): str,
                vol.Optional(CONF_USERNAME, default=frigate.get("username") or ""): str,
                vol.Optional(CONF_PASSWORD, default=frigate.get("password") or ""): str,
            }),
            errors=errors,
        )

    async def async_step_notify(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Étape 2 : sélection du service de notification par défaut."""
        if user_input is not None:
            return self.async_create_entry(
                title="Frigate Event Manager",
                data={
                    CONF_URL: self._url,
                    CONF_USERNAME: self._username,
                    CONF_PASSWORD: self._password,
                    CONF_NOTIFY_TARGET: user_input[CONF_NOTIFY_TARGET],
                },
            )

        notify_options = _get_notify_options(self.hass)
        return self.async_show_form(
            step_id="notify",
            data_schema=vol.Schema({
                vol.Required(
                    CONF_NOTIFY_TARGET,
                    default=notify_options[0] if notify_options else PERSISTENT_NOTIFICATION,
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=notify_options,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
            }),
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Reconfiguration : modifier URL, credentials et notify par défaut."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                await FrigateClient(
                    user_input[CONF_URL],
                    user_input.get(CONF_USERNAME) or None,
                    user_input.get(CONF_PASSWORD) or None,
                ).get_cameras()
            except aiohttp.ClientResponseError as err:
                errors["base"] = "invalid_auth" if err.status == 401 else "cannot_connect"
            except (aiohttp.ClientError, TimeoutError, ValueError):
                errors["base"] = "cannot_connect"
            else:
                return self.async_update_reload_and_abort(
                    entry,
                    data_updates={
                        CONF_URL: user_input[CONF_URL],
                        CONF_USERNAME: user_input.get(CONF_USERNAME) or None,
                        CONF_PASSWORD: user_input.get(CONF_PASSWORD) or None,
                        CONF_NOTIFY_TARGET: user_input[CONF_NOTIFY_TARGET],
                    },
                )

        notify_options = _get_notify_options(self.hass)
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema({
                vol.Required(CONF_URL, default=entry.data.get(CONF_URL, "")): str,
                vol.Optional(
                    CONF_USERNAME, default=entry.data.get(CONF_USERNAME) or ""
                ): str,
                vol.Optional(
                    CONF_PASSWORD, default=entry.data.get(CONF_PASSWORD) or ""
                ): str,
                vol.Required(
                    CONF_NOTIFY_TARGET,
                    default=entry.data.get(CONF_NOTIFY_TARGET, PERSISTENT_NOTIFICATION),
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=notify_options,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
            }),
            errors=errors,
        )


class CameraSubentryFlow(ConfigSubentryFlow):
    """Subentry flow — ajout et reconfiguration d'une caméra."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Formulaire d'ajout d'une caméra."""
        entry = self._get_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            camera_name = user_input[CONF_CAMERA]
            notify = user_input[CONF_NOTIFY_TARGET]
            return self.async_create_entry(
                title=f"Caméra {camera_name}",
                data={
                    CONF_CAMERA: camera_name,
                    CONF_NOTIFY_TARGET: notify,
                    CONF_ZONES: _parse_csv_str(user_input.get(CONF_ZONES, "")),
                    CONF_LABELS: _parse_csv_str(user_input.get(CONF_LABELS, "")),
                    CONF_DISABLED_HOURS: _parse_csv_int(user_input.get(CONF_DISABLED_HOURS, "")),
                },
                unique_id=f"fem_{camera_name}",
            )

        # Caméras disponibles = toutes les caméras Frigate - déjà configurées
        try:
            all_cameras = await FrigateClient(
                entry.data[CONF_URL],
                entry.data.get(CONF_USERNAME),
                entry.data.get(CONF_PASSWORD),
            ).get_cameras()
        except aiohttp.ClientResponseError as err:
            errors["base"] = "invalid_auth" if err.status == 401 else "cannot_connect"
            all_cameras = []
        except (aiohttp.ClientError, TimeoutError, ValueError):
            errors["base"] = "cannot_connect"
            all_cameras = []

        configured = _configured_cameras(entry)
        available = sorted(set(all_cameras) - configured)

        if not available and not errors:
            return self.async_abort(reason="no_cameras_available")

        notify_options = _get_notify_options(self.hass)
        default_notify = entry.data.get(CONF_NOTIFY_TARGET, PERSISTENT_NOTIFICATION)

        camera_field: object = (
            selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=available,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            )
            if available
            else str
        )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_CAMERA): camera_field,
                vol.Required(
                    CONF_NOTIFY_TARGET, default=default_notify
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=notify_options,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Optional(CONF_ZONES, default=""): str,
                vol.Optional(CONF_LABELS, default=""): str,
                vol.Optional(CONF_DISABLED_HOURS, default=""): str,
            }),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Reconfiguration d'une caméra — modifier le service de notification."""
        subentry = self._get_reconfigure_subentry()

        if user_input is not None:
            return self.async_update_and_abort(
                self._get_entry(),
                subentry,
                data_updates={
                    CONF_NOTIFY_TARGET: user_input[CONF_NOTIFY_TARGET],
                    CONF_ZONES: _parse_csv_str(user_input.get(CONF_ZONES, "")),
                    CONF_LABELS: _parse_csv_str(user_input.get(CONF_LABELS, "")),
                    CONF_DISABLED_HOURS: _parse_csv_int(user_input.get(CONF_DISABLED_HOURS, "")),
                },
            )

        notify_options = _get_notify_options(self.hass)
        existing_zones = ",".join(subentry.data.get(CONF_ZONES, []))
        existing_labels = ",".join(subentry.data.get(CONF_LABELS, []))
        existing_hours = ",".join(str(h) for h in subentry.data.get(CONF_DISABLED_HOURS, []))
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema({
                vol.Required(
                    CONF_NOTIFY_TARGET,
                    default=subentry.data.get(CONF_NOTIFY_TARGET, PERSISTENT_NOTIFICATION),
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=notify_options,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Optional(CONF_ZONES, default=existing_zones): str,
                vol.Optional(CONF_LABELS, default=existing_labels): str,
                vol.Optional(CONF_DISABLED_HOURS, default=existing_hours): str,
            }),
        )
