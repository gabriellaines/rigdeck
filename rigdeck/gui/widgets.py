"""Reusable widgets: stat cards and the fan-curve editor."""
from __future__ import annotations

import math

from gi.repository import Adw, Gtk


class StatCard(Gtk.Box):
    """A big live number with a caption, e.g. '1240 rpm / Fans'."""

    def __init__(self, caption: str, unit: str = "", icon: str | None = None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        self.add_css_class("card")
        self.add_css_class("stat-card")
        top = Gtk.Box(spacing=6)
        if icon:
            top.append(Gtk.Image.new_from_icon_name(icon))
        cap = Gtk.Label(label=caption, xalign=0)
        cap.add_css_class("caption-heading")
        cap.add_css_class("dim-label")
        top.append(cap)
        self.append(top)
        row = Gtk.Box(spacing=4)
        self.value = Gtk.Label(label="—", xalign=0)
        self.value.add_css_class("stat-value")
        self.value.add_css_class("numeric")
        row.append(self.value)
        self.unit = Gtk.Label(label=unit, xalign=0, valign=Gtk.Align.BASELINE_FILL)
        self.unit.add_css_class("dim-label")
        row.append(self.unit)
        self.append(row)
        self.set_hexpand(True)

    def set(self, value):
        self.value.set_label("—" if value is None else str(value))


class StatRow(Gtk.Box):
    """Horizontal row of StatCards that wraps on narrow windows."""

    def __init__(self, *cards: StatCard):
        super().__init__()
        self.flow = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, homogeneous=True,
                                min_children_per_line=2, max_children_per_line=4,
                                column_spacing=12, row_spacing=12, hexpand=True)
        for c in cards:
            self.flow.append(c)
        self.append(self.flow)


class CurveEditor(Gtk.DrawingArea):
    """Temperature→RPM chart with draggable points.

    `curves` maps a name to (points, editable, css_role); points are [(temp °C, rpm)].
    """

    T_MAX, RPM_MAX = 100, 3200
    PAD_L, PAD_R, PAD_T, PAD_B = 48, 16, 14, 30
    HIT = 14

    def __init__(self, on_changed=None):
        super().__init__(content_height=240, hexpand=True)
        self.add_css_class("curve-editor")
        self.curves: dict[str, dict] = {}
        self.on_changed = on_changed
        self.drag: tuple[str, int] | None = None
        self.set_draw_func(self._draw)
        g = Gtk.GestureDrag()
        g.connect("drag-begin", self._begin)
        g.connect("drag-update", self._update)
        g.connect("drag-end", lambda *_: setattr(self, "drag", None))
        self.add_controller(g)
        self._start = (0.0, 0.0)

    def set_curve(self, name: str, points, editable=False, dashed=False, color=None):
        self.curves[name] = {"points": [tuple(p) for p in points] if points else None,
                             "editable": editable, "dashed": dashed, "color": color}
        self.queue_draw()

    def points(self, name: str):
        c = self.curves.get(name)
        return list(c["points"]) if c and c["points"] else None

    # ---- geometry
    def _xy(self, t, rpm):
        w, h = self.get_width(), self.get_height()
        x = self.PAD_L + (w - self.PAD_L - self.PAD_R) * t / self.T_MAX
        y = self.PAD_T + (h - self.PAD_T - self.PAD_B) * (1 - rpm / self.RPM_MAX)
        return x, y

    def _data(self, x, y):
        w, h = self.get_width(), self.get_height()
        t = (x - self.PAD_L) / (w - self.PAD_L - self.PAD_R) * self.T_MAX
        rpm = (1 - (y - self.PAD_T) / (h - self.PAD_T - self.PAD_B)) * self.RPM_MAX
        return t, rpm

    # ---- drawing
    def _draw(self, area, cr, w, h):
        fg = self.get_color()
        accent = Adw.StyleManager.get_default().get_accent_color_rgba()
        cr.set_line_width(1)
        cr.select_font_face("sans")
        cr.set_font_size(10)
        for t in range(0, 101, 10):
            x, _ = self._xy(t, 0)
            cr.set_source_rgba(fg.red, fg.green, fg.blue, 0.08)
            cr.move_to(x, self.PAD_T)
            cr.line_to(x, h - self.PAD_B)
            cr.stroke()
            if t % 20 == 0:
                cr.set_source_rgba(fg.red, fg.green, fg.blue, 0.55)
                label = f"{t}°"
                cr.move_to(x - cr.text_extents(label).width / 2, h - self.PAD_B + 16)
                cr.show_text(label)
        for rpm in range(0, self.RPM_MAX + 1, 800):
            _, y = self._xy(0, rpm)
            cr.set_source_rgba(fg.red, fg.green, fg.blue, 0.08)
            cr.move_to(self.PAD_L, y)
            cr.line_to(w - self.PAD_R, y)
            cr.stroke()
            cr.set_source_rgba(fg.red, fg.green, fg.blue, 0.55)
            label = str(rpm)
            cr.move_to(self.PAD_L - 8 - cr.text_extents(label).width, y + 3)
            cr.show_text(label)
        for c in self.curves.values():
            pts = c["points"]
            if not pts:
                continue
            col = c["color"] or accent
            cr.set_source_rgba(col.red, col.green, col.blue, 1)
            cr.set_line_width(2.5)
            cr.set_dash([6, 4] if c["dashed"] else [])
            first = self._xy(*pts[0])
            cr.move_to(self.PAD_L, first[1])
            for p in pts:
                cr.line_to(*self._xy(*p))
            cr.line_to(w - self.PAD_R, self._xy(*pts[-1])[1])
            cr.stroke()
            cr.set_dash([])
            if c["editable"]:
                for p in pts:
                    x, y = self._xy(*p)
                    cr.arc(x, y, 6, 0, 2 * math.pi)
                    cr.set_source_rgba(col.red, col.green, col.blue, 1)
                    cr.fill_preserve()
                    cr.set_source_rgba(1, 1, 1, 0.9)
                    cr.set_line_width(2)
                    cr.stroke()

    # ---- dragging
    def _begin(self, g, x, y):
        best = None
        for name, c in self.curves.items():
            if not c["editable"] or not c["points"]:
                continue
            for i, p in enumerate(c["points"]):
                px, py = self._xy(*p)
                d = math.hypot(px - x, py - y)
                if d <= self.HIT and (best is None or d < best[0]):
                    best = (d, name, i)
        self.drag = (best[1], best[2]) if best else None
        self._start = (x, y)

    def _update(self, g, dx, dy):
        if not self.drag:
            return
        name, i = self.drag
        pts = self.curves[name]["points"]
        t, rpm = self._data(self._start[0] + dx, self._start[1] + dy)
        lo = pts[i - 1][0] + 1 if i > 0 else 0
        hi = pts[i + 1][0] - 1 if i < len(pts) - 1 else self.T_MAX
        t = int(round(min(max(t, lo), hi)))
        rpm = int(round(min(max(rpm, 0), self.RPM_MAX) / 10) * 10)
        pts[i] = (t, rpm)
        self.queue_draw()
        if self.on_changed:
            self.on_changed(name, list(pts))
