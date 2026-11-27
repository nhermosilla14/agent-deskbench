"""Host settings file: defaults, round trip, refusal, corruption and atomic writes. No container."""

from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from deskbench import settings, term, sessions


class Isolated(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="deskbench-settings-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        patcher = mock.patch.dict(
            os.environ,
            {
                "XDG_CONFIG_HOME": str(self.tmp / "config"),
                "DESKBENCH_FLAVOURS_DIR": str(self.tmp / "elsewhere"),
            },
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        self.file = self.tmp / "config" / "agent-deskbench" / "settings.toml"


class Load(Isolated):
    def test_absent_file_gives_the_default(self):
        self.assertEqual(settings.load(), settings.Settings(default_size="120x40"))

    def test_corrupt_file_gives_the_default(self):
        self.file.parent.mkdir(parents=True)
        self.file.write_text("[term\n= nonsense")
        self.assertEqual(settings.load().default_size, "120x40")

    def test_non_utf8_file_gives_the_default(self):
        self.file.parent.mkdir(parents=True)
        self.file.write_bytes(b"\xff\xfe[term]")
        self.assertEqual(settings.load().default_size, "120x40")

    def test_wrong_types_and_bad_grids_give_the_default(self):
        self.file.parent.mkdir(parents=True)
        for body in ('term = 5\n', '[term]\ndefault_size = 5\n',
                     '[term]\ndefault_size = "12x40"\n', '[term]\ndefault_size = "120x40x1"\n'):
            with self.subTest(body=body):
                self.file.write_text(body)
                self.assertEqual(settings.load().default_size, "120x40")

    def test_a_directory_in_place_of_the_file_gives_the_default(self):
        self.file.mkdir(parents=True)
        self.assertEqual(settings.load().default_size, "120x40")


class Save(Isolated):
    def test_round_trip(self):
        settings.save(settings.Settings(default_size="100x30"))
        self.assertEqual(settings.load(), settings.Settings(default_size="100x30"))

    def test_file_holds_only_the_term_table(self):
        settings.save(settings.Settings(default_size="100x30"))
        self.assertEqual(self.file.read_text(), '[term]\ndefault_size = "100x30"\n')

    def test_invalid_value_is_refused_and_the_stored_one_is_untouched(self):
        settings.save(settings.Settings(default_size="100x30"))
        before = self.file.read_bytes()
        for value in ("12", "12x40", "120x4", "120x40\"\n[evil]", ""):
            with self.subTest(value=value), self.assertRaises(sessions.SessionError):
                settings.save(settings.Settings(default_size=value))
        self.assertEqual(self.file.read_bytes(), before)
        self.assertEqual(settings.load().default_size, "100x30")

    def test_no_temporary_file_is_left_behind(self):
        settings.save(settings.Settings(default_size="100x30"))
        settings.save(settings.Settings(default_size="110x30"))
        self.assertEqual([entry.name for entry in self.file.parent.iterdir()], ["settings.toml"])

    def test_a_failed_replace_leaves_the_old_file_and_no_temporary(self):
        settings.save(settings.Settings(default_size="100x30"))
        before = self.file.read_bytes()
        with mock.patch("deskbench.settings.os.replace", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                settings.save(settings.Settings(default_size="110x30"))
        self.assertEqual(self.file.read_bytes(), before)
        self.assertEqual([entry.name for entry in self.file.parent.iterdir()], ["settings.toml"])

    def test_validation_reuses_the_cli_bounds(self):
        for value in ("20x5", "500x200", "120x40"):
            term.validate_cells(value)
            settings.save(settings.Settings(default_size=value))
            self.assertEqual(settings.load().default_size, value)


class Location(Isolated):
    def test_xdg_override_is_honoured(self):
        self.assertEqual(settings.path(), self.tmp / "config" / "agent-deskbench" / "settings.toml")

    def test_flavours_dir_never_redirects_settings(self):
        self.assertNotIn("elsewhere", str(settings.path()))

    def test_defaults_to_home_config_when_xdg_is_unset(self):
        with mock.patch.dict(os.environ, {"HOME": str(self.tmp / "home")}):
            os.environ.pop("XDG_CONFIG_HOME", None)
            self.assertEqual(
                settings.path(), self.tmp / "home" / ".config" / "agent-deskbench" / "settings.toml"
            )
