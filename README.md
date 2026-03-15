# Frigate Event Manager

Intégration Home Assistant (HACS) qui écoute les événements Frigate via MQTT et crée des entités HA par caméra : sensors, switch de notifications et binary_sensor de mouvement.

## Prérequis

- Home Assistant avec l'[intégration MQTT native](https://www.home-assistant.io/integrations/mqtt/) activée et configurée
- [Frigate NVR](https://frigate.video/) publiant ses événements sur le broker MQTT
- [HACS](https://hacs.xyz/) installé dans Home Assistant

## Installation via HACS

1. Dans Home Assistant, aller dans **HACS → Integrations → ⋮ → Custom repositories**
2. Ajouter l'URL : `https://github.com/trowaflo/frigate-event-manager`
   - Catégorie : **Integration**
3. Rechercher **Frigate Event Manager** dans HACS et cliquer sur **Download**
4. Redémarrer Home Assistant
5. Aller dans **Settings → Devices & Services → Add Integration**
6. Rechercher **Frigate Event Manager** et suivre le formulaire de configuration

## Configuration

Le formulaire de configuration demande les champs suivants.

| Champ | Obligatoire | Défaut | Description |
| --- | :-: | --- | --- |
| `mqtt_topic` | ✅ | `frigate/reviews` | Topic MQTT publié par Frigate |
| `notify_target` | ✅ | — | Service de notification HA (ex : `mobile_app_iphone`) |
| `severity_filter` | | _(tout accepter)_ | Liste de sévérités acceptées : `alert`, `detection` |
| `zones` | | _(tout accepter)_ | Zones Frigate requises (ex : `jardin`, `entree`) |
| `labels` | | _(tout accepter)_ | Labels d'objets requis (ex : `person`, `car`) |
| `disable_times` | | _(jamais désactivé)_ | Heures (0–23) où les notifications sont silencieuses |
| `cooldown` | | `60` | Secondes minimum entre deux notifications pour une même caméra |

**Règle liste vide** : une liste vide signifie "tout accepter" — aucun filtrage appliqué sur ce critère.

**`disable_times`** : exprimées en heure locale du serveur Home Assistant. Si HA tourne en UTC, configurer en UTC.

## Entités créées par caméra

Les entités sont créées automatiquement à la première réception d'un événement MQTT pour chaque caméra. Un **reload de l'intégration** est nécessaire si une caméra est découverte après le démarrage initial.

### Sensors

| Entité | `unique_id` | Description |
| --- | --- | --- |
| `sensor.fem_{cam}_last_severity` | `fem_{cam}_last_severity` | Sévérité du dernier événement : `alert` ou `detection` |
| `sensor.fem_{cam}_last_object` | `fem_{cam}_last_object` | Premier objet détecté (attribut `all_objects` : liste complète) |
| `sensor.fem_{cam}_event_count_24h` | `fem_{cam}_event_count_24h` | Nombre d'événements de type `new` reçus depuis le démarrage |

### Switch

| Entité | `unique_id` | Description |
| --- | --- | --- |
| `switch.fem_{cam}_notifications` | `fem_{cam}_notifications` | Active / désactive les notifications push pour cette caméra |

### Binary Sensor

| Entité | `unique_id` | `device_class` | Description |
| --- | --- | --- | --- |
| `binary_sensor.fem_{cam}_motion` | `fem_{cam}_motion` | `motion` | ON quand un événement `new` est actif, OFF sur `end` |

`{cam}` est le nom de la caméra tel que déclaré dans Frigate (champ `camera` du payload MQTT).

## Fonctionnement

```text
MQTT (frigate/reviews)
    → Coordinator (parse payload Frigate)
        → FilterChain (ZoneFilter + LabelFilter + TimeFilter)
            → Throttler (cooldown anti-spam par caméra)
                → HANotifier (notify.<target> via services HA)
        → Entités HA mises à jour (sensor, switch, binary_sensor)
```

- **Coordinator** : mode push MQTT uniquement, aucun polling. La reconnexion est gérée nativement par l'intégration MQTT de HA.
- **FilterChain** : un seul refus suffit pour bloquer l'événement.
- **Throttler** : cooldown configurable, indépendant par caméra.
- **HANotifier** : notification HA Companion avec collapse par caméra (tag), action "Voir le clip", et bypass DND iOS pour les alertes.

## Structure du custom component

```text
custom_components/frigate_event_manager/
    __init__.py         — setup / unload de la config entry
    const.py            — constantes DOMAIN, CONF_*, DEFAULTS
    config_flow.py      — formulaire de configuration HACS
    coordinator.py      — DataUpdateCoordinator MQTT (FrigateEvent, CameraState)
    filter.py           — ZoneFilter, LabelFilter, TimeFilter, FilterChain
    registry.py         — CameraRegistry (persistence JSON atomique)
    event_store.py      — ring buffer d'événements (deque maxlen=200)
    throttle.py         — Throttler anti-spam par caméra
    notifier.py         — HANotifier (notifications HA Companion)
    sensor.py           — 3 sensors par caméra
    switch.py           — switch notifications par caméra
    binary_sensor.py    — binary_sensor mouvement par caméra
```
