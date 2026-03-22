# Contributing

## Setup local

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install pytest pytest-cov pytest-homeassistant-custom-component ruff
```

## Lancer les tests et le lint

```bash
task test   # pytest + coverage >=80%
task lint   # ruff + markdownlint
```

Ou directement :

```bash
.venv/bin/pytest tests/ --cov=custom_components/frigate_event_manager -q
.venv/bin/ruff check custom_components/
markdownlint-cli2 '**/*.md' '!.venv/**'
```

## Format des commits

Ce projet suit les [commits conventionnels](https://www.conventionalcommits.org/) :

```text
type: titre court en minuscules
```

Types courants : `feat`, `fix`, `docs`, `refactor`, `test`, `ci`, `chore`.

Un commit par etape logique. Pas de corps de commit, pas de co-authored-by.

## Soumettre une PR

```text
1. Forker le depot et creer une branche depuis main
2. S'assurer que task test et task lint passent tous les deux
3. Ouvrir une Pull Request avec le template fourni
```
