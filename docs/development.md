# Development notes

## Config entry versioning

### Quand bumper la version ?

La version (`VERSION` dans `config_flow.py`) doit être incrémentée uniquement quand la **structure des données stockées** change.

| Changement | Migration nécessaire |
| --- | --- |
| Ajout d'un champ dans le config flow | ✅ Oui |
| Suppression d'un champ | ✅ Oui |
| Renommage d'un champ | ✅ Oui |
| Modification de code (logique, entités, filtres) | ❌ Non |

### Comment écrire une migration

Dans `__init__.py`, ajouter un bloc dans `async_migrate_entry` :

```python
if entry.version == N:
    new_data = {**entry.data, "new_field": DEFAULT_VALUE}
    hass.config_entries.async_update_entry(entry, data=new_data, version=N+1, minor_version=1)
    _LOGGER.info("migration vN -> vN+1 complete")
    return True
```

Ne pas oublier de bumper `VERSION = N+1` dans `FrigateEventManagerConfigFlow`.

### Éviter la migration avec `.get()`

Pour un **ajout de champ optionnel**, utiliser `entry.data.get("field", DEFAULT)` au lieu de `entry.data["field"]` rend la migration facultative — les configs existantes reçoivent la valeur par défaut à la volée sans migration.

### Historique

| Version | Changement |
| --- | --- |
| v2 → v3 | Suppression `notify_target` global (déplacé dans subentry) |
| v3 → v4 | Paramètres de tuning dans `subentry.data` |
| v4 → v5 | Ajout templates de notification (`notif_title`, `notif_message`, `critical_template`) |
| v5 → v6 | Suppression `silent_duration` (durée silence hardcodée à 30 min) |
| v6 → v7 | Ajout `media_ttl` (expiration URLs signées, défaut 3600s) |

---

## Presigned media URLs

Les URLs de médias dans les notifications sont signées avec HMAC-SHA256 par HA lui-même (pas par Frigate).

- Clé de signature : éphémère, 32 octets aléatoires, jamais persistée
- Rotation automatique toutes les 24h (`DEFAULT_MEDIA_ROTATION`) sans redémarrage
- TTL configurable dans le config flow (défaut 1h, min 5 min, max 24h)
- Format URL : `?exp=<timestamp>&kid=<slot>&sig=<hmac>`
- `kid` = identifiant du slot de clé (permet de vérifier avec la bonne clé après rotation)
- Max 2 clés en mémoire : slot courant + slot précédent (fenêtre de transition)

Script de démonstration interactif : `scripts/demo_signer.py`

---

## Déploiement local

```bash
task deploy   # SSH → copie custom_components/ + restart HA
task test     # pytest + coverage ≥80%
task lint     # ruff + markdownlint
```
