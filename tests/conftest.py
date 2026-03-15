"""Fixtures partagées pour les tests de l'intégration Frigate Event Manager."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Active les intégrations custom pour tous les tests."""
    yield
