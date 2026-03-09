# Frigate Event Manager

Home Assistant addon qui envoie des notifications à partir des événements MQTT de Frigate.

## Fonctionnalités

- Écoute le topic MQTT `frigate/reviews` (new, update, end)
- Filtre par sévérité (detection, alert)
- Anti-spam : **cooldown** entre events différents sur la même caméra, **debounce** entre updates du même event
- Notification via l'API Home Assistant (mobile)
- Nettoyage automatique : event "end" libère les ressources, TTL en ceinture-bretelles

## Installation

1. Ajouter ce dépôt comme **addon repository** dans Home Assistant :
   - Settings → Add-ons → Add-on Store → ⋮ → Repositories
   - Coller : `https://github.com/trowaflo/frigate-event-manager`

2. Installer **Frigate Event Manager** depuis la liste des addons

3. Configurer via l'onglet **Configuration** de l'addon

## Configuration

| Option | Obligatoire | Défaut | Description |
|--------|:-----------:|--------|-------------|
| `mqtt_broker_url` | ✅ | — | URL du broker MQTT (ex: `tcp://192.168.1.50:1883`) |
| `mqtt_topic` | | `frigate/reviews` | Topic MQTT Frigate |
| `mqtt_client_id` | | `frigate-event-manager` | ID client MQTT |
| `mqtt_username` | | — | Utilisateur MQTT |
| `mqtt_password` | | — | Mot de passe MQTT |
| `notify_service` | | — | Service de notification HA (ex: `mobile_app_iphone`) |
| `severity_filter` | | `["alert", "detection"]` | Sévérités acceptées |
| `cameras` | | — | Liste de caméras à surveiller (toutes si vide) |
| `cooldown` | | `30` | Secondes entre deux events différents (même caméra) |
| `debounce` | | `5` | Secondes entre deux notifications du même event |

### Exemple

```json
{
  "mqtt_broker_url": "tcp://192.168.1.50:1883",
  "mqtt_username": "frigate",
  "mqtt_password": "secret",
  "notify_service": "mobile_app_iphone",
  "severity_filter": ["alert"],
  "cooldown": 30,
  "debounce": 5
}
