---
name: deploy
description: Deployer l'integration vers Home Assistant OS via SSH (tar pipe).
user-invocable: true
disable-model-invocation: true
---

# Deploy

Deploie `custom_components/frigate_event_manager/` vers HA OS via SSH et redémarre le core.

## Prerequis

- Variable d'environnement `HA_HOST` définie (ex: `homeassistant.local` ou IP)
- Acces SSH root configuré (`ssh root@$HA_HOST` fonctionne sans mot de passe)

## Commande

```bash
tar -czf - -C ./custom_components frigate_event_manager \
  | ssh root@"$HA_HOST" \
    "rm -rf /config/custom_components/frigate_event_manager && tar -xzf - -C /config/custom_components/"

ssh root@"$HA_HOST" "ha core restart"
```

## Etapes

1. Verifier que `HA_HOST` est défini, sinon demander à l'utilisateur
2. Executer le tar pipe pour copier le composant
3. Lancer `ha core restart` via SSH
4. Indiquer à l'utilisateur de surveiller les logs HA (`ha core logs --follow`)

## Regles

- NEVER: rsync (non installé sur HA OS)
- NEVER: ha supervisor restart (inutilement destructif)
- ALWAYS: tar pipe depuis le Mac directement
