"""Registry of hardware modules. Add new ones (GPU, …) to MODULES."""
from __future__ import annotations

from .base import Module
from .waterforce import WaterforceModule

MODULES: list[Module] = [WaterforceModule()]


def by_id(module_id: str) -> Module:
    return next(m for m in MODULES if m.id == module_id)
