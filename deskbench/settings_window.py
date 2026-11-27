"""The Settings window: one field, Save and Cancel. The tray creates it once and reuses it.

Closing the window hides it; the tray keeps running. Requires GTK 3, so it is imported only by the
tray after the GI versions are chosen.
"""

from __future__ import annotations

from collections.abc import Callable

from gi.repository import Gtk

from . import notify, settings as settings_store


class SettingsWindow(Gtk.Dialog):
    def __init__(self, on_saved: Callable[[settings_store.Settings], None]) -> None:
        super().__init__(title="agent-deskbench settings")
        self._on_saved = on_saved
        self.set_default_size(360, 0)
        self.set_resizable(False)
        self.add_button("Cancel", Gtk.ResponseType.CANCEL)
        self.add_button("Save", Gtk.ResponseType.OK)
        self.set_default_response(Gtk.ResponseType.OK)

        box = self.get_content_area()
        box.set_spacing(6)
        box.set_border_width(12)
        box.pack_start(Gtk.Label(label="Default size for new terminals", xalign=0), False, False, 0)
        self._entry = Gtk.Entry()
        self._entry.set_placeholder_text("COLSxROWS, for example 120x40")
        self._entry.set_activates_default(True)
        box.pack_start(self._entry, False, False, 0)
        self._error = Gtk.Label(xalign=0)
        self._error.set_line_wrap(True)
        self._error.get_style_context().add_class("error")
        box.pack_start(self._error, False, False, 0)

        self.connect("response", self._on_response)
        self.connect("delete-event", self._on_delete)

    def open(self, current: settings_store.Settings) -> None:
        """Show the window with the stored value, discarding anything typed but not saved."""
        self._entry.set_text(current.default_size)
        self._error.set_text("")
        self.show_all()
        self.present()

    def _on_delete(self, *_: object) -> bool:
        self.hide()
        return True  # hide and keep the tray alive; returning False would end the GLib loop

    def _on_response(self, _dialog: object, response: int) -> None:
        if response != Gtk.ResponseType.OK:
            self.hide()
            return
        candidate = settings_store.Settings(default_size=self._entry.get_text().strip())
        try:
            settings_store.save(candidate)
        except ValueError as exc:
            # Refused here: the window stays open and the stored value is untouched.
            self._error.set_text(str(exc))
            return
        except OSError as exc:
            notify.send_async("Could not save settings", str(exc))
            return
        self.hide()
        self._on_saved(candidate)
