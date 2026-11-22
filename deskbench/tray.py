"""The tray: a StatusNotifierItem that exists exactly while a desktop exists."""

from __future__ import annotations

import signal
import subprocess
import sys
import threading
import time

from . import engine, lock

APP_ID = "agent-deskbench"
ICON_FALLBACKS = ("video-display", "computer", "utilities-terminal")


def _open(url: str) -> None:
    subprocess.Popen(
        ["xdg-open", url],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


def main() -> int:
    handle = lock.acquire()
    if handle is None:
        return 0  # another tray is alive; nothing to do

    try:
        import gi

        gi.require_version("Gtk", "3.0")
        gi.require_version("Gdk", "3.0")
        gi.require_version("AyatanaAppIndicator3", "0.1")
        from gi.repository import AyatanaAppIndicator3 as AppIndicator
        from gi.repository import Gdk, GLib, Gtk
    except (ImportError, ValueError) as exc:
        print(
            f"deskbench: the tray needs python3-gi with GTK 3 and AyatanaAppIndicator3 ({exc})",
            file=sys.stderr,
        )
        return 1

    menu = Gtk.Menu()
    theme = Gtk.IconTheme.get_default()
    icon = next((name for name in ICON_FALLBACKS if theme.has_icon(name)), "computer")
    indicator = AppIndicator.Indicator.new(
        APP_ID, icon, AppIndicator.IndicatorCategory.APPLICATION_STATUS
    )
    indicator.set_status(AppIndicator.IndicatorStatus.ACTIVE)
    indicator.set_menu(menu)

    def copy(url: str) -> None:
        clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        clipboard.set_text(url, -1)
        clipboard.store()  # survive the tray exiting

    def stop(name: str) -> None:
        # Stopping takes a second or two; never block the menu on it.
        def worker() -> None:
            try:
                engine.stop(name)
            except engine.EngineError as exc:
                print(f"deskbench: {exc}", file=sys.stderr)
            GLib.idle_add(refresh)

        threading.Thread(target=worker, daemon=True).start()

    def rebuild(desktops: list[engine.Desktop]) -> None:
        for child in menu.get_children():
            menu.remove(child)
        for desktop in desktops:
            top = Gtk.MenuItem(label=f"{desktop.name}  ·  {desktop.state}")
            submenu = Gtk.Menu()

            open_item = Gtk.MenuItem(label="Open viewer")
            open_item.connect("activate", lambda *_, url=desktop.url: _open(url))
            submenu.append(open_item)

            copy_item = Gtk.MenuItem(label="Copy URL")
            copy_item.connect("activate", lambda *_, url=desktop.url: copy(url))
            submenu.append(copy_item)

            stop_item = Gtk.MenuItem(label="Stop")
            stop_item.connect("activate", lambda *_, name=desktop.name: stop(name))
            submenu.append(stop_item)

            top.set_submenu(submenu)
            menu.append(top)

        menu.append(Gtk.SeparatorMenuItem())
        quit_item = Gtk.MenuItem(label="Quit")
        quit_item.connect("activate", lambda *_: Gtk.main_quit())
        menu.append(quit_item)
        menu.show_all()

    def refresh() -> bool:
        try:
            desktops = engine.list_desktops()
        except engine.EngineError as exc:
            # A transient failure must not hide desktops that are still running.
            print(f"deskbench: {exc}", file=sys.stderr)
            return False
        if not desktops:
            Gtk.main_quit()
            return False
        rebuild(desktops)
        indicator.set_status(
            AppIndicator.IndicatorStatus.NEEDS_ATTENTION
            if lock.attention_live()
            else AppIndicator.IndicatorStatus.ACTIVE
        )
        return False

    def tick() -> bool:
        refresh()
        return True

    def watch_events(stop_event: threading.Event) -> None:
        """Re-read the desktop list whenever Podman reports a container change."""
        while not stop_event.is_set():
            try:
                proc = subprocess.Popen(
                    ["podman", "events", "--filter", "type=container",
                     "--filter", "label=deskbench=1", "--format", "json"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                    text=True,
                )
            except OSError:
                return
            try:
                assert proc.stdout is not None
                for _line in proc.stdout:
                    if stop_event.is_set():
                        break
                    GLib.idle_add(refresh)
            finally:
                proc.terminate()
                proc.wait(timeout=5)
            if stop_event.is_set():
                return
            time.sleep(2)  # the event stream can end; keep it alive

    stop_event = threading.Event()
    threading.Thread(target=watch_events, args=(stop_event,), daemon=True).start()
    GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGUSR1, lambda: refresh() or True)
    GLib.timeout_add_seconds(2, tick)

    try:
        while True:
            refresh()
            Gtk.main()
            handle.close()
            # A desktop may have appeared while the tray was shutting down: its `new`
            # would have seen our lock still held and skipped spawning.
            try:
                remaining = engine.list_desktops()
            except engine.EngineError:
                remaining = []
            if not remaining:
                break
            handle = lock.acquire()
            if handle is None:
                break
    finally:
        stop_event.set()
        try:
            handle.close()
        except OSError:
            pass
    return 0
