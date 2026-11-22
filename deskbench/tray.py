"""The tray: a StatusNotifierItem that exists exactly while a desktop exists."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import threading
import time

from . import engine, lock

APP_ID = "agent-deskbench"
ICON_FALLBACKS = ("video-display", "computer", "utilities-terminal")


def _open(url: str) -> None:
    subprocess.Popen(["xdg-open", url], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL, start_new_session=True)


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
    indicator = AppIndicator.Indicator.new(APP_ID, icon, AppIndicator.IndicatorCategory.APPLICATION_STATUS)
    indicator.set_status(AppIndicator.IndicatorStatus.ACTIVE)
    indicator.set_menu(menu)

    def copy(url: str) -> None:
        Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD).set_text(url, -1)

    def stop(name: str) -> None:
        try:
            engine.stop(name)
        except engine.EngineError as exc:
            print(f"deskbench: {exc}", file=sys.stderr)
        GLib.idle_add(refresh)

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
            print(f"deskbench: {exc}", file=sys.stderr)
            desktops = []
        if not desktops:
            Gtk.main_quit()
            return False
        rebuild(desktops)
        attention = lock.attention_path().exists()
        indicator.set_status(
            AppIndicator.IndicatorStatus.NEEDS_ATTENTION
            if attention
            else AppIndicator.IndicatorStatus.ACTIVE
        )
        return False

    def on_usr1(*_: object) -> None:
        GLib.idle_add(refresh)

    def tick() -> bool:
        refresh()
        return True

    def watch_events(stop_event: threading.Event) -> None:
        """Re-read the desktop list whenever Podman reports a container change."""
        exe = "podman"
        while not stop_event.is_set():
            try:
                proc = subprocess.Popen(
                    [exe, "events", "--filter", "type=container", "--filter", "label=deskbench=1",
                     "--format", "json"],
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

    signal.signal(signal.SIGUSR1, on_usr1)
    stop_event = threading.Event()
    threading.Thread(target=watch_events, args=(stop_event,), daemon=True).start()
    refresh()
    GLib.timeout_add_seconds(2, tick)
    try:
        Gtk.main()
    finally:
        stop_event.set()
        handle.close()
    return 0
