"""Main window: sidebar of devices on the left, the selected page on the right."""
from __future__ import annotations

from gi.repository import Adw, Gtk

from .. import servicectl
from ..modules import MODULES
from .overview import OverviewPage
from .util import run_async


class MainWindow(Adw.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title="rigdeck", default_width=1000, default_height=720)
        self.set_size_request(360, 480)
        self.pages: dict[str, object] = {}
        self.current = None

        self.toasts = Adw.ToastOverlay()
        self.set_content(self.toasts)
        self.split = Adw.NavigationSplitView(min_sidebar_width=200, max_sidebar_width=260)
        self.toasts.set_child(self.split)

        # sidebar
        self.list = Gtk.ListBox(selection_mode=Gtk.SelectionMode.SINGLE)
        self.list.add_css_class("navigation-sidebar")
        self.list.connect("row-selected", self._on_row)
        side = Adw.ToolbarView()
        side_header = Adw.HeaderBar()
        menu = Gtk.MenuButton(icon_name="open-menu-symbolic", tooltip_text="Menu",
                              menu_model=self._menu())
        side_header.pack_end(menu)
        side.add_top_bar(side_header)
        side.set_content(Gtk.ScrolledWindow(child=self.list, vexpand=True))
        self.split.set_sidebar(Adw.NavigationPage(title="rigdeck", child=side))

        # content: header + service banner + page body
        self.content_view = Adw.ToolbarView()
        self.header = Adw.HeaderBar()
        self.content_view.add_top_bar(self.header)
        self.banner = Adw.Banner(title="The rigdeck background service is not running — the cooler "
                                       "isn't getting CPU temperature and software LED effects are off.",
                                 button_label="Start service")
        self.banner.connect("button-clicked", self._start_service)
        self.content_view.add_top_bar(self.banner)
        self.content_page = Adw.NavigationPage(title="Overview", child=self.content_view)
        self.split.set_content(self.content_page)

        bp = Adw.Breakpoint.new(Adw.BreakpointCondition.parse("max-width: 640sp"))
        bp.add_setter(self.split, "collapsed", True)
        self.add_breakpoint(bp)

        self._add_page("overview", OverviewPage(self, MODULES))
        for m in MODULES:
            if m.detect():
                self._add_page(m.id, m.gui_page(self))
        self.list.select_row(self.list.get_row_at_index(0))
        self.refresh_service_state()

    def _menu(self):
        from gi.repository import Gio
        m = Gio.Menu()
        m.append("About rigdeck", "app.about")
        return m

    def _add_page(self, pid, page):
        if page is None:
            return
        self.pages[pid] = page
        box = Gtk.Box(spacing=10, margin_top=8, margin_bottom=8, margin_start=4)
        box.append(Gtk.Image.new_from_icon_name(page.icon))
        box.append(Gtk.Label(label=page.title, xalign=0))
        row = Gtk.ListBoxRow(child=box)
        row.page_id = pid
        self.list.append(row)

    def _on_row(self, _list, row):
        if row is None:
            return
        page = self.pages[row.page_id]
        if self.current is page:
            return
        if self.current:
            self.current.hidden()
        self.current = page
        self.content_view.set_content(page.body)
        self.header.set_title_widget(page.title_widget)
        self.content_page.set_title(page.title)
        self.split.set_show_content(True)
        page.shown()

    def show_page(self, pid):
        i = 0
        while (row := self.list.get_row_at_index(i)) is not None:
            if row.page_id == pid:
                self.list.select_row(row)
                return
            i += 1

    def toast(self, text: str):
        self.toasts.add_toast(Adw.Toast(title=text, timeout=3))

    def refresh_service_state(self):
        run_async(servicectl.is_active, lambda ok: self.banner.set_revealed(not ok))

    def _start_service(self, _banner):
        def done(ok):
            self.toast("Service started" if ok else "Could not start the service — is rigdeck installed?")
            self.refresh_service_state()
        run_async(servicectl.enable_now, done)
