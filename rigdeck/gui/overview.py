"""Overview page: live CPU numbers, system/driver info, detected devices."""
from __future__ import annotations

from gi.repository import Adw, Gtk

from .. import sysinfo
from ..sensors import CpuSensors
from .page import Page
from .util import run_async
from .widgets import StatCard, StatRow


class OverviewPage(Page):
    title = "Overview"
    icon = "computer-symbolic"

    def __init__(self, window, modules):
        super().__init__(window)
        self.sensors = CpuSensors()
        page = Adw.PreferencesPage()
        self.body = page

        live = Adw.PreferencesGroup(title="Now")
        self.temp = StatCard("CPU temperature", "°C", "rigdeck-temperature-symbolic")
        self.load = StatCard("CPU load", "%", "rigdeck-gauge-symbolic")
        self.clock = StatCard("CPU clock", "GHz", "rigdeck-bolt-symbolic")
        live.add(StatRow(self.temp, self.load, self.clock))
        page.add(live)

        self.devices = Adw.PreferencesGroup(title="Devices")
        found = [m for m in modules if m.detect()]
        for m in found:
            row = Adw.ActionRow(title=m.title, activatable=True)
            row.add_prefix(Gtk.Image.new_from_icon_name(m.icon))
            row.add_suffix(Gtk.Image.new_from_icon_name("go-next-symbolic"))
            row.connect("activated", lambda _r, mid=m.id: window.show_page(mid))
            self.devices.add(row)
        if not found:
            self.devices.add(Adw.ActionRow(title="No supported devices detected",
                                           subtitle="Plugged in? Passed through to a VM?"))
        page.add(self.devices)

        self.system = Adw.PreferencesGroup(title="System")
        page.add(self.system)
        self.gpu_groups: list[Adw.PreferencesGroup] = []
        run_async(sysinfo.overview, self._fill_info)

        self.poll_every(2, self._refresh)

    @staticmethod
    def _row(title, value):
        row = Adw.ActionRow(title=title, subtitle=value or "unknown", subtitle_selectable=True)
        row.add_css_class("property")
        return row

    def _fill_info(self, o):
        for title, key in (("Operating system", "os"), ("Kernel", "kernel"), ("Processor", "cpu"),
                           ("Mesa", "mesa")):
            self.system.add(self._row(title, o.get(key)))
        for g in o["gpus"]:
            grp = Adw.PreferencesGroup(title=g.get("name") or f"{g['vendor']} GPU",
                                       description=f"PCI {g['pci']}")
            grp.add(self._row("Kernel driver", g.get("kernel_driver")))
            grp.add(self._row("Vulkan driver", " ".join(filter(None, (g.get("vulkan_driver"),
                                                                       g.get("driver_version"))))))
            grp.add(self._row("Vulkan API", g.get("vulkan_api")))
            grp.add(self._row("VBIOS", g.get("vbios")))
            self.body.add(grp)

    def _refresh(self):
        self.temp.set(self.sensors.temperature() or None)
        self.load.set(self.sensors.load())
        mhz = self.sensors.freq_mhz()
        self.clock.set(f"{mhz / 1000:.2f}" if mhz else None)
