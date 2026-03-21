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
    ACTION_BTN_OPTIONS,
    CONF_ACTION_BTN1,
    CONF_ACTION_BTN2,
    CONF_ACTION_BTN3,
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
    DEFAULT_ACTION_BTN,
    DEFAULT_DEBOUNCE,
    DEFAULT_SEVERITY,
    DEFAULT_SILENT_DURATION,
    DEFAULT_TAP_ACTION,
    DEFAULT_THROTTLE_COOLDOWN,
    DOMAIN,
    PERSISTENT_NOTIFICATION,
    SUBENTRY_TYPE_CAMERA,
    TAP_ACTION_OPTIONS,
)
from .frigate_client import FrigateClient

# Options statiques pour les heures bloquées (0-23)
_HOUR_OPTIONS = [str(h) for h in range(24)]

# Options pour le critical_template — presets prédéfinis + custom
_CRITICAL_TEMPLATE_NEVER = "false"
_CRITICAL_TEMPLATE_ALWAYS = "true"
_CRITICAL_TEMPLATE_NIGHT_ONLY = "{{'false' if now().hour in [8,9,10,11,12,13,14,15,16,17,18] else 'true'}}"
_CRITICAL_TEMPLATE_CUSTOM = "custom"

CRITICAL_TEMPLATE_PRESET_OPTIONS = [
    _CRITICAL_TEMPLATE_NEVER,
    _CRITICAL_TEMPLATE_ALWAYS,
    _CRITICAL_TEMPLATE_NIGHT_ONLY,
    _CRITICAL_TEMPLATE_CUSTOM,
]


def _parse_csv_str(value: str) -> list[str]:
    """Parse une string CSV en liste de strings."""
    return [x.strip() for x in value.split(",") if x.strip()]


def _parse_filters_input(
    user_input: dict[str, Any],
    zones_available: list[str],
    labels_available: list[str],
) -> dict[str, Any]:
    """Parse les champs zones/labels/heures/severity depuis user_input.

    Gère le double mode : SelectSelector (liste disponible) ou texte libre CSV (fallback).
    """
    raw_zones = user_input.get(CONF_ZONES, [])
    if zones_available:
        zones: list[str] = raw_zones if isinstance(raw_zones, list) else []
    else:
        zones = _parse_csv_str(raw_zones if isinstance(raw_zones, str) else "")

    raw_labels = user_input.get(CONF_LABELS, [])
    if labels_available:
        labels: list[str] = raw_labels if isinstance(raw_labels, list) else []
    else:
        labels = _parse_csv_str(raw_labels if isinstance(raw_labels, str) else "")

    raw_hours = user_input.get(CONF_DISABLED_HOURS, [])
    disabled_hours: list[int] = [int(h) for h in raw_hours if str(h).isdigit()]

    raw_severity = user_input.get(CONF_SEVERITY, DEFAULT_SEVERITY)
    severity: list[str] = raw_severity if isinstance(raw_severity, list) else DEFAULT_SEVERITY

    return {
        CONF_ZONES: zones,
        CONF_LABELS: labels,
        CONF_DISABLED_HOURS: disabled_hours,
        CONF_SEVERITY: severity,
    }


def _build_filters_schema(
    configure_data: dict[str, Any],
    zones_available: list[str],
    labels_available: list[str],
) -> vol.Schema:
    """Construit le schéma voluptuous pour l'étape filtres de détection."""
    existing_zones: list[str] = configure_data.get(CONF_ZONES, [])
    existing_labels: list[str] = configure_data.get(CONF_LABELS, [])

    zones_default: list[str] | str = (
        existing_zones if zones_available else ",".join(existing_zones)
    )
    labels_default: list[str] | str = (
        existing_labels if labels_available else ",".join(existing_labels)
    )

    zones_field: object = (
        selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=zones_available,
                multiple=True,
                mode=selector.SelectSelectorMode.LIST,
            )
        )
        if zones_available
        else str
    )
    labels_field: object = (
        selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=labels_available,
                multiple=True,
                mode=selector.SelectSelectorMode.LIST,
            )
        )
        if labels_available
        else str
    )

    return vol.Schema({
        vol.Optional(CONF_ZONES, default=zones_default): zones_field,
        vol.Optional(CONF_LABELS, default=labels_default): labels_field,
        vol.Optional(
            CONF_DISABLED_HOURS,
            default=[str(h) for h in configure_data.get(CONF_DISABLED_HOURS, [])],
        ): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=_HOUR_OPTIONS,
                multiple=True,
                mode=selector.SelectSelectorMode.LIST,
            )
        ),
        vol.Optional(
            CONF_SEVERITY,
            default=configure_data.get(CONF_SEVERITY, DEFAULT_SEVERITY),
        ): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=["alert", "detection"],
                multiple=True,
                mode=selector.SelectSelectorMode.LIST,
            )
        ),
    })


