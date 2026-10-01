"""GUI page for the AORUS WATERFORCE X II: Cooling, Lighting and Screen tabs."""
from __future__ import annotations

import threading

from gi.repository import Adw, Gdk, Gio, GLib, Gtk

from ... import config
from ...gui.page import Page
from ...gui.util import Debounce, run_async
from ...gui.widgets import CurveEditor, StatCard, StatRow
from ...sensors import CpuSensors
from . import Screen, add_to_carousel, delete_media, effects, media, set_led
from .device import FAN_MODES, PUMP_MODES, Cooler, SpeedMode, SpeedType, preset_curve

FAN_LABELS = {SpeedMode.DEFAULT: "Default", SpeedMode.ZERO_RPM: "Zero RPM", SpeedMode.QUIET: "Quiet",
              SpeedMode.BALANCED: "Balanced", SpeedMode.PERFORMANCE: "Performance",
              SpeedMode.TURBO: "Turbo", SpeedMode.CUSTOMIZED: "Custom"}
PUMP_LABELS = {SpeedMode.BALANCED: "Balanced", SpeedMode.TURBO: "Turbo"}
SWATCHES = ["ff0000", "ff8000", "ffd000", "00ff40", "00c8ff", "0040ff", "a000ff", "ffffff"]
ROTATIONS = [0, 90, 180, 270]
PUMP_COLOR = Gdk.RGBA()
PUMP_COLOR.parse("#3584e4")


