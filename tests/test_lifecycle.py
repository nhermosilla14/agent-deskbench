"""The tray exists exactly while a desktop exists."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import unittest

from deskbench import lock

from support import call, e2e_skip_reason

PACKAGE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _tray_skip_reason() -> str | None:
    reason = e2e_skip_reason()
    if reason:
        return reason
    if not (os.environ.get("WAYLAND_DISPLAY") or os.environ.get("DISPLAY")):
        return "no graphical session for the tray"
    try:
        import gi  # noqa: F401

        gi.require_version("Gtk", "3.0")
        gi.require_version("AyatanaAppIndicator3", "0.1")
    except (ImportError, ValueError) as exc:
        return f"tray dependencies missing: {exc}"
    return None


def _wait_for(predicate, timeout: float) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.2)
    return False


class TrayLifetime(unittest.TestCase):
    desktop = "e2e-tray"

    @classmethod
    def setUpClass(cls) -> None:
        reason = _tray_skip_reason()
        if reason:
            raise unittest.SkipTest(reason)
        call("stop", cls.desktop)
        code, out, err = call("new", "--name", cls.desktop)
        if code != 0:
            raise unittest.SkipTest(f"could not start {cls.desktop}: {err.strip()}")
        cls.created = json.loads(out)
        env = dict(os.environ, PYTHONPATH=PACKAGE_ROOT)
        cls.proc = subprocess.Popen(
            [sys.executable, "-m", "deskbench", "tray"],
            cwd=PACKAGE_ROOT,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    @classmethod
    def tearDownClass(cls) -> None:
        call("stop", cls.desktop)
        proc = getattr(cls, "proc", None)
        if proc and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
        if proc:
            for stream in (proc.stdout, proc.stderr):
                if stream:
                    stream.close()

    def test_1_a_second_tray_refuses_to_start(self):
        self.assertTrue(_wait_for(lock.is_held, 10), "the tray never took the lock")
        env = dict(os.environ, PYTHONPATH=PACKAGE_ROOT)
        second = subprocess.run(
            [sys.executable, "-m", "deskbench", "tray"],
            cwd=PACKAGE_ROOT,
            env=env,
            capture_output=True,
            timeout=15,
        )
        self.assertEqual(second.returncode, 0, second.stderr.decode("utf-8", "replace"))

    def test_2_tray_exits_when_the_last_desktop_is_stopped(self):
        self.assertTrue(_wait_for(lock.is_held, 10), "the tray never took the lock")
        code, _, _ = call("stop", self.desktop)
        self.assertEqual(code, 0)
        exited = _wait_for(lambda: self.proc.poll() is not None, 20)
        stderr = b""
        if not exited:
            self.proc.kill()
        self.proc.wait(timeout=5)
        stderr = self.proc.stderr.read() if self.proc.stderr else b""
        self.assertTrue(exited, f"the tray did not exit: {stderr.decode('utf-8', 'replace')}")
        self.assertFalse(lock.is_held(), "the tray lock outlived the tray")


class TrayDiesWithItsContainer(unittest.TestCase):
    """A container that dies on its own must take the tray with it, with no CLI call."""

    desktop = "e2e-tray-die"

    @classmethod
    def setUpClass(cls) -> None:
        reason = _tray_skip_reason()
        if reason:
            raise unittest.SkipTest(reason)
        call("stop", cls.desktop)
        code, _, err = call("new", "--name", cls.desktop)
        if code != 0:
            raise unittest.SkipTest(f"could not start {cls.desktop}: {err.strip()}")
        env = dict(os.environ, PYTHONPATH=PACKAGE_ROOT)
        cls.proc = subprocess.Popen(
            [sys.executable, "-m", "deskbench", "tray"],
            cwd=PACKAGE_ROOT,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    @classmethod
    def tearDownClass(cls) -> None:
        call("stop", cls.desktop)
        if cls.proc.poll() is None:
            cls.proc.terminate()
            cls.proc.wait(timeout=5)

    def test_tray_exits_when_the_container_is_killed(self):
        self.assertTrue(_wait_for(lock.is_held, 10), "the tray never took the lock")
        subprocess.run(["podman", "kill", f"deskbench-{self.desktop}"], check=True,
                       capture_output=True, timeout=30)
        self.assertTrue(
            _wait_for(lambda: self.proc.poll() is not None, 20),
            "the tray outlived its container",
        )


if __name__ == "__main__":
    unittest.main()
