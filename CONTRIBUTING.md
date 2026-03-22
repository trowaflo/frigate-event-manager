# Contributing

## Local setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install pytest pytest-cov pytest-homeassistant-custom-component ruff
```

When you are done:

```bash
deactivate
```

## Run tests and lint

```bash
task test   # pytest + coverage >=80%
task lint   # ruff + markdownlint
```

Or directly:

```bash
.venv/bin/pytest tests/ --cov=custom_components/frigate_event_manager -q
.venv/bin/ruff check .
markdownlint-cli2 '**/*.md' '!.venv/**'
```

## Commit format

This project follows [Conventional Commits](https://www.conventionalcommits.org/):

```text
type: short lowercase title
```

Common types: `feat`, `fix`, `docs`, `refactor`, `test`, `ci`, `chore`.

One commit per logical step. No commit body, no co-authored-by.

## Submitting a PR

```text
1. Fork the repository and create a branch from main
2. Make sure task test and task lint both pass
3. Open a Pull Request using the provided template
```

Review comments follow [Conventional Comments](https://conventionalcomments.org/).