class CoolerPage(Page):
    title = "AIO Cooler"
    icon = "rigdeck-cooler-symbolic"

    def __init__(self, window):
        super().__init__(window)
        self.lock = threading.Lock()
        self.cooler: Cooler | None = None
        self.sensors = CpuSensors()
        self.loading = True
        self.custom_curve: list[tuple[int, int]] | None = None
        self.saved = (None, None, None)

        self.stack = stack = Adw.ViewStack(vexpand=True)
        stack.add_titled_with_icon(self._cooling_tab(), "cooling", "Cooling", "rigdeck-fan-symbolic")
        stack.add_titled_with_icon(self._lighting_tab(), "lighting", "Lighting", "rigdeck-light-symbolic")
        stack.add_titled_with_icon(self._screen_tab(), "screen", "Screen", "rigdeck-screen-symbolic")
        self.title_widget = Adw.ViewSwitcher(stack=stack, policy=Adw.ViewSwitcherPolicy.WIDE)

        self.fan_stat = StatCard("Fans", "rpm", "rigdeck-fan-symbolic")
        self.pump_stat = StatCard("Pump", "rpm", "rigdeck-pump-symbolic")
        self.cpu_stat = StatCard("CPU", "°C", "rigdeck-temperature-symbolic")
        stats = Adw.Clamp(maximum_size=600, margin_top=12, margin_start=12, margin_end=12,
                          child=StatRow(self.fan_stat, self.pump_stat, self.cpu_stat))
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        box.append(stats)
        box.append(stack)
        self.body = box

        self.poll_every(2, self._poll)
        self._load()

    # ---- device access (always on a worker thread, one call at a time) --------

    def _dev(self, fn, done=None, what="talk to the cooler"):
        def call():
            with self.lock:
                if self.cooler is None:
                    self.cooler = Cooler()
                try:
                    return fn(self.cooler)
                except Exception:
                    self.cooler.close()
                    self.cooler = None
                    raise

        run_async(call, done, lambda e: self.window.toast(f"Could not {what}: {e}"))

    def _poll(self):
        self.cpu_stat.set(self.sensors.temperature() or None)

        def show(rpm):
            self.fan_stat.set(rpm[0])
            self.pump_stat.set(rpm[1])
        if not self.lock.locked():  # skip a beat while an upload or apply is running
            run_async(lambda: self._locked(lambda c: c.rpm()), show,
                      lambda e: (self.fan_stat.set(None), self.pump_stat.set(None)))

    def _locked(self, fn):
        with self.lock:
            if self.cooler is None:
                self.cooler = Cooler()
            return fn(self.cooler)

    def _load(self):
        def read(c: Cooler):
            return {"modes": c.modes(), "curve": c.curve(SpeedType.FAN), "rotation": c.rotation(),
                    "fahrenheit": c.temp_unit_fahrenheit(), "screen": Screen.read(c),
                    "free": c.storage_free_kb()}
        self._dev(read, self._loaded, "read the cooler settings")

    def _loaded(self, s):
        self.loading = True
        fan, pump = s["modes"]
        self.custom_curve = s["curve"]
        self.saved = (fan, pump, list(self.custom_curve))
        self.fan_row.set_selected(FAN_MODES.index(fan) if fan in FAN_MODES else 0)
        self.pump_row.set_selected(PUMP_MODES.index(pump) if pump in PUMP_MODES else 0)
        self.rotation_row.set_selected(ROTATIONS.index(s["rotation"]) if s["rotation"] in ROTATIONS else 0)
        self.unit_row.set_selected(1 if s["fahrenheit"] else 0)
        self._show_media(s["screen"], s["free"])
        self.loading = False
        self._update_curves()
        self._set_dirty(False)

    # ---- Cooling ------------------------------------------------------------

    def _cooling_tab(self):
        page = Adw.PreferencesPage()
        modes = Adw.PreferencesGroup(title="Modes",
                                     description="The cooler follows the CPU temperature that the rigdeck "
                                                 "service sends it every 1.5 s.")
        self.fan_row = Adw.ComboRow(title="Fans", model=Gtk.StringList.new([FAN_LABELS[m] for m in FAN_MODES]))
        self.pump_row = Adw.ComboRow(title="Pump", model=Gtk.StringList.new([PUMP_LABELS[m] for m in PUMP_MODES]))
        for r in (self.fan_row, self.pump_row):
            r.connect("notify::selected", self._mode_changed)
            modes.add(r)
        page.add(modes)

        chart = Adw.PreferencesGroup(title="Curve")
        legend = Gtk.Box(spacing=12)
        for text, css in (("━ Fans", "accent"), ("┅ Pump", "pump-legend")):
            lbl = Gtk.Label(label=text)
            lbl.add_css_class("caption")
            lbl.add_css_class(css)
            legend.append(lbl)
        chart.set_header_suffix(legend)
        self.curve_hint = Gtk.Label(wrap=True, xalign=0, margin_top=6)
        self.curve_hint.add_css_class("dim-label")
        self.curve_hint.add_css_class("caption")
        self.editor = CurveEditor(on_changed=self._curve_edited)
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, margin_top=4)
        card.add_css_class("card")
        inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, margin_top=10, margin_bottom=10,
                        margin_start=10, margin_end=10)
        inner.append(self.editor)
        inner.append(self.curve_hint)
        card.append(inner)
        chart.add(card)
        page.add(chart)

        actions = Gtk.Box(spacing=12, halign=Gtk.Align.END, margin_top=6)
        self.revert_btn = Gtk.Button(label="Revert")
        self.revert_btn.connect("clicked", lambda *_: self._load())
        self.apply_btn = Gtk.Button(label="Apply")
        self.apply_btn.add_css_class("suggested-action")
        self.apply_btn.add_css_class("pill")
        self.revert_btn.add_css_class("pill")
        self.apply_btn.connect("clicked", self._apply_modes)
        actions.append(self.revert_btn)
        actions.append(self.apply_btn)
        g = Adw.PreferencesGroup()
        g.add(actions)
        page.add(g)
        return page

    def _selected_modes(self):
        return FAN_MODES[self.fan_row.get_selected()], PUMP_MODES[self.pump_row.get_selected()]

    def _set_dirty(self, dirty: bool):
        self.apply_btn.set_sensitive(dirty)
        self.revert_btn.set_sensitive(dirty)

    def _mode_changed(self, *_):
        if self.loading:
            return
        self._update_curves()
        fan, pump = self._selected_modes()
        self._set_dirty((fan, pump, self.custom_curve) != self.saved)

    def _update_curves(self):
        fan, pump = self._selected_modes()
        custom = fan == SpeedMode.CUSTOMIZED
        self.editor.set_curve("fan", self.custom_curve if custom else preset_curve(SpeedType.FAN, fan),
                              editable=custom)
        self.editor.set_curve("pump", preset_curve(SpeedType.PUMP, pump), dashed=True, color=PUMP_COLOR)
        if custom:
            hint = "Drag the points to shape your custom fan curve, then Apply."
        elif fan == SpeedMode.ZERO_RPM:
            hint = "Zero RPM: fans stop at low temperatures and spin up under load (curve set by the cooler)."
        else:
            hint = "Preset curve. Choose Custom to edit it."
        self.curve_hint.set_label(hint)

    def _curve_edited(self, name, pts):
        if name == "fan":
            self.custom_curve = pts
            self._set_dirty(True)

    def _apply_modes(self, *_):
        fan, pump = self._selected_modes()
        curve = list(self.custom_curve) if fan == SpeedMode.CUSTOMIZED else None

        def done(_):
            self.saved = (fan, pump, list(self.custom_curve))
            self._set_dirty(False)
            self.window.toast("Saved to the cooler")
        self._dev(lambda c: c.set_modes(fan, pump, curve), done, "apply the modes")

    # ---- Lighting -----------------------------------------------------------

    def _lighting_tab(self):
        effect, rgb, bright = effects.settings(config.section(config.load(), "cooler", "led"))
        self.led = {"effect": effect, "color": "%02x%02x%02x" % rgb, "brightness": bright}
        page = Adw.PreferencesPage()

        g = Adw.PreferencesGroup(title="Effect",
                                 description="Static and Rainbow wave run on the cooler itself; the others "
                                             "are animated by the rigdeck service.")
        flow = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, min_children_per_line=3,
                           max_children_per_line=7, column_spacing=8, row_spacing=8, homogeneous=True)
        first = None
        for e in effects.ALL:
            b = Gtk.ToggleButton(label=effects.LABELS[e])
            b.add_css_class("effect-chip")
            if first is None:
                first = b
            else:
                b.set_group(first)
            b.set_active(e == effect)
            b.connect("toggled", self._effect_toggled, e)
            flow.append(b)
        g.add(flow)
        page.add(g)

        cg = Adw.PreferencesGroup(title="Color")
        swatches = Gtk.Box(spacing=8, valign=Gtk.Align.CENTER)
        self.swatch_btns = {}
        for hexc in SWATCHES:
            b = Gtk.Button(tooltip_text="#" + hexc, valign=Gtk.Align.CENTER)
            b.add_css_class("swatch")
            prov = Gtk.CssProvider()
            prov.load_from_string(f"button {{ background: #{hexc}; }}")
            b.get_style_context().add_provider(prov, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
            b.connect("clicked", lambda _b, h=hexc: self._pick_color(h))
            swatches.append(b)
            self.swatch_btns[hexc] = b
        self.color_btn = Gtk.ColorDialogButton(dialog=Gtk.ColorDialog(with_alpha=False),
                                               valign=Gtk.Align.CENTER, tooltip_text="Custom color")
        self.color_btn.set_rgba(self._rgba(self.led["color"]))
        self.color_btn.connect("notify::rgba", self._color_dialog_changed)
        swatches.append(self.color_btn)
        color_row = Adw.ActionRow(title="Color")
        color_row.add_suffix(swatches)
        cg.add(color_row)

        bright_row = Adw.ActionRow(title="Brightness")
        self.bright = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 5)
        self.bright.set_hexpand(True)
        self.bright.set_size_request(220, -1)
        self.bright.set_draw_value(True)
        self.bright.set_value_pos(Gtk.PositionType.RIGHT)
        self.bright.set_value(bright)
        self.bright.connect("value-changed", lambda s: self._led_changed())
        bright_row.add_suffix(self.bright)
        cg.add(bright_row)
        page.add(cg)
        self.color_group = cg
        self._led_apply = Debounce(150, self._send_led)
        self._refresh_led_ui()
        return page

    @staticmethod
    def _rgba(hexc):
        c = Gdk.RGBA()
        c.parse("#" + hexc)
        return c

    def _effect_toggled(self, btn, effect):
        if btn.get_active():
            self.led["effect"] = effect
            self._refresh_led_ui()
            self._led_changed()

    def _pick_color(self, hexc):
        self.led["color"] = hexc
        self.color_btn.set_rgba(self._rgba(hexc))  # triggers _color_dialog_changed

    def _color_dialog_changed(self, btn, _pspec):
        c = btn.get_rgba()
        self.led["color"] = "%02x%02x%02x" % (round(c.red * 255), round(c.green * 255), round(c.blue * 255))
        self._refresh_led_ui()
        self._led_changed()

    def _refresh_led_ui(self):
        uses = self.led["effect"] in effects.USES_COLOR
        self.color_group.set_sensitive(self.led["effect"] != "off")
        for hexc, b in self.swatch_btns.items():
            b.set_sensitive(uses)
            (b.add_css_class if hexc == self.led["color"] else b.remove_css_class)("selected")
        self.color_btn.set_sensitive(uses)

    def _led_changed(self):
        self.led["brightness"] = int(self.bright.get_value())
        self._led_apply()

    def _send_led(self):
        led = dict(self.led)

        def done(msg):
            if msg != "applied":
                self.window.toast(msg)
        run_async(lambda: set_led(led["effect"], led["color"], led["brightness"]), done,
                  lambda e: self.window.toast(f"Could not set lighting: {e}"))

    # ---- Screen -------------------------------------------------------------

    def _screen_tab(self):
        page = Adw.PreferencesPage()
        g = Adw.PreferencesGroup(title="Display")
        self.rotation_row = Adw.ComboRow(title="Rotation", model=Gtk.StringList.new([f"{r}°" for r in ROTATIONS]))
        self.rotation_row.connect("notify::selected", self._rotation_changed)
        self.unit_row = Adw.ComboRow(title="Temperature unit", model=Gtk.StringList.new(["Celsius (°C)",
                                                                                         "Fahrenheit (°F)"]))
        self.unit_row.connect("notify::selected", self._unit_changed)
        g.add(self.rotation_row)
        g.add(self.unit_row)
        page.add(g)

        self.media_group = Adw.PreferencesGroup(title="Animations")
        upload = Gtk.Button(icon_name="list-add-symbolic", tooltip_text="Upload a GIF, video or image")
        upload.add_css_class("flat")
        upload.connect("clicked", self._choose_file)
        self.media_group.set_header_suffix(upload)
        self.progress = Gtk.ProgressBar(show_text=True, visible=False, margin_bottom=8)
        self.media_group.add(self.progress)

        self.show_toggle = Adw.ToggleGroup(valign=Gtk.Align.CENTER)
        self.show_toggle.add(Adw.Toggle(name="one", label="One animation"))
        self.show_toggle.add(Adw.Toggle(name="carousel", label="Carousel"))
        self.show_toggle.connect("notify::active-name", self._show_mode_changed)
        show_row = Adw.ActionRow(title="Show")
        show_row.add_suffix(self.show_toggle)
        self.media_group.add(show_row)

        self.interval_row = Adw.SpinRow.new_with_range(5, 60, 5)
        self.interval_row.set_title("Seconds per animation")
        self.interval_row.connect("notify::value", lambda *_: self._screen_changed())
        self.media_group.add(self.interval_row)

        self.screen = None           # last state read from / written to the cooler
        self.files: list[str] = []   # UI order
        self.playing: set[str] = set()
        self.media_rows: list[Gtk.Widget] = []
        self._screen_apply = Debounce(400, self._send_screen)
        page.add(self.media_group)
        return page

    def _show_media(self, screen, free_kb):
        self.screen = screen
        self.files = list(screen.files)
        self.playing = set(screen.playing)
        was, self.loading = self.loading, True
        self.show_toggle.set_active_name("one" if len(self.playing) == 1 else "carousel")
        self.interval_row.set_value(screen.interval)
        self.loading = was
        self.free_kb = free_kb
        self._rebuild_media()

    def _single(self) -> bool:
        return self.show_toggle.get_active_name() == "one"

    def _rebuild_media(self):
        for r in self.media_rows:
            self.media_group.remove(r)
        self.media_rows = []
        single = self._single()
        self.interval_row.set_visible(not single)
        first_check = None
        for pos, name in enumerate(self.files):
            row = Adw.ActionRow(title=name)
            check = Gtk.CheckButton(active=name in self.playing, valign=Gtk.Align.CENTER)
            if single:  # radio buttons
                if first_check is None:
                    first_check = check
                else:
                    check.set_group(first_check)
            check.connect("toggled", self._file_toggled, name)
            row.add_prefix(check)
            row.set_activatable_widget(check)
            if not single:
                if name in self.playing:
                    row.set_subtitle(f"#{[n for n in self.files if n in self.playing].index(name) + 1} in the rotation")
                for icon, delta, tip in (("go-up-symbolic", -1, "Play earlier"), ("go-down-symbolic", 1, "Play later")):
                    b = Gtk.Button(icon_name=icon, tooltip_text=tip, valign=Gtk.Align.CENTER,
                                   sensitive=0 <= pos + delta < len(self.files))
                    b.add_css_class("flat")
                    b.connect("clicked", lambda _b, n=name, d=delta: self._move(n, d))
                    row.add_suffix(b)
            rm = Gtk.Button(icon_name="user-trash-symbolic", tooltip_text=f"Delete {name}",
                            valign=Gtk.Align.CENTER)
            rm.add_css_class("flat")
            rm.connect("clicked", lambda _b, n=name: self._confirm_delete(n))
            row.add_suffix(rm)
            self.media_group.add(row)
            self.media_rows.append(row)
        what = "Pick the animation to show." if single else \
            "Tick the animations to rotate through; arrows set the order."
        self.media_group.set_description(f"{what} {self.free_kb / 1024:.1f} MB free on the cooler — "
                                         "any GIF, video or image is converted for the round screen.")

    def _show_mode_changed(self, *_):
        if self.loading or not self.files:
            return
        if self._single():  # keep the first switched-on animation
            first = next((n for n in self.files if n in self.playing), self.files[0])
            self.playing = {first}
        self._rebuild_media()
        self._screen_changed()

    def _file_toggled(self, check, name):
        if self.loading:
            return
        if self._single():
            if not check.get_active():
                return  # the radio that turned off; the one turning on handles it
            self.playing = {name}
        elif check.get_active():
            self.playing.add(name)
        elif len(self.playing) == 1:
            self.window.toast("At least one animation has to stay on")
            self.loading = True
            check.set_active(True)
            self.loading = False
            return
        else:
            self.playing.discard(name)
        self._rebuild_media()
        self._screen_changed()

    def _move(self, name, delta):
        i = self.files.index(name)
        j = i + delta
        self.files[i], self.files[j] = self.files[j], self.files[i]
        self._rebuild_media()
        self._screen_changed()

    def _screen_changed(self):
        if not self.loading and self.screen:
            self._screen_apply()

    def _send_screen(self):
        files = list(self.files)
        playing = [n for n in files if n in self.playing]
        interval = int(self.interval_row.get_value())
        screen = self.screen
        self._dev(lambda c: screen.write(c, files, playing, interval), None, "update the screen")

    def _confirm_delete(self, name):
        dlg = Adw.AlertDialog(heading=f"Delete {name}?",
                              body="The file is removed from the cooler's storage.")
        dlg.add_response("cancel", "Cancel")
        dlg.add_response("delete", "Delete")
        dlg.set_response_appearance("delete", Adw.ResponseAppearance.DESTRUCTIVE)

        def answered(d, res):
            if d.choose_finish(res) != "delete":
                return
            row = self.media_rows[self.files.index(name)]
            row.set_subtitle("Deleting…")
            spinner = Adw.Spinner()
            row.add_suffix(spinner)
            self._set_media_busy(True)
            before = self.screen

            def done(r):
                self._set_media_busy(False)
                self._show_media(*r)
                self.window.toast(f"Deleted {name}")

            def failed(e):
                self._set_media_busy(False)
                self.window.toast(f"Could not delete {name}: {e}")
                self._load()
            run_async(lambda: self._locked(lambda c: (delete_media(c, name, before), c.storage_free_kb())),
                      done, failed)
        dlg.choose(self.window, None, answered)

    def _set_media_busy(self, busy: bool):
        """Block the animation controls while the cooler is busy (deletes/uploads take seconds)."""
        for w in [*self.media_rows, self.interval_row, self.show_toggle, self.media_group.get_header_suffix()]:
            w.set_sensitive(not busy)

    def _rotation_changed(self, row, _p):
        if not self.loading:
            deg = ROTATIONS[row.get_selected()]
            self._dev(lambda c: (c.set_rotation(deg), c.save()), None, "rotate the screen")

    def _unit_changed(self, row, _p):
        if not self.loading:
            f = row.get_selected() == 1
            self._dev(lambda c: (c.set_temp_unit(f), c.save()), None, "change the unit")

    def _choose_file(self, *_):
        filt = Gtk.FileFilter(name="Animations, videos and images")
        for mt in ("image/gif", "image/png", "image/jpeg", "image/webp", "video/*"):
            filt.add_mime_type(mt)
        filters = Gio.ListStore.new(Gtk.FileFilter)
        filters.append(filt)
        dlg = Gtk.FileDialog(title="Upload to the cooler screen", filters=filters)
        dlg.open(self.window, None, self._file_chosen)

    def _file_chosen(self, dlg, result):
        try:
            path = dlg.open_finish(result).get_path()
        except Exception:  # cancelled
            return
        try:
            name = media.target_name(path)
        except media.MediaError as e:
            self.window.toast(str(e))
            return
        self.progress.set_visible(True)
        self.progress.set_fraction(0)
        self.progress.set_text("Converting…")
        self._set_media_busy(True)

        def show_progress(done, total):
            self.progress.set_fraction(done / total)
            self.progress.set_text(f"Uploading {name}… {100 * done // total}%")
            return GLib.SOURCE_REMOVE

        def progress(done, total):  # called on the worker thread
            GLib.idle_add(show_progress, done, total)

        def work(c: Cooler):
            data = media.convert(path)
            if len(data) > c.storage_free_kb() * 1024:
                raise media.MediaError("not enough space on the cooler")
            c.upload_media(data, name, progress)
            return add_to_carousel(c, name), c.storage_free_kb()

        def done(res):
            self._set_media_busy(False)
            self.progress.set_visible(False)
            self._show_media(*res)
            self.window.toast(f"Uploaded {name} — it's now in the rotation")

        def failed(e):
            self._set_media_busy(False)
            self.progress.set_visible(False)
            self.window.toast(f"Upload failed: {e}")
        run_async(lambda: self._locked(work), done, failed)