def _build_behavior_schema(configure_data: dict[str, Any]) -> vol.Schema:
    """Construit le schéma voluptuous pour l'étape comportement."""
    return vol.Schema({
        vol.Optional(
            CONF_COOLDOWN,
            default=configure_data.get(CONF_COOLDOWN, DEFAULT_THROTTLE_COOLDOWN),
        ): selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=0,
                max=3600,
                step=1,
                mode=selector.NumberSelectorMode.BOX,
                unit_of_measurement="s",
            )
        ),
        vol.Optional(
            CONF_DEBOUNCE,
            default=configure_data.get(CONF_DEBOUNCE, DEFAULT_DEBOUNCE),
        ): selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=0,
                max=60,
                step=1,
                mode=selector.NumberSelectorMode.BOX,
                unit_of_measurement="s",
            )
        ),
        vol.Optional(
            CONF_SILENT_DURATION,
            default=configure_data.get(CONF_SILENT_DURATION, DEFAULT_SILENT_DURATION),
        ): selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=1,
                max=480,
                step=1,
                mode=selector.NumberSelectorMode.BOX,
                unit_of_measurement="min",
            )
        ),
        vol.Optional(
            CONF_TAP_ACTION,
            default=configure_data.get(CONF_TAP_ACTION, DEFAULT_TAP_ACTION),
        ): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=TAP_ACTION_OPTIONS,
                mode=selector.SelectSelectorMode.LIST,
            )
        ),
        vol.Optional(
            CONF_ACTION_BTN1,
            default=configure_data.get(CONF_ACTION_BTN1, DEFAULT_ACTION_BTN),
        ): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=ACTION_BTN_OPTIONS,
                mode=selector.SelectSelectorMode.LIST,
            )
        ),
        vol.Optional(
            CONF_ACTION_BTN2,
            default=configure_data.get(CONF_ACTION_BTN2, DEFAULT_ACTION_BTN),
        ): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=ACTION_BTN_OPTIONS,
                mode=selector.SelectSelectorMode.LIST,
            )
        ),
        vol.Optional(
            CONF_ACTION_BTN3,
            default=configure_data.get(CONF_ACTION_BTN3, DEFAULT_ACTION_BTN),
        ): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=ACTION_BTN_OPTIONS,
                mode=selector.SelectSelectorMode.LIST,
            )
        ),
    })


def _build_notifications_schema(configure_data: dict[str, Any]) -> vol.Schema:
    """Construit le schéma voluptuous pour l'étape notifications."""
    existing_tpl = configure_data.get(CONF_CRITICAL_TEMPLATE)
    preset_default = _critical_template_to_preset(existing_tpl)
    custom_default = existing_tpl if preset_default == _CRITICAL_TEMPLATE_CUSTOM else ""

    return vol.Schema({
        vol.Optional(
            CONF_NOTIF_TITLE,
            default=configure_data.get(CONF_NOTIF_TITLE) or "",
        ): selector.TemplateSelector(),
        vol.Optional(
            CONF_NOTIF_MESSAGE,
            default=configure_data.get(CONF_NOTIF_MESSAGE) or "",
        ): selector.TemplateSelector(),
        vol.Optional(
            CONF_CRITICAL_TEMPLATE,
            default=preset_default,
        ): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=CRITICAL_TEMPLATE_PRESET_OPTIONS,
                mode=selector.SelectSelectorMode.LIST,
            )
        ),
        vol.Optional(
            "critical_template_custom",
            default=custom_default,
        ): selector.TemplateSelector(),
    })


def _resolve_critical_template(user_input: dict[str, Any]) -> str | None:
    """Résout le preset critical_template en valeur stockable (template ou None)."""
    preset = user_input.get(CONF_CRITICAL_TEMPLATE, _CRITICAL_TEMPLATE_NEVER)
    if preset == _CRITICAL_TEMPLATE_CUSTOM:
        return (user_input.get("critical_template_custom") or "").strip() or None
    if preset == _CRITICAL_TEMPLATE_NEVER:
        return None
    return preset


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


def _critical_template_to_preset(tpl: str | None) -> str:
    """Convertit un template stocké en option de preset (ou 'custom')."""
    if not tpl:
        return _CRITICAL_TEMPLATE_NEVER
    if tpl in CRITICAL_TEMPLATE_PRESET_OPTIONS:
        return tpl
    return _CRITICAL_TEMPLATE_CUSTOM


