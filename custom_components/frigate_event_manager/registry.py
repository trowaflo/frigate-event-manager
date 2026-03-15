"""Registre en mémoire des caméras Frigate.

Maintient un dict ``camera_name → CameraState`` avec persistence JSON
dans ``hass.config.path("frigate_em_state.json")``.
Toute nouvelle caméra est créée avec ``enabled=True`` (auto-découverte).
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from homeassistant.core import HomeAssistant

from .coordinator import CameraState, FrigateEvent

_LOGGER = logging.getLogger(__name__)

# Nom du fichier de persistence dans le répertoire de configuration HA
_STATE_FILENAME = "frigate_em_state.json"


class CameraRegistry:
    """Registre en mémoire des états de caméras Frigate.

    Responsabilités :
    - Maintenir un ``dict[str, CameraState]`` mis à jour à chaque événement MQTT.
    - Persister l'état (enabled, compteurs) entre les redémarrages HA.
    - Auto-découvrir les nouvelles caméras (``enabled=True`` par défaut).
    """

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialise le registre.

        Args:
            hass: Instance HomeAssistant, utilisée pour résoudre le chemin
                  de persistence et déléguer les I/O bloquants.
        """
        self._hass = hass
        self._cameras: dict[str, CameraState] = {}
        self._state_path: str = hass.config.path(_STATE_FILENAME)

    # ------------------------------------------------------------------
    # API publique
    # ------------------------------------------------------------------

    def get(self, camera_name: str) -> CameraState:
        """Retourne l'état de la caméra, la crée si inconnue.

        Une caméra inconnue est créée avec ``enabled=True``
        (comportement plug & play).
        """
        if camera_name not in self._cameras:
            _LOGGER.info("Nouvelle caméra auto-découverte : %s", camera_name)
            self._cameras[camera_name] = CameraState(name=camera_name)
        return self._cameras[camera_name]

    def update(self, event: FrigateEvent) -> None:
        """Met à jour l'état de la caméra concernée à partir d'un FrigateEvent.

        Règles :
        - ``new``    → motion=True, event_count_24h+1, met à jour sévérité/objets/last_event_time
        - ``update`` → met à jour sévérité/objets/last_event_time (pas de compteur)
        - ``end``    → motion=False, last_event_time = end_time ou start_time
        """
        state = self.get(event.camera)

        if event.type in ("new", "update"):
            state.last_severity = event.severity
            state.last_objects = event.objects
            state.last_event_time = event.start_time
            if event.type == "new":
                state.motion = True
                state.event_count_24h += 1
        elif event.type == "end":
            state.motion = False
            state.last_event_time = event.end_time or event.start_time

        _LOGGER.debug(
            "Registre mis à jour — caméra=%s type=%s motion=%s count=%d",
            event.camera,
            event.type,
            state.motion,
            state.event_count_24h,
        )

    def set_enabled(self, camera_name: str, enabled: bool) -> None:
        """Active ou désactive les notifications pour une caméra.

        Si la caméra est inconnue, elle est créée via ``get()``
        (auto-découverte).
        """
        state = self.get(camera_name)
        state.enabled = enabled
        _LOGGER.debug(
            "Caméra %s : notifications %s",
            camera_name,
            "activées" if enabled else "désactivées",
        )

    def all_cameras(self) -> list[CameraState]:
        """Retourne la liste de tous les CameraState connus."""
        return list(self._cameras.values())

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    async def async_save(self) -> None:
        """Sauvegarde l'état en JSON de manière atomique (tmp + rename).

        Utilise ``hass.async_add_executor_job`` pour ne pas bloquer la
        boucle asyncio lors des I/O disque.
        """
        data = self._serialize()
        await self._hass.async_add_executor_job(self._write_atomic, data)

    async def async_load(self) -> None:
        """Charge l'état depuis le fichier JSON de persistence.

        Si le fichier est absent ou corrompu, le registre démarre vide
        (les caméras seront recréées à la première réception MQTT).
        """
        await self._hass.async_add_executor_job(self._read_state)

    # ------------------------------------------------------------------
    # Méthodes privées
    # ------------------------------------------------------------------

    def _serialize(self) -> dict[str, Any]:
        """Sérialise le registre en dict JSON-compatible."""
        return {
            name: state.as_dict()
            for name, state in self._cameras.items()
        }

    def _write_atomic(self, data: dict[str, Any]) -> None:
        """Écrit ``data`` dans le fichier de persistence de manière atomique.

        Stratégie : écrire dans ``.tmp``, puis ``os.replace`` (atomique
        sur POSIX et Windows NT).
        """
        tmp_path = self._state_path + ".tmp"
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, self._state_path)
            _LOGGER.debug("État du registre sauvegardé : %s", self._state_path)
        except OSError as err:
            _LOGGER.error(
                "Impossible de sauvegarder l'état du registre (%s) : %s",
                self._state_path,
                err,
            )

    def _read_state(self) -> None:
        """Lit le fichier JSON et reconstitue le dict ``_cameras``.

        Les champs inconnus dans le JSON sont ignorés silencieusement pour
        assurer la compatibilité ascendante avec d'anciens fichiers d'état.
        """
        if not os.path.isfile(self._state_path):
            _LOGGER.debug(
                "Aucun fichier d'état trouvé (%s) — démarrage à vide",
                self._state_path,
            )
            return

        try:
            with open(self._state_path, encoding="utf-8") as f:
                raw: dict[str, Any] = json.load(f)
        except (OSError, json.JSONDecodeError) as err:
            _LOGGER.error(
                "Fichier d'état corrompu (%s), ignoré : %s",
                self._state_path,
                err,
            )
            return

        if not isinstance(raw, dict):
            _LOGGER.error(
                "Format de fichier d'état invalide (%s) : dict attendu",
                self._state_path,
            )
            return

        for name, cam_data in raw.items():
            if not isinstance(cam_data, dict):
                _LOGGER.warning(
                    "Entrée ignorée pour la caméra %r : dict attendu, reçu %s",
                    name,
                    type(cam_data).__name__,
                )
                continue

            self._cameras[name] = CameraState(
                name=str(cam_data.get("name", name)),
                last_severity=cam_data.get("last_severity"),
                last_objects=list(cam_data.get("last_objects") or []),
                event_count_24h=int(cam_data.get("event_count_24h") or 0),
                last_event_time=cam_data.get("last_event_time"),
                motion=bool(cam_data.get("motion", False)),
                enabled=bool(cam_data.get("enabled", True)),
            )

        _LOGGER.info(
            "Registre chargé depuis %s — %d caméra(s)",
            self._state_path,
            len(self._cameras),
        )
