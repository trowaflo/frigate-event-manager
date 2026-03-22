---
name: test
description: Lance les tests Python, verifie la couverture, et analyse les resultats.
user-invocable: true
argument-hint: "[module]"
---

# Tests

1. Si `$ARGUMENTS` contient un nom de module, lancer `.venv/bin/pytest tests/test_$ARGUMENTS.py -v`
2. Sinon lancer `.venv/bin/pytest tests/ --cov=custom_components/frigate_event_manager --cov-report=term-missing -q`
3. Si des tests echouent : lire le fichier de test concerne, identifier la cause (assertion, mock manquant, import), expliquer sans modifier les fichiers source — seuls les fichiers `tests/` peuvent etre corriges
4. Si couverture < 80% : lister les fonctions non couvertes indiquees dans le rapport `term-missing`, suggerer quels cas tester
5. Resume concis : passes/echoues + couverture globale
