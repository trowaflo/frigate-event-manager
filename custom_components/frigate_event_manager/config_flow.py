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
    CONF_COOLDOWN,
    CONF_CRITICAL_TEMPLATE,
    CONF_DEBOUNCE,
    CONF_DISABLED_HOURS,
    CONF_LABELS,
    CONF_NOTIF_MESSAGE,
    CONF_NOTIF_TITLE,
    CONF_NOTIFY_TARGET,
    CONF_PASSWORD,
    CONF_SEVERITY,
    CONF_SILENT_DURATION,
    CONF_TAP_ACTION,
    CONF_URL,
    CONF_USERNAME,
    CONF_ZONES,
    DEFAULT_SEVERITY,
    DEFAULT_SILENT_DURATION,
    DEFAULT_TAP_ACTION,
    DEFAULT_THROTTLE_COOLDOWN,
    DOMAIN,
    PERSISTENT_NOTIFICATION,
    SEVERITY_OPTIONS,
    SUBENTRY_TYPE_CAMERA,
    TAP_ACTION_OPTIONS,
)
from .frigate_client import FrigateClient

# Options statiques pour les heures bloquées (0-23)
_HOUR_OPTIONS = [str(h) for h in range(24)]


def _parse_csv_str(value: str) -> list[str]:
    """Parse une string CSV en liste de strings."""
    return [x.strip() for x in value.split(",") if x.strip()]


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


def _build_configure_schema(
    notify_options: list[str],
    zones: list[str],
    labels: list[str],
    *,
    default_notify: str = PERSISTENT_NOTIFICATION,
    default_zones: list[str] | None = None,
    default_labels: list[str] | None = None,
    default_hours: list[str] | None = None,
    default_severity: list[str] | None = None,
    default_title: str = "",
    default_message: str = "",
    default_critical_template: str = "",
    default_tap: str = DEFAULT_TAP_ACTION,
    default_cooldown: int = DEFAULT_THROTTLE_COOLDOWN,
    default_debounce: int = 0,
    default_silent: int = DEFAULT_SILENT_DURATION,
) -> vol.Schema:
    """Construit le schéma de la step configure (ajout ou reconfigure).

    Si zones ou labels sont vides (Frigate ne retourne rien), bascule sur
    un champ texte libre pour ne pas bloquer l'utilisateur.
    """
    zones_field: object = (
        selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=zones,
                multiple=True,
                mode=selector.SelectSelectorMode.LIST,
            )
        )
        if zones
        else str
    )
    labels_field: object = (
        selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=labels,
                multiple=True,
                mode=selector.SelectSelectorMode.LIST,
            )
        )
        if labels
        else str
    )

    # Valeurs par défaut pour les champs multi-select
    zones_default: list[str] | str = (default_zones or []) if zones else ",".join(default_zones or [])
    labels_default: list[str] | str = (default_labels or []) if labels else ",".join(default_labels or [])

    return vol.Schema({
        vol.Required(
            CONF_NOTIFY_TARGET, default=default_notify
        ): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=notify_options,
                mode=selector.SelectSelectorMode.DROPDOWN,
            )
        ),
        vol.Optional(CONF_ZONES, default=zones_default): zones_field,
        vol.Optional(CONF_LABELS, default=labels_default): labels_field,
        vol.Optional(
            CONF_DISABLED_HOURS, default=default_hours or []
        ): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=_HOUR_OPTIONS,
                multiple=True,
                mode=selector.SelectSelectorMode.LIST,
            )
        ),
        vol.Optional(
            CONF_SEVERITY, default=default_severity if default_severity is not None else DEFAULT_SEVERITY
        ): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=SEVERITY_OPTIONS,
                multiple=True,
                mode=selector.SelectSelectorMode.LIST,
                translation_key=CONF_SEVERITY,
            )
        ),
        vol.Optional(CONF_NOTIF_TITLE, default=default_title): str,
        vol.Optional(CONF_NOTIF_MESSAGE, default=default_message): str,
        vol.Optional(
            CONF_CRITICAL_TEMPLATE, default=default_critical_template
        ): selector.TemplateSelector(),
        vol.Required(CONF_TAP_ACTION, default=default_tap): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=TAP_ACTION_OPTIONS,
                mode=selector.SelectSelectorMode.LIST,
                translation_key=CONF_TAP_ACTION,
            )
        ),
        vol.Optional(
            CONF_COOLDOWN, default=default_cooldown
        ): selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=0,
                max=3600,
                mode=selector.NumberSelectorMode.BOX,
                unit_of_measurement="s",
            )
        ),
        vol.Optional(CONF_DEBOUNCE, default=default_debounce): selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=0,
                max=60,
                mode=selector.NumberSelectorMode.BOX,
                unit_of_measurement="s",
            )
        ),
        vol.Optional(
            CONF_SILENT_DURATION, default=default_silent
        ): selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=0,
                max=480,
                mode=selector.NumberSelectorMode.BOX,
                unit_of_measurement="min",
            )
        ),
    })


