"""Entités sensor pour Frigate Event Manager — une par caméra."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import FrigateEventManagerCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Crée les sensors à partir des caméras découvertes.

    Note comportementale : les entités sont créées une seule fois au chargement
    de la plateforme, à partir de coordinator.data au moment du setup. Si aucun
    événement MQTT n'a encore été reçu (coordinator.data vide), aucune entité
    n'est créée. Les caméras découvertes ultérieurement via MQTT n'apparaissent
    pas automatiquement — un reload de l'intégration est nécessaire pour les
    enregistrer. La découverte dynamique post-démarrage est prévue en T-484.
    """
    coordinator: FrigateEventManagerCoordinator = hass.data[DOMAIN][entry.entry_id]

    sensors = []
    for cam in coordinator.data or []:
        name = cam["name"]
        sensors += [
            FrigateLastSeveritySensor(coordinator, name),
            FrigateLastObjectSensor(coordinator, name),
            FrigateEventCountSensor(coordinator, name),
        ]

    async_add_entities(sensors)


def _camera_data(coordinator: FrigateEventManagerCoordinator, name: str) -> dict:
    """Retourne les données de la caméra ou un dict vide."""
    for cam in coordinator.data or []:
        if cam["name"] == name:
            return cam
    return {}


class _FrigateBaseSensor(CoordinatorEntity[FrigateEventManagerCoordinator], SensorEntity):
    """Sensor de base — partage le coordinator et l'identité par caméra."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: FrigateEventManagerCoordinator,
        cam_name: str,
        key: str,
        name: str,
        icon: str,
    ) -> None:
        super().__init__(coordinator)
        self._cam_name = cam_name
        self._key = key
        self._attr_name = name
        self._attr_icon = icon
        self._attr_unique_id = f"fem_{cam_name}_{key}"

    def _cam(self) -> dict:
        return _camera_data(self.coordinator, self._cam_name)


class FrigateLastSeveritySensor(_FrigateBaseSensor):
    """Sévérité du dernier événement (alert / detection)."""

    def __init__(self, coordinator: FrigateEventManagerCoordinator, cam_name: str) -> None:
        super().__init__(coordinator, cam_name, "last_severity", "Dernière sévérité", "mdi:alert")

    @property
    def native_value(self) -> str | None:
        return self._cam().get("last_severity")


class FrigateLastObjectSensor(_FrigateBaseSensor):
    """Dernier objet détecté."""

    def __init__(self, coordinator: FrigateEventManagerCoordinator, cam_name: str) -> None:
        super().__init__(coordinator, cam_name, "last_object", "Dernier objet", "mdi:magnify")

    @property
    def native_value(self) -> str | None:
        objects = self._cam().get("last_objects") or []
        return objects[0] if objects else None

    @property
    def extra_state_attributes(self) -> dict:
        return {"all_objects": self._cam().get("last_objects", [])}


class FrigateEventCountSensor(_FrigateBaseSensor):
    """Nombre d'événements sur les 24 dernières heures."""

    def __init__(self, coordinator: FrigateEventManagerCoordinator, cam_name: str) -> None:
        super().__init__(coordinator, cam_name, "event_count_24h", "Événements 24h", "mdi:counter")
        self._attr_native_unit_of_measurement = "événements"

    @property
    def native_value(self) -> int | None:
        return self._cam().get("event_count_24h")
