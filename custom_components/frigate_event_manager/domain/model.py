"""Modèles de domaine Frigate — aucune dépendance HA ou bibliothèque externe."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


@dataclass
class FrigateEvent:
    """Représentation d'un événement Frigate parsé depuis le payload MQTT."""

    type: str           # "new" | "update" | "end"
    camera: str
    severity: str       # "alert" | "detection"
    objects: list[str] = field(default_factory=list)
    zones: list[str] = field(default_factory=list)
    detections: list[str] = field(default_factory=list)
    score: float = 0.0
    thumb_path: str = ""
    review_id: str = ""
    start_time: float = 0.0
    end_time: float | None = None


@dataclass
class CameraState:
    """État courant d'une caméra, mis à jour à chaque événement Frigate."""

    name: str
    last_severity: str | None = None
    last_objects: list[str] = field(default_factory=list)
    last_event_time: float | None = None
    motion: bool = False    # True sur type=new, False sur type=end
    enabled: bool = True    # contrôle notifications (switch HA)

    def as_dict(self) -> dict[str, Any]:
        """Sérialise l'état en dict pour coordinator.data."""
        return {
            "name": self.name,
            "last_severity": self.last_severity,
            "last_objects": self.last_objects,
            "last_event_time": self.last_event_time,
            "motion": self.motion,
            "enabled": self.enabled,
        }


def _to_float(value: Any, *, default: float | None) -> float | None:
    """Convertit une valeur en float de manière sécurisée."""
    if value is None:
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def _parse_event(payload: str) -> FrigateEvent | None:
    """Parse un payload MQTT Frigate JSON → FrigateEvent, None si invalide."""
    try:
        raw: dict[str, Any] = json.loads(payload)
    except (json.JSONDecodeError, TypeError):
        return None

    if not isinstance(raw, dict):
        return None

    event_type = raw.get("type")
    if event_type not in ("new", "update", "end"):
        return None

    after: dict[str, Any] = raw.get("after") or raw.get("before") or {}
    camera = after.get("camera") or raw.get("camera")
    if not camera:
        return None

    # Frigate stocke objects/zones/score dans after.data pour les reviews MQTT
    data: dict[str, Any] = after.get("data") or {}

    return FrigateEvent(
        type=event_type,
        camera=str(camera),
        severity=str(after.get("severity") or raw.get("severity") or "detection"),
        objects=list(after.get("objects") or data.get("objects") or raw.get("objects") or []),
        zones=list(after.get("current_zones") or data.get("zones") or raw.get("zones") or []),
        detections=list(data.get("detections") or []),
        score=_to_float(
            after.get("score") if after.get("score") is not None
            else data.get("top_score") if data.get("top_score") is not None
            else raw.get("score"),
            default=0.0,
        ),
        thumb_path=str(after.get("thumb_path") or raw.get("thumb_path") or ""),
        review_id=str(after.get("id") or raw.get("review_id") or ""),
        start_time=_to_float(
            after.get("start_time") if after.get("start_time") is not None else raw.get("start_time"),
            default=0.0,
        ),
        end_time=_to_float(
            after.get("end_time") if after.get("end_time") is not None else raw.get("end_time"),
            default=None,
        ),
    )
