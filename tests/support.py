"""Shared helpers for the container-backed tests."""

from __future__ import annotations

import contextlib
import io
import json
import os
import shutil
import unittest

from deskbench import cli


def e2e_skip_reason() -> str | None:
    if os.environ.get("DESKBENCH_E2E") != "1":
        return "set DESKBENCH_E2E=1 to run the container tests"
    if shutil.which("podman") is None:
        return "podman is not installed"
    return None


def call(*argv: str) -> tuple[int, str, str]:
    """Run the CLI in-process and return (code, stdout, stderr)."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = cli.main(list(argv))
    return code, out.getvalue(), err.getvalue()


class ContainerTest(unittest.TestCase):
    """One desktop per test class, started through the public interface and always cleaned up."""

    desktop = "e2e"
    size = "1024x768"

    @classmethod
    def setUpClass(cls) -> None:
        reason = e2e_skip_reason()
        if reason:
            raise unittest.SkipTest(reason)
        call("stop", cls.desktop)  # left over from a crashed run
        code, out, err = call("new", "--name", cls.desktop, "--size", cls.size)
        if code != 0:
            raise unittest.SkipTest(f"could not start {cls.desktop}: {err.strip() or out.strip()}")
        cls.created = json.loads(out)

    @classmethod
    def tearDownClass(cls) -> None:
        call("stop", cls.desktop)
