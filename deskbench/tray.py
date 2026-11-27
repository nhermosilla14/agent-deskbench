"""The tray: a StatusNotifierItem that exists exactly while a desktop exists."""

from __future__ import annotations

import signal
import subprocess
import sys
import threading
import time
from collections.abc import Callable

from . import engine, hostterm, lock, notify, runtime as runtimes, settings as settings_store
from . import term, tray_menu

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

        from .settings_window import SettingsWindow
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

    # Only the main thread touches these; workers hand results back through GLib.idle_add.
    polling = threading.Lock()
    state: dict = {"settings": settings_store.load(), "shown": None}
    settings_dialog: list[SettingsWindow] = []

    def copy(url: str) -> None:
        clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        clipboard.set_text(url, -1)
        clipboard.store()  # survive the tray exiting

    def run_action(title: str, action: Callable[[], None]) -> None:
        """Run a runtime-touching action off the GUI thread; a failure becomes a notification."""

        def worker() -> None:
            try:
                action()
            except Exception as exc:  # any failure must reach the human, not die silently here
                GLib.idle_add(notify.send_async, title, str(exc))
            GLib.idle_add(refresh)

        threading.Thread(target=worker, daemon=True).start()

    def stop(name: str) -> None:
        # Stopping takes a second or two; never block the menu on it.
        def worker() -> None:
            try:
                engine.stop(name)
            except engine.EngineError as exc:
                print(f"deskbench: {exc}", file=sys.stderr)
            GLib.idle_add(refresh)

        threading.Thread(target=worker, daemon=True).start()

    def new_terminal(name: str) -> None:
        size = state["settings"].default_size

        def action() -> None:
            cols, rows = term.validate_cells(size)
            if not any(entry.name == term.DEFAULT_SESSION for entry in engine.term_list(name)):
                engine.term_start(name, cols, rows, term.DEFAULT_SESSION)
            hostterm.attach(name, term.DEFAULT_SESSION)

        run_action(f"Could not open a terminal on {name}", action)

    def open_settings() -> None:
        if not settings_dialog:
            settings_dialog.append(SettingsWindow(on_saved=on_settings_saved))
        settings_dialog[0].open(state["settings"])

    def on_settings_saved(saved: settings_store.Settings) -> None:
        state["settings"] = saved
        refresh()

    def rebuild(model: tray_menu.MenuModel) -> None:
        for child in menu.get_children():
            menu.remove(child)
        for desktop in model.desktops:
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

            submenu.append(Gtk.SeparatorMenuItem())
            header = Gtk.MenuItem(label="Terminals")
            header.set_sensitive(False)
            submenu.append(header)
            for terminal in desktop.terminals:
                item = Gtk.MenuItem(label=terminal.label)
                item.connect(
                    "activate",
                    lambda *_, name=desktop.name, session=terminal.session: run_action(
                        f"Could not attach to {name}",
                        lambda: hostterm.attach(name, session),
                    ),
                )
                submenu.append(item)

            new_item = Gtk.MenuItem(label="New terminal…")
            new_item.set_tooltip_text(f"Starts {term.DEFAULT_SESSION} at {model.new_terminal_size} if absent")
            new_item.connect("activate", lambda *_, name=desktop.name: new_terminal(name))
            submenu.append(new_item)

            shell_item = Gtk.MenuItem(label="Open private shell")
            shell_item.set_tooltip_text("Not shared with the agent; secrets are safe here")
            shell_item.connect(
                "activate",
                lambda *_, name=desktop.name: run_action(
                    f"Could not open a shell on {name}", lambda: hostterm.open_shell(name)
                ),
            )
            submenu.append(shell_item)

            top.set_submenu(submenu)
            menu.append(top)

        menu.append(Gtk.SeparatorMenuItem())
        settings_item = Gtk.MenuItem(label="Settings…")
        settings_item.connect("activate", lambda *_: open_settings())
        menu.append(settings_item)
        quit_item = Gtk.MenuItem(label="Quit")
        quit_item.connect("activate", lambda *_: Gtk.main_quit())
        menu.append(quit_item)
        menu.show_all()

    def apply(desktops: list[engine.Desktop], sessions: dict) -> bool:
        if not desktops:
            Gtk.main_quit()
            return False
        last_sessions.clear()
        last_sessions.update(sessions)
        model = tray_menu.build(desktops, sessions, state["settings"])
        signature = tray_menu.signature(model)
        if signature != state["shown"]:
            state["shown"] = signature
            rebuild(model)
        indicator.set_status(
            AppIndicator.IndicatorStatus.NEEDS_ATTENTION
            if lock.attention_live()
            else AppIndicator.IndicatorStatus.ACTIVE
        )
        return False

    def poll(known: dict) -> None:
        """Read desktops and their sessions off the GUI thread, then hand the result back."""
        try:
            desktops = engine.list_desktops()
            sessions: dict = {}
            for desktop in desktops:
                if desktop.state != "running":
                    continue
                try:
                    sessions[desktop.name] = engine.term_list(desktop.name)
                except engine.EngineError:
                    # A transient failure must not hide sessions that are still running.
                    if desktop.name in known:
                        sessions[desktop.name] = known[desktop.name]
            GLib.idle_add(apply, desktops, sessions)
        except engine.EngineError as exc:
            # A transient failure must not hide desktops that are still running.
            print(f"deskbench: {exc}", file=sys.stderr)
        finally:
            polling.release()

    last_sessions: dict = {}

    def refresh() -> bool:
        """Start a poll unless one is already in flight, so a wedged runtime cannot pile up ticks."""
        if not polling.acquire(blocking=False):
            return False
        threading.Thread(target=poll, args=(dict(last_sessions),), daemon=True).start()
        return False

    def tick() -> bool:
        refresh()
        return True

    def watch_events(stop_event: threading.Event) -> None:
        """Re-read the desktop list whenever the runtime reports a container change."""
        runtime = runtimes.detect()
        command = runtimes.events_command(runtime, "deskbench=1")
        while not stop_event.is_set():
            try:
                proc = subprocess.Popen(
                    [runtime.binary, *command],
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
