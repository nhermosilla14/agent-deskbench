"""End-to-end through the CLI: create, list, open, drive, capture, stop."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from support import ContainerTest, call, e2e_skip_reason, png_colour_count

PACKAGE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class Desktops(ContainerTest):
    def test_new_reports_a_usable_desktop(self):
        created = self.created
        self.assertEqual(created["name"], self.desktop)
        self.assertTrue(created["url"].startswith("http://127.0.0.1:"))
        self.assertTrue(created["id"])

    def test_viewer_url_serves_novnc(self):
        deadline = time.monotonic() + 20
        last: Exception | None = None
        while time.monotonic() < deadline:
            try:
                with urllib.request.urlopen(self.created["url"], timeout=5) as response:
                    self.assertEqual(response.status, 200)
                    body = response.read().decode("utf-8", "replace").lower()
                break
            except (urllib.error.URLError, ConnectionError) as exc:
                last = exc
                time.sleep(0.5)
        else:
            self.fail(f"the viewer never answered: {last}")
        self.assertIn("novnc", body)

    def test_ls_json_includes_the_desktop(self):
        code, out, _ = call("ls", "--json")
        self.assertEqual(code, 0)
        names = [entry["name"] for entry in json.loads(out)]
        self.assertIn(self.desktop, names)

    def test_url_verb_matches_ls(self):
        code, out, _ = call("url", self.desktop)
        self.assertEqual(code, 0)
        self.assertEqual(out.strip(), self.created["url"])


class Capture(unittest.TestCase):
    """A shot must show what a human would see, without the caller guessing at sleeps."""

    desktop = "e2e-frame"

    @classmethod
    def setUpClass(cls) -> None:
        reason = e2e_skip_reason()
        if reason:
            raise unittest.SkipTest(reason)
        call("stop", cls.desktop)
        code, _, err = call("new", "--name", cls.desktop, "--size", "1024x768")
        if code != 0:
            raise unittest.SkipTest(f"could not start {cls.desktop}: {err.strip()}")

    @classmethod
    def tearDownClass(cls) -> None:
        call("stop", cls.desktop)

    def shoot(self, *extra: str) -> str:
        destination = f"/tmp/deskbench-frame-{os.getpid()}.png"
        self.addCleanup(lambda: os.path.exists(destination) and os.unlink(destination))
        code, out, err = call("shot", self.desktop, "-o", destination, *extra)
        self.assertEqual(code, 0, err)
        self.assertEqual(out.strip(), destination)
        return destination

    def test_immediate_shot_after_launch_shows_the_window(self):
        # No sleep on purpose: this is the race the tool exists to absorb.
        call("exec", self.desktop, "--", "sh", "-c", "xterm -geometry 40x10+20+20 &")
        destination = self.shoot()
        self.assertGreater(png_colour_count(destination), 1,
                           "the capture came back blank; the window was not waited for")

    def test_shot_still_returns_when_nothing_is_drawn(self):
        # Close the window and wait for the window manager to drop it, otherwise the capture
        # legitimately still contains it.
        call("exec", self.desktop, "--", "pkill", "xterm")
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            _, clients, _ = call("exec", self.desktop, "--", "xprop", "-root", "_NET_CLIENT_LIST")
            if "0x" not in clients:
                break
            time.sleep(0.3)
        destination = self.shoot()
        with open(destination, "rb") as handle:
            self.assertEqual(handle.read(8), b"\x89PNG\r\n\x1a\n")
        self.assertEqual(png_colour_count(destination), 1)


class AgentSurface(ContainerTest):
    desktop = "e2e-drive"

    def cli(self, *argv: str) -> subprocess.CompletedProcess:
        """Invoke the real entry point, so streaming output is captured like a user's would be."""
        return subprocess.run(
            [sys.executable, "-m", "deskbench", *argv],
            cwd=PACKAGE_ROOT,
            capture_output=True,
            text=True,
            timeout=60,
        )

    def test_exec_propagates_output_and_exit_code(self):
        result = self.cli("exec", self.desktop, "--", "echo", "hello bench")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("hello bench", result.stdout)

    def test_exec_propagates_failure(self):
        result = self.cli("exec", self.desktop, "--", "sh", "-c", "exit 7")
        self.assertEqual(result.returncode, 7)

    def test_shot_writes_a_png(self):
        destination = f"/tmp/deskbench-shot-test-{os.getpid()}.png"
        self.addCleanup(lambda: os.path.exists(destination) and os.unlink(destination))
        code, out, err = call("shot", self.desktop, "-o", destination)
        self.assertEqual(code, 0, err)
        self.assertEqual(out.strip(), destination)
        with open(destination, "rb") as handle:
            self.assertEqual(handle.read(8), b"\x89PNG\r\n\x1a\n")

    def test_logs_returns_something(self):
        code, out, _ = call("logs", self.desktop, "-n", "5")
        self.assertEqual(code, 0)
        self.assertIsInstance(out, str)


class BindMounts(unittest.TestCase):
    """The project under test has to be visible inside the desktop."""

    desktop = "e2e-bind"

    @classmethod
    def setUpClass(cls) -> None:
        reason = e2e_skip_reason()
        if reason:
            raise unittest.SkipTest(reason)
        cls.work = tempfile.mkdtemp(prefix="deskbench-bind-")
        Path(cls.work, "hello.txt").write_text("from the host\n")
        cls.mounted = f"/mnt/{os.path.basename(cls.work)}"
        call("stop", cls.desktop)
        code, _, err = call("new", "--name", cls.desktop, "--size", "800x600",
                            "--bind", cls.work,
                            "--bind", f"{cls.work}:/mnt/readonly:ro")
        if code != 0:
            shutil.rmtree(cls.work, ignore_errors=True)
            raise unittest.SkipTest(f"could not start {cls.desktop}: {err.strip()}")

    @classmethod
    def tearDownClass(cls) -> None:
        call("stop", cls.desktop)
        shutil.rmtree(cls.work, ignore_errors=True)

    def test_host_file_is_visible_inside(self):
        result = subprocess.run(
            [sys.executable, "-m", "deskbench", "exec", self.desktop, "--",
             "cat", f"{self.mounted}/hello.txt"],
            cwd=PACKAGE_ROOT, capture_output=True, text=True, timeout=60,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("from the host", result.stdout)

    def test_writes_round_trip_to_the_host(self):
        code, _, err = call("exec", self.desktop, "--", "sh", "-c",
                            f"echo made-inside > {self.mounted}/made.txt")
        self.assertEqual(code, 0, err)
        self.assertEqual(Path(self.work, "made.txt").read_text().strip(), "made-inside")

    def test_read_only_mount_refuses_writes(self):
        code, _, _ = call("exec", self.desktop, "--", "sh", "-c",
                          "touch /mnt/readonly/nope")
        self.assertNotEqual(code, 0, "a read-only mount accepted a write")
        self.assertFalse(Path(self.work, "nope").exists())


class Failures(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        reason = e2e_skip_reason()
        if reason:
            raise unittest.SkipTest(reason)

    def test_unknown_desktop_fails_cleanly(self):
        code, _, err = call("url", "does-not-exist")
        self.assertEqual(code, 1)
        self.assertIn("does-not-exist", err)

    def test_invalid_name_is_rejected(self):
        code, _, err = call("new", "--name", "Not Valid")
        self.assertEqual(code, 1)
        self.assertIn("invalid desktop name", err)


if __name__ == "__main__":
    unittest.main()
