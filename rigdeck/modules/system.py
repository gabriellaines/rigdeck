"""Built-in system pages (read-only telemetry). They use the shared `system` QML backend."""
from __future__ import annotations

import os

from .base import Module

PAGES = os.path.join(os.path.dirname(os.path.dirname(__file__)), "gui", "qml", "pages")


class _SystemPage(Module):
    kind = "system"
    page_file = ""

    def detect(self) -> bool:
        return True

    def qml_page(self):
        return os.path.join(PAGES, self.page_file)


class ResourcesModule(_SystemPage):
    id, title, icon, order, page_file = "resources", "Resources", "activity", 5, "ResourcesPage.qml"


class ProcessorModule(_SystemPage):
    id, title, icon, order, page_file = "cpu", "Processor", "cpu", 30, "ProcessorPage.qml"


class MemoryModule(_SystemPage):
    id, title, icon, order, page_file = "memory", "Memory", "memory-stick", 40, "MemoryPage.qml"


class StorageModule(_SystemPage):
    id, title, icon, order, page_file = "storage", "Storage", "hard-drive", 50, "StoragePage.qml"
