"""Naming, sizing and URL rules. No containers, no GUI."""

from __future__ import annotations

import unittest

from deskbench import sessions


class Names(unittest.TestCase):
    def test_accepts_ordinary_names(self):
        for name in ("alpha", "a", "desk1", "my-desk-2"):
            self.assertEqual(sessions.validate_name(name), name)

    def test_rejects_unusable_names(self):
        for name in ("", "Alpha", "-lead", "trail-", "two words", "under_score", "x" * 40):
            with self.subTest(name=name), self.assertRaises(sessions.SessionError):
                sessions.validate_name(name)

    def test_container_round_trip(self):
        self.assertEqual(sessions.container_name("alpha"), "deskbench-alpha")
        self.assertEqual(sessions.desktop_name("deskbench-alpha"), "alpha")

    def test_desktop_name_tolerates_foreign_names(self):
        self.assertEqual(sessions.desktop_name("something-else"), "something-else")

    def test_next_free_name_fills_the_first_gap(self):
        self.assertEqual(sessions.next_free_name([]), "desk1")
        self.assertEqual(sessions.next_free_name(["desk1", "desk3"]), "desk2")


class Sizes(unittest.TestCase):
    def test_accepts_plausible_geometry(self):
        for size in ("1024x768", "1600x1000", "3840x2160"):
            self.assertEqual(sessions.validate_size(size), size)

    def test_rejects_nonsense(self):
        for size in ("1600", "x1000", "1600*1000", "10x10", "99999x99999"):
            with self.subTest(size=size), self.assertRaises(sessions.SessionError):
                sessions.validate_size(size)


class Binds(unittest.TestCase):
    def test_defaults_to_mnt_and_read_write(self):
        bind = sessions.parse_bind("/tmp")
        self.assertEqual(bind.source, "/tmp")
        self.assertEqual(bind.target, "/mnt/tmp")
        self.assertFalse(bind.read_only)
        self.assertEqual(bind.as_volume(), "/tmp:/mnt/tmp")

    def test_explicit_destination_and_read_only(self):
        bind = sessions.parse_bind("/tmp:/work:ro")
        self.assertEqual((bind.target, bind.read_only), ("/work", True))
        self.assertEqual(bind.as_volume(), "/tmp:/work:ro")

    def test_rejects_missing_source(self):
        with self.assertRaises(sessions.SessionError):
            sessions.parse_bind("/nope/definitely-not-here")

    def test_rejects_relative_destination(self):
        with self.assertRaises(sessions.SessionError):
            sessions.parse_bind("/tmp:relative/path")

    def test_rejects_unknown_mode(self):
        with self.assertRaises(sessions.SessionError):
            sessions.parse_bind("/tmp:/work:rx")


class Urls(unittest.TestCase):
    def test_viewer_url_autoconnects(self):
        url = sessions.viewer_url(41234)
        self.assertTrue(url.startswith("http://127.0.0.1:41234/"))
        self.assertIn("autoconnect=1", url)


if __name__ == "__main__":
    unittest.main()
