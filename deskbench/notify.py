"""``ask``: notify a human, block until they say they are done.

Uses the freedesktop notification service over the session bus. The tray learns about the
request through a per-process marker file, so the two never talk to each other directly and a
killed asker cannot leave the tray pulsing forever.
"""

from __future__ import annotations

import os
import subprocess
import sys

from . import engine, lock

APP_NAME = "deskbench"
SERVICE = "org.freedesktop.Notifications"
OBJECT = "/org/freedesktop/Notifications"

RESULT_DONE = 0
RESULT_TIMEOUT = 4
RESULT_CLOSED = 5


def ask(name: str, message: str, timeout: int = 600) -> int:
    desktop = engine.get(name)

    try:
        import gi

        from gi.repository import Gio, GLib
    except (ImportError, ValueError) as exc:
        print(f"deskbench: ask needs python3-gi ({exc})", file=sys.stderr)
        return 1

    body = message if not desktop.url else f"{message}\n\n{desktop.url}"
    actions = ["open", "Open viewer", "done", "I'm done"]
    hints = {"urgency": GLib.Variant("y", 2)}
    params = GLib.Variant(
        "(susssasa{sv}i)",
        (APP_NAME, 0, "video-display", f"{name} needs you", body, actions, hints, -1),
    )

    try:
        bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        reply = bus.call_sync(
            SERVICE,
            OBJECT,
            SERVICE,
            "Notify",
            params,
            GLib.VariantType.new("(u)"),
            Gio.DBusCallFlags.NONE,
            5000,
            None,
        )
    except GLib.Error as exc:
        print(f"deskbench: could not send a notification: {exc.message}", file=sys.stderr)
        return 1

    notification_id = reply.unpack()[0]
    outcome = {"code": RESULT_CLOSED}
    loop = GLib.MainLoop()

    def on_action(_bus: object, _sender: str, _path: str, _iface: str, _signal: str, args: object) -> None:
        notification, key = args.unpack()
        if notification != notification_id:
            return
        if key == "done":
            outcome["code"] = RESULT_DONE
            loop.quit()
        elif key == "open" and desktop.url:
            subprocess.Popen(
                ["xdg-open", desktop.url],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )

    def on_closed(_bus: object, _sender: str, _path: str, _iface: str, _signal: str, args: object) -> None:
        notification, _reason = args.unpack()
        if notification == notification_id:
            loop.quit()

    def on_service_gone(_bus: object, _sender: str, _path: str, _iface: str,
                        _signal: str, args: object) -> None:
        changed, _old, new = args.unpack()
        if changed == SERVICE and not new:
            outcome["code"] = RESULT_CLOSED
            loop.quit()

    def on_timeout() -> bool:
        outcome["code"] = RESULT_TIMEOUT
        loop.quit()
        return False

    def on_desktop_check() -> bool:
        try:
            engine.get(name)
        except engine.EngineError:
            outcome["code"] = RESULT_CLOSED
            loop.quit()
            return False
        return True

    bus.signal_subscribe(SERVICE, SERVICE, "ActionInvoked", OBJECT, None,
                         Gio.DBusSignalFlags.NONE, on_action)
    bus.signal_subscribe(SERVICE, SERVICE, "NotificationClosed", OBJECT, None,
                         Gio.DBusSignalFlags.NONE, on_closed)
    bus.signal_subscribe("org.freedesktop.DBus", "org.freedesktop.DBus", "NameOwnerChanged",
                         "/org/freedesktop/DBus", None, Gio.DBusSignalFlags.NONE, on_service_gone)

    marker = lock.attention_mark(name, os.getpid())
    try:
        GLib.timeout_add_seconds(timeout, on_timeout)
        GLib.timeout_add_seconds(5, on_desktop_check)
        loop.run()
    finally:
        marker.unlink(missing_ok=True)

    if outcome["code"] == RESULT_TIMEOUT:
        print(f"deskbench: nobody answered for {name} within {timeout}s", file=sys.stderr)
    return outcome["code"]
