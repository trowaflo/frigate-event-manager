"""Re-export — le module canonique est domain/filter.py."""

from .domain.filter import (  # noqa: F401
    Filter,
    FilterChain,
    LabelFilter,
    TimeFilter,
    ZoneFilter,
    _est_sous_sequence,
)
