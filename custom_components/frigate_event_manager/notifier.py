"""Notifier HA Companion — envoi de notifications push via les services HA.

Gère la construction du payload de notification (message, titre, image,
tag, actions, critical iOS) et délègue l'envoi à hass.services.async_call.
"""

from __future__ import annotations

import logging
from html import escape
from typing import Any

from homeassistant.core import HomeAssistant

from .coordinator import FrigateEvent

_LOGGER = logging.getLogger(__name__)


class HANotifier:
    """Envoie des notifications HA Companion pour les événements Frigate.

    Construit un payload structuré conforme à l'API HA Companion :
    - message et titre avec html.escape() sur tous les champs dynamiques
    - image : URL miniature si fournie
    - tag : identifiant par caméra pour le collapse des notifications
    - actions : boutons interactifs (ex. "Voir le clip")
    - critical iOS : bypass DND si la sévérité est "alert"
    """

    def __init__(self, hass: HomeAssistant, notify_target: str) -> None:
        """Initialise le notifier.

        Args:
            hass:           Instance HomeAssistant pour appeler les services.
            notify_target:  Nom du service notify (ex: "mobile_app_iphone").
                            Correspond au deuxième segment de notify.<target>.
        """
        self._hass = hass
        self._notify_target = notify_target

    async def async_notify(self, event: FrigateEvent, thumb_url: str = "") -> None:
        """Envoie une notification HA Companion pour un événement Frigate.

        Échappe tous les champs dynamiques via html.escape() pour éviter
        toute injection dans les clients qui rendraient du HTML.

        Args:
            event:     Événement Frigate à notifier.
            thumb_url: URL de la miniature (snapshot Frigate). Optionnelle.
        """
        # Échappement de tous les champs dynamiques issus du payload Frigate
        camera_safe = escape(event.camera)
        severity_safe = escape(event.severity)
        objects_safe = escape(", ".join(event.objects) if event.objects else "inconnu")

        titre = f"Frigate — {camera_safe}"
        message = (
            f"Caméra : {camera_safe} | "
            f"Sévérité : {severity_safe} | "
            f"Objets : {objects_safe}"
        )

        # Construction du bloc data HA Companion
        data: dict[str, Any] = {
            # Collapse des notifications par caméra (remplace la précédente)
            "tag": f"frigate_{camera_safe}",
            # Boutons d'action interactifs
            "actions": [
                {
                    "action": "URI",
                    "title": "Voir le clip",
                    "uri": f"/api/frigate/notifications/{escape(event.review_id)}/clip.mp4"
                    if event.review_id
                    else "/lovelace/cameras",
                },
            ],
        }

        # Ajout de la miniature si une URL est fournie
        if thumb_url:
            data["image"] = thumb_url

        # Bypass DND iOS (critical=1) uniquement pour les alertes
        if event.severity == "alert":
            data["push"] = {
                "sound": {
                    "name": "default",
                    "critical": 1,
                    "volume": 1.0,
                }
            }

        service_data = {
            "message": message,
            "title": titre,
            "data": data,
        }

        _LOGGER.debug(
            "Envoi notification HA Companion — cible=%s caméra=%s sévérité=%s",
            self._notify_target,
            event.camera,
            event.severity,
        )

        try:
            await self._hass.services.async_call(
                "notify",
                self._notify_target,
                service_data,
            )
        except Exception as err:  # noqa: BLE001
            _LOGGER.error(
                "Échec de la notification HA Companion (cible=%s) : %s",
                self._notify_target,
                err,
            )
