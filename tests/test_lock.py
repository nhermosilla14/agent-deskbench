"""Liveness and attention markers. No containers, no GUI."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

from deskbench import lock


class Isolated(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.mkdtemp(prefix="deskbench-test-")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        patcher = mock.patch.dict(os.environ, {"XDG_RUNTIME_DIR": self.tmp})
        patcher.start()
        self.addCleanup(patcher.stop)


class Poke(Isolated):
    def test_poke_is_a_noop_without_a_tray(self):
        self.assertFalse(lock.is_held())
        self.assertFalse(lock.poke())

    def test_poke_refuses_a_pid_that_is_not_a_tray(self):
        bystander = subprocess.Popen(["sleep", "30"])
        self.addCleanup(bystander.kill)
        lock.lock_path().write_text(str(bystander.pid))
        self.assertFalse(lock.poke(), "poke signalled a process it could not identify")
        self.assertIsNone(bystander.poll(), "the bystander was killed by SIGUSR1")
        bystander.terminate()
        bystander.wait(timeout=5)


class Attention(Isolated):
    def test_a_live_asker_raises_attention(self):
        marker = lock.attention_mark("alpha", os.getpid())
        try:
            self.assertTrue(marker.exists())
            self.assertTrue(lock.attention_live())
        finally:
            marker.unlink(missing_ok=True)
        self.assertFalse(lock.attention_live())

    def test_a_dead_asker_is_pruned(self):
        dead = subprocess.Popen(["/bin/true"])
        dead.wait(timeout=10)
        marker = lock.attention_dir() / f"alpha.{dead.pid}"
        marker.touch()
        self.assertFalse(lock.attention_live(), "a dead asker kept the tray pulsing")
        self.assertFalse(marker.exists(), "the stale marker was not removed")

    def test_garbage_markers_are_pruned(self):
        marker = lock.attention_dir() / "notapid"
        marker.touch()
        self.assertFalse(lock.attention_live())
        self.assertFalse(marker.exists())


if __name__ == "__main__":
    unittest.main()
