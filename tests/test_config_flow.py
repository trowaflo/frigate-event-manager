"""Tests du config flow Frigate Event Manager."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.frigate_event_manager.const import (
    CONF_COOLDOWN,
    CONF_LABELS,
    CONF_MQTT_TOPIC,
    CONF_NOTIFY_TARGET,
    CONF_SEVERITY_FILTER,
    CONF_ZONES,
    DEFAULT_COOLDOWN,
    DEFAULT_MQTT_TOPIC,
    DOMAIN,
)

# Données valides pour les tests happy path
# Les champs liste sont saisis comme CSV (ce que l'UI HA envoie)
VALID_USER_INPUT = {
    CONF_MQTT_TOPIC: "frigate/reviews",
    CONF_NOTIFY_TARGET: "notify.mobile_app_iphone",
    CONF_SEVERITY_FILTER: "",
    CONF_ZONES: "",
    CONF_LABELS: "",
    "disable_times": "",
    CONF_COOLDOWN: 60,
}


async def test_config_flow_happy_path(hass: HomeAssistant) -> None:
    """Happy path : formulaire valide → entrée créée."""
    with patch(
        "custom_components.frigate_event_manager.async_setup_entry",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "user"

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=VALID_USER_INPUT,
        )

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Frigate Event Manager"
    assert result2["data"][CONF_MQTT_TOPIC] == "frigate/reviews"
    assert result2["data"][CONF_NOTIFY_TARGET] == "notify.mobile_app_iphone"
    assert result2["data"][CONF_COOLDOWN] == 60
    # Les champs CSV sont convertis en listes dans le config entry
    assert result2["data"][CONF_SEVERITY_FILTER] == []
    assert result2["data"][CONF_ZONES] == []
    assert result2["data"][CONF_LABELS] == []


async def test_config_flow_defaults(hass: HomeAssistant) -> None:
    """Les valeurs par défaut doivent correspondre aux constantes."""
    assert DEFAULT_MQTT_TOPIC == "frigate/reviews"
    assert DEFAULT_COOLDOWN == 60


async def test_config_flow_already_configured(hass: HomeAssistant) -> None:
    """Si l'intégration est déjà configurée → abort already_configured."""
    from homeassistant.helpers import entity_registry as er

    # Première configuration
    with patch(
        "custom_components.frigate_event_manager.async_setup_entry",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )
        await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=VALID_USER_INPUT,
        )

    # Deuxième tentative → abort
    result2 = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    assert result2["type"] == FlowResultType.ABORT
    assert result2["reason"] == "already_configured"


async def test_config_flow_missing_notify_target(hass: HomeAssistant) -> None:
    """notify_target est requis — voluptuous lève une exception pour champ Required manquant."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    assert result["type"] == FlowResultType.FORM

    invalid_input = {k: v for k, v in VALID_USER_INPUT.items() if k != CONF_NOTIFY_TARGET}

    # HA propage l'erreur voluptuous comme exception pour un champ Required absent
    with pytest.raises(Exception):
        await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=invalid_input,
        )


async def test_config_flow_custom_mqtt_topic(hass: HomeAssistant) -> None:
    """Un topic MQTT personnalisé doit être accepté."""
    custom_input = {**VALID_USER_INPUT, CONF_MQTT_TOPIC: "frigate/events/custom"}

    with patch(
        "custom_components.frigate_event_manager.async_setup_entry",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=custom_input,
        )

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["data"][CONF_MQTT_TOPIC] == "frigate/events/custom"


async def test_config_flow_zero_cooldown(hass: HomeAssistant) -> None:
    """Un cooldown de 0 est valide (pas de délai anti-spam)."""
    zero_cooldown_input = {**VALID_USER_INPUT, CONF_COOLDOWN: 0}

    with patch(
        "custom_components.frigate_event_manager.async_setup_entry",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=zero_cooldown_input,
        )

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["data"][CONF_COOLDOWN] == 0


async def test_const_domain() -> None:
    """DOMAIN doit être cohérent avec le nom du dossier."""
    assert DOMAIN == "frigate_event_manager"


async def test_const_all_conf_keys() -> None:
    """Toutes les clés CONF_* doivent être des chaînes non-vides."""
    from custom_components.frigate_event_manager import const

    conf_keys = [v for k, v in vars(const).items() if k.startswith("CONF_")]
    assert len(conf_keys) == 7
    for key in conf_keys:
        assert isinstance(key, str)
        assert len(key) > 0