def _parse_configure_input(
    user_input: dict[str, Any],
    zones_available: list[str],
    labels_available: list[str],
) -> dict[str, Any]:
    """Parse les données du formulaire configure en données subentry propres.

    Gère le fallback texte libre si zones/labels étaient vides (pas de multi-select).
    """
    # Zones : SelectSelector → list[str] direct ; champ texte → CSV
    raw_zones = user_input.get(CONF_ZONES, [])
    if zones_available:
        zones: list[str] = raw_zones if isinstance(raw_zones, list) else []
    else:
        zones = _parse_csv_str(raw_zones if isinstance(raw_zones, str) else "")

    # Labels : idem
    raw_labels = user_input.get(CONF_LABELS, [])
    if labels_available:
        labels: list[str] = raw_labels if isinstance(raw_labels, list) else []
    else:
        labels = _parse_csv_str(raw_labels if isinstance(raw_labels, str) else "")

    # Heures : SelectSelector retourne list[str] → convertir en list[int]
    raw_hours = user_input.get(CONF_DISABLED_HOURS, [])
    disabled_hours: list[int] = [int(h) for h in raw_hours if str(h).isdigit()]

    return {
        CONF_NOTIFY_TARGET: user_input[CONF_NOTIFY_TARGET],
        CONF_ZONES: zones,
        CONF_LABELS: labels,
        CONF_DISABLED_HOURS: disabled_hours,
        CONF_SEVERITY: user_input.get(CONF_SEVERITY, DEFAULT_SEVERITY),
        CONF_NOTIF_TITLE: user_input.get(CONF_NOTIF_TITLE, "").strip() or None,
        CONF_NOTIF_MESSAGE: user_input.get(CONF_NOTIF_MESSAGE, "").strip() or None,
        CONF_CRITICAL_TEMPLATE: user_input.get(CONF_CRITICAL_TEMPLATE, "").strip() or None,
        CONF_TAP_ACTION: user_input.get(CONF_TAP_ACTION, DEFAULT_TAP_ACTION),
        CONF_COOLDOWN: int(user_input.get(CONF_COOLDOWN, DEFAULT_THROTTLE_COOLDOWN)),
        CONF_DEBOUNCE: int(user_input.get(CONF_DEBOUNCE, 0)),
        CONF_SILENT_DURATION: int(
            user_input.get(CONF_SILENT_DURATION, DEFAULT_SILENT_DURATION)
        ),
    }


