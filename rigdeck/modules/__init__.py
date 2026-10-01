"""Registry of hardware modules. Add new ones (GPU controls, peripherals, …) to MODULES."""
from __future__ import annotations

from .base import Module
from .gpu import GpuModule
from .headset import HeadsetModule
from .system import MemoryModule, ProcessorModule, StorageModule
from .waterforce import WaterforceModule

MODULES: list[Module] = [WaterforceModule(), GpuModule(), ProcessorModule(), MemoryModule(),
                         StorageModule(), HeadsetModule()]


def by_id(module_id: str) -> Module:
    return next(m for m in MODULES if m.id == module_id)
