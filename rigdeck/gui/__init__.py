"""`rigdeck-gui`: the GTK4 / libadwaita app."""
from __future__ import annotations

import os
import sys

MISSING_DEPS = """rigdeck-gui needs GTK 4, libadwaita and PyGObject. Install them with:
  Arch/CachyOS/Manjaro:  sudo pacman -S python-gobject gtk4 libadwaita
  Fedora:                sudo dnf install python3-gobject gtk4 libadwaita
  Debian/Ubuntu:         sudo apt install python3-gi gir1.2-gtk-4.0 gir1.2-adw-1
The command-line tool `rigdeck` works without them."""


def main():
    try:
        import gi
        gi.require_version("Gtk", "4.0")
        gi.require_version("Adw", "1")
        from gi.repository import Adw, Gdk, Gio, Gtk
    except (ImportError, ValueError):
        sys.exit(MISSING_DEPS)

    from .. import APP_ID, __version__
    from .window import MainWindow

    class App(Adw.Application):
        def __init__(self):
            super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.DEFAULT_FLAGS)
            about = Gio.SimpleAction.new("about", None)
            about.connect("activate", self._about)
            self.add_action(about)
            quit_ = Gio.SimpleAction.new("quit", None)
            quit_.connect("activate", lambda *_: self.quit())
            self.add_action(quit_)
            self.set_accels_for_action("app.quit", ["<Control>q"])

        def do_startup(self):
            Adw.Application.do_startup(self)
            css = Gtk.CssProvider()
            css.load_from_path(os.path.join(os.path.dirname(__file__), "style.css"))
            display = Gdk.Display.get_default()
            Gtk.StyleContext.add_provider_for_display(display, css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
            Gtk.IconTheme.get_for_display(display).add_search_path(os.path.join(os.path.dirname(__file__), "icons"))

        def do_activate(self):
            win = self.get_active_window() or MainWindow(self)
            if start_page:
                win.show_page(start_page)
            win.present()

        def _about(self, *_):
            Adw.AboutDialog(application_name="rigdeck", application_icon=APP_ID, version=__version__,
                            comments="Control panel for PC hardware on Linux",
                            license_type=Gtk.License.GPL_3_0,
                            website="https://github.com/").present(self.get_active_window())

    argv = list(sys.argv)
    start_page = None
    if "--page" in argv:  # e.g. rigdeck-gui --page cooler
        i = argv.index("--page")
        start_page = argv[i + 1] if i + 1 < len(argv) else None
        del argv[i:i + 2]
    sys.exit(App().run(argv))
