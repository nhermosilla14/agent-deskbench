"""Handoff: the notification is well formed and the timeout path is honoured."""

from __future__ import annotations

import subprocess
import time
import unittest

from deskbench import lock

from support import ContainerTest, call, e2e_skip_reason


def _notifications_available() -> bool:
    try:
        proc = subprocess.run(
            ["gdbus", "call", "--session", "--dest", "org.freedesktop.DBus",
             "--object-path", "/org/freedesktop/DBus", "--method",
             "org.freedesktop.DBus.NameHasOwner", "org.freedesktop.Notifications"],
            capture_output=True, text=True, timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return proc.returncode == 0 and "true" in proc.stdout.strip()


class Handoff(ContainerTest):
    desktop = "e2e-ask"

    @classmethod
    def setUpClass(cls) -> None:
        if not _notifications_available():
            raise unittest.SkipTest("no notification service on the session bus")
        super().setUpClass()

    def test_timeout_is_reported_and_the_marker_is_cleared(self):
        started = time.monotonic()
        code, _, err = call("ask", self.desktop, "e2e timeout check", "--timeout", "1")
        elapsed = time.monotonic() - started
        self.assertEqual(code, 4, err)
        self.assertGreaterEqual(elapsed, 1.0)
        self.assertLess(elapsed, 10.0, "ask did not return promptly after its timeout")
        self.assertFalse(lock.attention_live(), "the attention marker was left behind")


class AskArgumentHandling(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        reason = e2e_skip_reason()
        if reason:
            raise unittest.SkipTest(reason)

    def test_unknown_desktop_does_not_notify(self):
        code, _, err = call("ask", "nope", "hello", "--timeout", "1")
        self.assertEqual(code, 1)
        self.assertIn("nope", err)


if __name__ == "__main__":
    unittest.main()
