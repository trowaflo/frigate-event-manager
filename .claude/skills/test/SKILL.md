---
name: test
description: Lance les tests Python, verifie la couverture, et analyse les resultats.
user-invocable: true
argument-hint: "[module]"
---

# Tests

1. Si `$ARGUMENTS` contient un nom de module, lancer `.venv/bin/pytest tests/test_$ARGUMENTS.py -v`
2. Sinon lancer `.venv/bin/pytest tests/ --cov=custom_components/frigate_event_manager --cov-report=term-missing -q`
3. Si tests echouent : lire le fichier concerne, analyser, proposer un fix
4. Si couverture < 80% : identifier les fonctions non couvertes listees dans le rapport `term-missing`
5. Resume concis : passes/echoues + couverture globale