class FrigateEventManagerConfigFlow(ConfigFlow, domain=DOMAIN):
    """Config flow — 1 étape : connexion Frigate."""

    VERSION = 5
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
    """Subentry flow — ajout en 5 étapes et reconfiguration d'une caméra."""

    def __init__(self) -> None:
        """Initialise le flow caméra."""
        super().__init__()
        self._camera: str = ""
        # Zones et labels récupérés depuis Frigate (mémorisés pour le parsing)
        self._zones_available: list[str] = []
        self._labels_available: list[str] = []
        # Vrai si Frigate était inaccessible lors du fetch de la config caméra
        self._frigate_unreachable: bool = False
        # Dictionnaire accumulateur pour les données inter-étapes
        self._configure_data: dict[str, Any] = {}

    # -----------------------------------------------------------------------
    # Étape 1 — Sélection de la caméra
    # -----------------------------------------------------------------------

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Étape 1 — sélection de la caméra uniquement."""
        entry = self._get_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
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

    # -----------------------------------------------------------------------
    # Étape 2 — Service de notification
    # -----------------------------------------------------------------------

    async def async_step_configure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Étape 2 — service de notification."""
        if user_input is not None:
            self._configure_data[CONF_NOTIFY_TARGET] = user_input[CONF_NOTIFY_TARGET]
            return await self.async_step_configure_filters()

        entry = self._get_entry()

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
            self._zones_available = []
            self._labels_available = []
            self._frigate_unreachable = True

        notify_options = _get_notify_options(self.hass)

        return self.async_show_form(
            step_id="configure",
            data_schema=vol.Schema({
                vol.Required(
                    CONF_NOTIFY_TARGET,
                    default=self._configure_data.get(CONF_NOTIFY_TARGET, PERSISTENT_NOTIFICATION),
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=notify_options,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
            }),
        )

    # -----------------------------------------------------------------------
    # Étape 3 — Filtres de détection
    # -----------------------------------------------------------------------

    async def async_step_configure_filters(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Étape 3 — filtres de détection (zones, labels, heures, severity)."""
        if user_input is not None:
            self._configure_data.update(
                _parse_filters_input(user_input, self._zones_available, self._labels_available)
            )
            return await self.async_step_configure_behavior()

        warning = (
            "⚠ Frigate inaccessible — saisissez les zones et labels manuellement."
            if self._frigate_unreachable
            else ""
        )

        return self.async_show_form(
            step_id="configure_filters",
            data_schema=_build_filters_schema(
                self._configure_data, self._zones_available, self._labels_available
            ),
            description_placeholders={"warning": warning},
        )

    # -----------------------------------------------------------------------
    # Étape 4 — Comportement
    # -----------------------------------------------------------------------

    async def async_step_configure_behavior(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Étape 4 — comportement (cooldown, debounce, silent_duration, tap_action)."""
        if user_input is not None:
            self._configure_data.update({
                CONF_COOLDOWN: int(user_input.get(CONF_COOLDOWN, DEFAULT_THROTTLE_COOLDOWN)),
                CONF_DEBOUNCE: int(user_input.get(CONF_DEBOUNCE, DEFAULT_DEBOUNCE)),
                CONF_SILENT_DURATION: int(user_input.get(CONF_SILENT_DURATION, DEFAULT_SILENT_DURATION)),
                CONF_TAP_ACTION: user_input.get(CONF_TAP_ACTION, DEFAULT_TAP_ACTION),
                CONF_ACTION_BTN1: user_input.get(CONF_ACTION_BTN1, DEFAULT_ACTION_BTN),
                CONF_ACTION_BTN2: user_input.get(CONF_ACTION_BTN2, DEFAULT_ACTION_BTN),
                CONF_ACTION_BTN3: user_input.get(CONF_ACTION_BTN3, DEFAULT_ACTION_BTN),
            })
            return await self.async_step_configure_notifications()

        return self.async_show_form(
            step_id="configure_behavior",
            data_schema=_build_behavior_schema(self._configure_data),
        )

    # -----------------------------------------------------------------------
    # Étape 5 — Notifications (dernier écran — crée la subentry)
    # -----------------------------------------------------------------------

    async def async_step_configure_notifications(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Étape 5 — templates de notification et condition critique."""
        if user_input is not None:
            self._configure_data.update({
                CONF_NOTIF_TITLE: (user_input.get(CONF_NOTIF_TITLE) or "").strip() or None,
                CONF_NOTIF_MESSAGE: (user_input.get(CONF_NOTIF_MESSAGE) or "").strip() or None,
                CONF_CRITICAL_TEMPLATE: _resolve_critical_template(user_input),
            })

            return self.async_create_entry(
                title=f"Caméra {self._camera}",
                data={
                    CONF_CAMERA: self._camera,
                    **self._configure_data,
                },
                unique_id=f"fem_{self._camera}",
            )

        return self.async_show_form(
            step_id="configure_notifications",
            data_schema=_build_notifications_schema(self._configure_data),
        )

    # -----------------------------------------------------------------------
    # Reconfiguration (5 étapes pré-remplies)
    # -----------------------------------------------------------------------

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Reconfiguration — étape 1 (service de notification)."""
        subentry = self._get_reconfigure_subentry()
        entry = self._get_entry()
        self._camera = subentry.data[CONF_CAMERA]

        # Initialiser _configure_data depuis les données existantes
        if not self._configure_data:
            self._configure_data = dict(subentry.data)

        if user_input is not None:
            self._configure_data[CONF_NOTIFY_TARGET] = user_input[CONF_NOTIFY_TARGET]
            return await self.async_step_reconfigure_filters()

        # Récupérer les zones et labels depuis Frigate
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
            self._zones_available = []
            self._labels_available = []
            self._frigate_unreachable = True

        notify_options = _get_notify_options(self.hass)

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema({
                vol.Required(
                    CONF_NOTIFY_TARGET,
                    default=self._configure_data.get(CONF_NOTIFY_TARGET, PERSISTENT_NOTIFICATION),
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=notify_options,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
            }),
        )

    async def async_step_reconfigure_filters(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Reconfiguration — étape 2 (filtres de détection)."""
        if user_input is not None:
            self._configure_data.update(
                _parse_filters_input(user_input, self._zones_available, self._labels_available)
            )
            return await self.async_step_reconfigure_behavior()

        warning = (
            "⚠ Frigate inaccessible — saisissez les zones et labels manuellement."
            if self._frigate_unreachable
            else ""
        )

        return self.async_show_form(
            step_id="reconfigure_filters",
            data_schema=_build_filters_schema(
                self._configure_data, self._zones_available, self._labels_available
            ),
            description_placeholders={"warning": warning},
        )

    async def async_step_reconfigure_behavior(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Reconfiguration — étape 3 (comportement)."""
        if user_input is not None:
            self._configure_data.update({
                CONF_COOLDOWN: int(user_input.get(CONF_COOLDOWN, DEFAULT_THROTTLE_COOLDOWN)),
                CONF_DEBOUNCE: int(user_input.get(CONF_DEBOUNCE, DEFAULT_DEBOUNCE)),
                CONF_SILENT_DURATION: int(user_input.get(CONF_SILENT_DURATION, DEFAULT_SILENT_DURATION)),
                CONF_TAP_ACTION: user_input.get(CONF_TAP_ACTION, DEFAULT_TAP_ACTION),
                CONF_ACTION_BTN1: user_input.get(CONF_ACTION_BTN1, DEFAULT_ACTION_BTN),
                CONF_ACTION_BTN2: user_input.get(CONF_ACTION_BTN2, DEFAULT_ACTION_BTN),
                CONF_ACTION_BTN3: user_input.get(CONF_ACTION_BTN3, DEFAULT_ACTION_BTN),
            })
            return await self.async_step_reconfigure_notifications()

        return self.async_show_form(
            step_id="reconfigure_behavior",
            data_schema=_build_behavior_schema(self._configure_data),
        )

    async def async_step_reconfigure_notifications(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Reconfiguration — étape 4 (notifications) — dernière étape, sauvegarde."""
        subentry = self._get_reconfigure_subentry()
        entry = self._get_entry()

        if user_input is not None:
            self._configure_data.update({
                CONF_NOTIF_TITLE: (user_input.get(CONF_NOTIF_TITLE) or "").strip() or None,
                CONF_NOTIF_MESSAGE: (user_input.get(CONF_NOTIF_MESSAGE) or "").strip() or None,
                CONF_CRITICAL_TEMPLATE: _resolve_critical_template(user_input),
            })

            # Supprimer la clé caméra de l'accumulateur pour les data_updates
            data_updates = {k: v for k, v in self._configure_data.items() if k != CONF_CAMERA}

            return self.async_update_and_abort(
                entry,
                subentry,
                data_updates=data_updates,
            )

        return self.async_show_form(
            step_id="reconfigure_notifications",
            data_schema=_build_notifications_schema(self._configure_data),
        )
