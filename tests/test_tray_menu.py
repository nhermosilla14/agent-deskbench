"""The tray's menu model and its change signature, asserted without GTK."""

from __future__ import annotations

import unittest

from deskbench import engine, settings, term, tray_menu


def desktop(name: str = "desk1", state: str = "running") -> engine.Desktop:
    return engine.Desktop(name=name, container=f"deskbench-{name}", state=state,
                          url=f"http://127.0.0.1:6080/{name}", id=name)


def session(name: str, attached: int = 0) -> term.TermSession:
    return term.TermSession(name=name, cols=120, rows=40, attached=attached)


class Model(unittest.TestCase):
    def test_a_desktop_with_no_sessions_offers_none(self):
        model = tray_menu.build([desktop()], {}, settings.Settings())
        self.assertEqual(len(model.desktops), 1)
        self.assertEqual(model.desktops[0].terminals, ())
        self.assertEqual(model.new_terminal_size, "120x40")

    def test_two_sessions_are_listed_with_their_attached_counts(self):
        model = tray_menu.build(
            [desktop()], {"desk1": [session("main", 1), session("logs", 0)]}, settings.Settings()
        )
        labels = [item.label for item in model.desktops[0].terminals]
        self.assertEqual(labels, ["main  ·  1 attached", "logs  ·  0 attached"])

    def test_only_listed_sessions_appear_so_a_private_shell_is_never_a_terminal(self):
        model = tray_menu.build([desktop()], {"desk1": [session("main")]}, settings.Settings())
        self.assertEqual([item.session for item in model.desktops[0].terminals], ["main"])

    def test_sessions_belong_to_their_own_desktop(self):
        model = tray_menu.build(
            [desktop("a"), desktop("b")], {"b": [session("main")]}, settings.Settings()
        )
        by_name = {entry.name: entry for entry in model.desktops}
        self.assertEqual(by_name["a"].terminals, ())
        self.assertEqual(len(by_name["b"].terminals), 1)

    def test_the_configured_size_is_carried_into_the_model(self):
        model = tray_menu.build([desktop()], {}, settings.Settings(default_size="100x30"))
        self.assertEqual(model.new_terminal_size, "100x30")


class Signature(unittest.TestCase):
    def sig(self, desktops, sessions=None, size="120x40"):
        return tray_menu.signature(
            tray_menu.build(desktops, sessions or {}, settings.Settings(default_size=size))
        )

    def test_identical_content_gives_an_identical_signature(self):
        first = self.sig([desktop()], {"desk1": [session("main", 1)]})
        second = self.sig([desktop()], {"desk1": [session("main", 1)]})
        self.assertEqual(first, second)

    def test_a_new_session_changes_it(self):
        self.assertNotEqual(self.sig([desktop()]), self.sig([desktop()], {"desk1": [session("main")]}))

    def test_an_attach_count_change_changes_it(self):
        base = {"desk1": [session("main", 0)]}
        self.assertNotEqual(self.sig([desktop()], base),
                            self.sig([desktop()], {"desk1": [session("main", 1)]}))

    def test_a_desktop_state_change_changes_it(self):
        self.assertNotEqual(self.sig([desktop(state="running")]),
                            self.sig([desktop(state="exited")]))

    def test_a_settings_change_changes_it(self):
        self.assertNotEqual(self.sig([desktop()], size="120x40"), self.sig([desktop()], size="100x30"))

    def test_the_signature_is_hashable(self):
        hash(self.sig([desktop()], {"desk1": [session("main")]}))