class FrigateEventManagerConfigFlow(ConfigFlow, domain=DOMAIN):
    """Config flow — 1 étape : connexion Frigate."""

    VERSION = 3
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
        """Étape unique : connexion Frigate (URL + credentials)."""
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
                return self.async_create_entry(
                    title="Frigate Event Manager",
                    data={
                        CONF_URL: user_input[CONF_URL],
                        CONF_USERNAME: user_input.get(CONF_USERNAME) or None,
                        CONF_PASSWORD: user_input.get(CONF_PASSWORD) or None,
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_URL, default=frigate.get("url", "")): str,
                vol.Optional(CONF_USERNAME, default=frigate.get("username") or ""): str,
                vol.Optional(CONF_PASSWORD, default=frigate.get("password") or ""): str,
            }),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Reconfiguration : modifier URL et credentials Frigate."""
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
                    },
                )

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
            }),
            errors=errors,
        )


class CameraSubentryFlow(ConfigSubentryFlow):
    """Subentry flow — ajout en 2 étapes et reconfiguration d'une caméra."""

    def __init__(self) -> None:
        """Initialise le flow caméra."""
        super().__init__()
        self._camera: str = ""
        # Zones et labels récupérés depuis Frigate (mémorisés pour le parsing)
        self._zones_available: list[str] = []
        self._labels_available: list[str] = []
        # Vrai si Frigate était inaccessible lors du fetch de la config caméra
        self._frigate_unreachable: bool = False

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Étape 1 — sélection de la caméra uniquement."""
        entry = self._get_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            # Stocker la caméra choisie et passer à l'étape configure
            self._camera = user_input[CONF_CAMERA]
            return await self.async_step_configure()

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
            }),
            errors=errors,
        )

    async def async_step_configure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Étape 2 — configuration (zones, labels, heures, notifications)."""
        entry = self._get_entry()

        if user_input is not None:
            parsed = _parse_configure_input(
                user_input, self._zones_available, self._labels_available
            )
            return self.async_create_entry(
                title=f"Caméra {self._camera}",
                data={
                    CONF_CAMERA: self._camera,
                    **parsed,
                },
                unique_id=f"fem_{self._camera}",
            )

        # Récupérer les zones et labels depuis Frigate pour cette caméra
        try:
            cam_config = await FrigateClient(
                entry.data[CONF_URL],
                entry.data.get(CONF_USERNAME),
                entry.data.get(CONF_PASSWORD),
            ).get_camera_config(self._camera)
            self._zones_available = cam_config.get("zones", [])
            self._labels_available = cam_config.get("labels", [])
            self._frigate_unreachable = False
        except (aiohttp.ClientError, TimeoutError, ValueError):
            # Fallback : l'utilisateur saisira les zones/labels manuellement
            self._zones_available = []
            self._labels_available = []
            self._frigate_unreachable = True

        notify_options = _get_notify_options(self.hass)
        warning = "⚠ Frigate inaccessible — saisissez les zones et labels manuellement." if self._frigate_unreachable else ""

        return self.async_show_form(
            step_id="configure",
            data_schema=_build_configure_schema(
                notify_options,
                self._zones_available,
                self._labels_available,
            ),
            description_placeholders={"warning": warning},
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Reconfiguration d'une caméra — caméra connue, fetch direct + multi-select pré-rempli."""
        subentry = self._get_reconfigure_subentry()
        entry = self._get_entry()
        camera = subentry.data[CONF_CAMERA]

        if user_input is not None:
            parsed = _parse_configure_input(
                user_input, self._zones_available, self._labels_available
            )
            return self.async_update_and_abort(
                entry,
                subentry,
                data_updates=parsed,
            )

        # Récupérer les zones et labels depuis Frigate
        try:
            cam_config = await FrigateClient(
                entry.data[CONF_URL],
                entry.data.get(CONF_USERNAME),
                entry.data.get(CONF_PASSWORD),
            ).get_camera_config(camera)
            self._zones_available = cam_config.get("zones", [])
            self._labels_available = cam_config.get("labels", [])
        except (aiohttp.ClientError, TimeoutError, ValueError):
            self._zones_available = []
            self._labels_available = []

        notify_options = _get_notify_options(self.hass)

        # Valeurs existantes pré-sélectionnées
        existing_zones = subentry.data.get(CONF_ZONES, [])
        existing_labels = subentry.data.get(CONF_LABELS, [])
        # Heures : list[int] → list[str] pour le selector
        existing_hours = [str(h) for h in subentry.data.get(CONF_DISABLED_HOURS, [])]
        existing_severity = subentry.data.get(CONF_SEVERITY, DEFAULT_SEVERITY)

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_build_configure_schema(
                notify_options,
                self._zones_available,
                self._labels_available,
                default_notify=subentry.data.get(CONF_NOTIFY_TARGET, PERSISTENT_NOTIFICATION),
                default_zones=existing_zones,
                default_labels=existing_labels,
                default_hours=existing_hours,
                default_severity=existing_severity,
                default_title=subentry.data.get(CONF_NOTIF_TITLE) or "",
                default_message=subentry.data.get(CONF_NOTIF_MESSAGE) or "",
                default_critical_template=subentry.data.get(CONF_CRITICAL_TEMPLATE) or "",
                default_tap=subentry.data.get(CONF_TAP_ACTION, DEFAULT_TAP_ACTION),
                default_cooldown=subentry.data.get(CONF_COOLDOWN, DEFAULT_THROTTLE_COOLDOWN),
                default_debounce=subentry.data.get(CONF_DEBOUNCE, 0),
                default_silent=subentry.data.get(CONF_SILENT_DURATION, DEFAULT_SILENT_DURATION),
            ),
        )
