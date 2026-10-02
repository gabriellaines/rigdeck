"""Registry of hardware modules. Add new ones (GPU controls, peripherals, …) to MODULES."""
from __future__ import annotations

from .base import Module
from .bluetooth import BluetoothModule
from .gamemon import GameMonitorModule
from .gpu import GpuModule
from .headset import HeadsetModule
from .keyboard import KeyboardModule
from .monitor import MonitorModule
from .motherboard import MotherboardModule
from .mouse import MouseModule
from .network import NetworkModule
from .webcam import WebcamModule
from .system import MemoryModule, ProcessorModule, ResourcesModule, StorageModule
from .waterforce import WaterforceModule

MODULES: list[Module] = [ResourcesModule(), GameMonitorModule(), WaterforceModule(), GpuModule(), ProcessorModule(), MemoryModule(),
                         StorageModule(), HeadsetModule(), KeyboardModule(), MouseModule(), WebcamModule(),
                         MonitorModule(), MotherboardModule(),
                         NetworkModule(), BluetoothModule()]


def by_id(module_id: str) -> Module:
    return next(m for m in MODULES if m.id == module_id)
