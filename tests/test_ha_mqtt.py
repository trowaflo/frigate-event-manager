"""Tests for HaMqttAdapter."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.core import HomeAssistant

from custom_components.frigate_event_manager.ha_mqtt import HaMqttAdapter


class TestHaMqttAdapter:
    def test_init_stocke_hass(self, hass: HomeAssistant) -> None:
        """HaMqttAdapter.__init__ stores the hass instance."""
        adapter = HaMqttAdapter(hass)
        assert adapter._hass is hass

    async def test_async_subscribe_appelle_mqtt_subscribe(
        self, hass: HomeAssistant
    ) -> None:
        """async_subscribe delegates to mqtt.async_subscribe and returns the callback."""
        mock_unsubscribe = MagicMock()
        callback = MagicMock()

        with patch(
            "custom_components.frigate_event_manager.ha_mqtt.mqtt.async_subscribe",
            new=AsyncMock(return_value=mock_unsubscribe),
        ) as mock_subscribe:
            adapter = HaMqttAdapter(hass)
            result = await adapter.async_subscribe("frigate/reviews", callback)

        mock_subscribe.assert_called_once_with(hass, "frigate/reviews", callback)
        assert result is mock_unsubscribe

    async def test_async_subscribe_retourne_callable(
        self, hass: HomeAssistant
    ) -> None:
        """async_subscribe returns a callable (the unsubscribe function)."""
        unsubscribe_fn = MagicMock()

        with patch(
            "custom_components.frigate_event_manager.ha_mqtt.mqtt.async_subscribe",
            new=AsyncMock(return_value=unsubscribe_fn),
        ):
            adapter = HaMqttAdapter(hass)
            result = await adapter.async_subscribe("test/topic", MagicMock())

        assert callable(result)
