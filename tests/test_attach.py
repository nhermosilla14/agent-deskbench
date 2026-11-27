"""Attaching a host terminal to a session, and the private shell. The emulator is a fake that
records its argv; desktops are mocked except where a ContainerTest needs a real one."""

from __future__ import annotations

import json
import os
import shlex
import shutil
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from deskbench import engine, hostterm, runtime as runtimes, sessions

from support import ContainerTest, call

FAKE = Path(__file__).resolve().parent / "fixtures" / "fake-terminal.sh"


class Isolated(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="deskbench-attach-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.log = self.tmp / "emulator.log"
        patcher = mock.patch.dict(
            os.environ,
            {
                "XDG_CONFIG_HOME": str(self.tmp / "config"),
                "DESKBENCH_TERMINAL": str(FAKE),
                "FAKE_TERMINAL_LOG": str(self.log),
                "TERMINAL": "",
            },
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def wait_for_log(self) -> list[str]:
        deadline = time.monotonic() + 5
        while not self.log.exists() and time.monotonic() < deadline:
            time.sleep(0.05)
        self.assertTrue(self.log.exists(), "the fake emulator was never run")
        return self.log.read_text().splitlines()


def mocked_desktop(labels: dict[str, str] | None = None) -> engine.Desktop:
    return engine.Desktop(name="d1", container="deskbench-d1", state="running", url="",
                          id="x", labels=labels if labels is not None else {
                              sessions.RUN_USER_LABEL: "1000:1000"})


class Attach(Isolated):
    def mocked(self, *, session_exists: bool = True):
        """Mock the desktop, the session check and the runtime binary; nothing else."""
        stack = [
            mock.patch.object(engine, "get", return_value=mocked_desktop()),
            mock.patch.object(engine, "_term_exists", return_value=session_exists),
            mock.patch("deskbench.runtime.detect",
                       return_value=runtimes.Runtime(name="podman", binary="/usr/bin/podman")),
        ]
        for patcher in stack:
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_print_shows_the_run_user_and_session_and_spawns_nothing(self):
        self.mocked()
        code, out, err = call("term", "attach", "d1", "--session", "work", "--print")
        self.assertEqual(code, 0, err)
        line = out.strip()
        argv = shlex.split(line)
        self.assertEqual(argv[0], str(FAKE))
        self.assertEqual(argv[1], "-e")
        self.assertEqual(argv[2:], ["/usr/bin/podman", "exec", "-it", "--user", "1000:1000",
                                    "deskbench-d1", "tmux", "attach", "-t", "=work"])
        time.sleep(0.2)
        self.assertFalse(self.log.exists(), "--print ran the emulator")

    def test_a_real_attach_returns_zero_and_the_emulator_gets_the_command(self):
        self.mocked()
        code, _, err = call("term", "attach", "d1")
        self.assertEqual(code, 0, err)
        recorded = self.wait_for_log()
        self.assertIn("exec", recorded)
        self.assertIn("1000:1000", recorded)
        self.assertEqual(recorded[-3:], ["attach", "-t", "=main"])

    def test_a_missing_session_exits_one_and_no_emulator_runs(self):
        self.mocked(session_exists=False)
        code, _, err = call("term", "attach", "d1", "--session", "gone")
        self.assertEqual(code, 1)
        self.assertIn("has ended", err)
        time.sleep(0.2)
        self.assertFalse(self.log.exists())

    def test_an_unknown_desktop_exits_one_and_no_emulator_runs(self):
        code, _, err = call("term", "attach", "no-such-desktop-xyz")
        self.assertEqual(code, 1)
        self.assertIn("no desktop", err)
        time.sleep(0.2)
        self.assertFalse(self.log.exists())

    def test_an_invalid_session_name_exits_one_before_anything_runs(self):
        code, _, err = call("term", "attach", "d1", "--session", "Bad Name")
        self.assertEqual(code, 1)
        self.assertFalse(self.log.exists())

    def test_no_emulator_names_what_was_looked_for(self):
        self.mocked()
        empty = self.tmp / "empty-path"
        empty.mkdir()
        with mock.patch.dict(os.environ, {"DESKBENCH_TERMINAL": "", "PATH": str(empty)}):
            code, _, err = call("term", "attach", "d1")
        self.assertEqual(code, 1)
        self.assertIn("no terminal emulator found", err)
        self.assertIn("gnome-terminal", err)

    def test_an_explicit_emulator_that_is_not_installed_is_an_error(self):
        self.mocked()
        with mock.patch.dict(os.environ, {"DESKBENCH_TERMINAL": "no-such-terminal-xyz"}):
            code, _, err = call("term", "attach", "d1", "--print")
        self.assertEqual(code, 1)
        self.assertIn("DESKBENCH_TERMINAL", err)

    def test_declared_arguments_are_kept_before_the_command(self):
        self.mocked()
        with mock.patch.dict(os.environ, {"DESKBENCH_TERMINAL": f"{FAKE} --title work"}):
            argv = hostterm.attach_argv("d1", "main")
        self.assertEqual(argv[:3], [str(FAKE), "--title", "work"])
        self.assertEqual(argv[3], "-e")

    def test_known_emulators_use_their_own_separator(self):
        with mock.patch.object(hostterm, "emulator", return_value=["/usr/bin/gnome-terminal"]):
            argv = hostterm._in_terminal(["podman", "exec"])
        self.assertEqual(argv, ["/usr/bin/gnome-terminal", "--", "podman", "exec"])

    def test_the_private_shell_is_sh_login_with_no_multiplexer(self):
        with mock.patch.object(engine, "get", return_value=mocked_desktop()), \
                mock.patch("deskbench.runtime.detect",
                           return_value=runtimes.Runtime(name="podman", binary="/usr/bin/podman")):
            argv = engine.shell_command("d1")
        self.assertEqual(argv, ["/usr/bin/podman", "exec", "-it", "--user", "1000:1000",
                                "deskbench-d1", "sh", "-l"])
        self.assertNotIn("tmux", argv)


class Live(ContainerTest):
    """A real desktop: the session is real, the emulator is the fake."""

    desktop = "e2e-attach"
    size = "1024x768"

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="deskbench-live-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.log = self.tmp / "emulator.log"
        patcher = mock.patch.dict(
            os.environ,
            {"DESKBENCH_TERMINAL": str(FAKE), "FAKE_TERMINAL_LOG": str(self.log), "TERMINAL": ""},
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_attach_to_a_real_session_and_the_shell_is_not_a_session(self):
        code, _, err = call("term", "start", self.desktop, "--cells", "80x24")
        self.assertEqual(code, 0, err)
        self.addCleanup(call, "term", "stop", self.desktop)

        code, _, err = call("term", "attach", self.desktop)
        self.assertEqual(code, 0, err)
        deadline = time.monotonic() + 10
        while not self.log.exists() and time.monotonic() < deadline:
            time.sleep(0.1)
        self.assertIn("=main", self.log.read_text())

        code, out, _ = call("term", "list", self.desktop, "--json")
        self.assertEqual(code, 0)
        self.assertEqual([entry["name"] for entry in json.loads(out)], ["main"])

        argv = engine.shell_command(self.desktop)
        self.assertEqual(argv[-2:], ["sh", "-l"])
        self.assertNotIn("tmux", argv)
