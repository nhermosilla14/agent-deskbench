"""Built-in flavours name OCI references; ``new`` pulls instead of building."""

from __future__ import annotations

import contextlib
import io
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from deskbench import engine, flavours
from deskbench import runtime as runtimes
from deskbench.cli import build_parser

from support import call, e2e_skip_reason

BASE_IMAGE = "ghcr.io/nhermosilla14/agent-deskbench/desktop:1"


def _container_image(container_id: str) -> str:
    """The image reference the running container was started from."""
    result = subprocess.run(
        ["podman", "inspect", "--format", "{{.Config.Image}}", container_id],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        raise AssertionError(f"podman inspect failed: {result.stderr.strip()}")
    return result.stdout.strip()


class ImageReferences(unittest.TestCase):
    """The container-backed contract: local refs are started, absent ones refuse cleanly."""

    desktop = "e2e-image"
    direct = "e2e-image-direct"
    absent = "e2e-image-absent"

    @classmethod
    def setUpClass(cls) -> None:
        reason = e2e_skip_reason()
        if reason:
            raise unittest.SkipTest(reason)
        cls.registry = os.environ["DESKBENCH_REGISTRY"]
        cls.base_image = f"{cls.registry}/desktop:1"
        for name in (cls.desktop, cls.direct, cls.absent):
            call("stop", name)
        code, out, err = call("new", "--name", cls.desktop, "--size", "1024x768")
        if code != 0:
            raise unittest.SkipTest(
                f"could not start {cls.desktop}: {err.strip() or out.strip()}"
            )
        cls.created = json.loads(out)

    @classmethod
    def tearDownClass(cls) -> None:
        for name in (cls.desktop, cls.direct, cls.absent):
            call("stop", name)

    def test_new_uses_the_local_builtin_ref(self):
        self.assertEqual(self.created["name"], self.desktop)
        self.assertTrue(self.created["url"].startswith("http://127.0.0.1:"))
        self.assertTrue(self.created["id"])
        self.assertTrue(engine.image_exists(self.base_image))
        self.assertEqual(_container_image(self.created["id"]), self.base_image)

    def test_image_flag_runs_a_direct_reference(self):
        code, out, err = call(
            "new", "--name", self.direct, "--size", "1024x768",
            "--image", self.base_image,
        )
        self.assertEqual(code, 0, err)
        created = json.loads(out)
        self.assertEqual(created["name"], self.direct)
        self.assertTrue(created["url"].startswith("http://127.0.0.1:"))
        self.assertEqual(_container_image(created["id"]), self.base_image)

    def test_pull_never_fails_when_the_image_is_absent(self):
        absent = f"{self.registry}/absent:1"
        code, out, err = call(
            "new", "--name", self.absent, "--image", absent, "--pull=never",
        )
        self.assertEqual(code, 1)
        self.assertIn(absent, err)
        self.assertEqual(out.strip(), "", "a failed new must not print a desktop JSON")
        result = subprocess.run(
            ["podman", "container", "exists", f"deskbench-{self.absent}"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertNotEqual(result.returncode, 0, "a container was created despite --pull=never")

    def test_images_lists_builtin_references(self):
        code, out, err = call("images", "--json")
        self.assertEqual(code, 0, err)
        rows = {
            row["name"]: row
            for row in json.loads(out)
            if row["source"] == "builtin"
        }
        self.assertEqual(set(rows), set(flavours.names()))
        expected = {
            "base": f"{self.registry}/desktop:1",
            "firefox": f"{self.registry}/desktop-firefox:1",
            "chromium": f"{self.registry}/desktop-chromium:1",
        }
        for name, image in expected.items():
            with self.subTest(flavour=name):
                row = rows[name]
                self.assertEqual(row["source"], "builtin")
                self.assertEqual(row["image"], image)
                self.assertIsInstance(row["present"], bool)
                self.assertNotIn("built", row)
        self.assertTrue(rows["base"]["present"])
        self.assertTrue(rows["base"]["summary"])

    def test_images_table_carries_refs_and_summaries(self):
        code, out, err = call("images")
        self.assertEqual(code, 0, err)
        for name in flavours.names():
            with self.subTest(flavour=name):
                flavour = flavours.get(name)
                self.assertIn(name, out)
                self.assertIn(flavour.image, out)
                self.assertIn(flavour.summary, out)


class UserFlavours(unittest.TestCase):
    """A flavour defined under the config directory starts like a built-in and is reported."""

    desktop = "e2e-user-flavour"
    broken = "e2e-user-broken"
    flavour = "custom"
    malformed = "broken"
    summary = "User flavour for the suite"

    @classmethod
    def setUpClass(cls) -> None:
        reason = e2e_skip_reason()
        if reason:
            raise unittest.SkipTest(reason)
        cls.registry = os.environ["DESKBENCH_REGISTRY"]
        cls.base_image = f"{cls.registry}/desktop:1"
        if not engine.image_exists(cls.base_image):
            raise unittest.SkipTest(
                f"{cls.base_image} is absent; build it with `task image` first"
            )

        cls._tempdir = tempfile.TemporaryDirectory()
        directory = Path(cls._tempdir.name)
        (directory / cls.flavour).mkdir()
        (directory / cls.flavour / "flavour.toml").write_text(
            f'image = "{cls.base_image}"\nsummary = "{cls.summary}"\n',
            encoding="utf-8",
        )
        (directory / cls.malformed).mkdir()
        cls.manifest = directory / cls.malformed / "flavour.toml"
        cls.manifest.write_text("image = \n", encoding="utf-8")

        cls._env = mock.patch.dict(
            os.environ, {"DESKBENCH_FLAVOURS_DIR": str(directory)}
        )
        cls._env.start()
        try:
            call("stop", cls.desktop)
            code, out, err = call(
                "new", "--name", cls.desktop, "--size", "1024x768",
                "--flavour", cls.flavour,
            )
        except BaseException:
            cls._cleanup()
            raise
        if code != 0:
            cls._cleanup()
            raise unittest.SkipTest(
                f"could not start {cls.desktop}: {err.strip() or out.strip()}"
            )
        cls.created = json.loads(out)

    @classmethod
    def _cleanup(cls) -> None:
        call("stop", cls.desktop)
        cls._tempdir.cleanup()
        cls._env.stop()

    @classmethod
    def tearDownClass(cls) -> None:
        cls._cleanup()

    def test_named_flavour_from_the_config_directory(self):
        self.assertEqual(self.created["name"], self.desktop)
        self.assertTrue(self.created["url"].startswith("http://127.0.0.1:"))
        self.assertEqual(_container_image(self.created["id"]), self.base_image)

        code, _, err = call("exec", self.desktop, "--", "true")
        self.assertEqual(code, 0, err)

        code, out, err = call("images", "--json")
        self.assertEqual(code, 0, err)
        rows = {row["name"]: row for row in json.loads(out)}
        self.assertIn(self.flavour, rows)
        self.assertEqual(rows[self.flavour]["source"], "user")
        self.assertEqual(rows[self.flavour]["image"], self.base_image)
        self.assertTrue(rows[self.flavour]["present"])
        self.assertEqual(rows[self.flavour]["summary"], self.summary)

    def test_malformed_manifest_warns_without_hiding_valid_flavours(self):
        code, out, err = call("images", "--json")
        self.assertEqual(code, 0, err)
        self.assertIn(f"deskbench: ignoring {self.manifest}", err)
        self.assertIn("invalid TOML", err)
        rows = {row["name"]: row for row in json.loads(out)}
        self.assertIn(self.flavour, rows)
        self.assertNotIn(self.malformed, rows)

    def test_new_fails_for_a_malformed_manifest(self):
        code, out, err = call(
            "new", "--name", self.broken, "--flavour", self.malformed,
        )
        self.assertEqual(code, 1)
        self.assertEqual(out.strip(), "", "a failed new must not print a desktop JSON")
        self.assertIn(str(self.manifest), err)
        result = subprocess.run(
            ["podman", "container", "exists", f"deskbench-{self.broken}"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertNotEqual(result.returncode, 0, "a container was created for a bad manifest")


class Arguments(unittest.TestCase):
    def test_defaults_to_base_with_the_missing_pull_policy(self):
        args = build_parser().parse_args(["new"])
        self.assertIsNone(args.flavour)
        self.assertIsNone(args.image)
        self.assertEqual(args.pull, "missing")

    def test_flavour_and_image_are_mutually_exclusive(self):
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                build_parser().parse_args(
                    ["new", "--flavour", "base", "--image", BASE_IMAGE]
                )


class PullPolicy(unittest.TestCase):
    """The decision to pull is testable without a runtime; nothing may ever build."""

    image = BASE_IMAGE

    def _ensure(self, present: bool, policy: str) -> mock.Mock:
        with mock.patch.object(engine, "image_exists", return_value=present), \
                mock.patch.object(engine, "_podman") as podman, \
                contextlib.redirect_stderr(io.StringIO()):
            engine.ensure_image(self.image, policy)
        return podman

    def test_missing_does_not_pull_when_present(self):
        podman = self._ensure(True, "missing")
        podman.assert_not_called()

    def test_missing_pulls_when_absent(self):
        podman = self._ensure(False, "missing")
        podman.assert_called_once_with(["pull", self.image], capture=False)

    def test_always_pulls_even_when_present(self):
        podman = self._ensure(True, "always")
        podman.assert_called_once_with(["pull", self.image], capture=False)

    def test_never_raises_when_absent(self):
        with mock.patch.object(engine, "image_exists", return_value=False), \
                mock.patch.object(engine, "_podman") as podman:
            with self.assertRaises(engine.EngineError) as caught:
                engine.ensure_image(self.image, "never")
        self.assertIn(self.image, str(caught.exception))
        self.assertIn("--pull=never", str(caught.exception))
        podman.assert_not_called()

    def test_never_returns_when_present(self):
        podman = self._ensure(True, "never")
        podman.assert_not_called()

    def test_create_never_runs_a_build(self):
        desktop = engine.Desktop(
            name="demo",
            container="deskbench-demo",
            state="running",
            url="http://127.0.0.1:6080/",
            id="abc",
        )
        runtime = runtimes.Runtime(name="podman", binary="podman")
        with mock.patch.object(engine, "image_exists", return_value=True), \
                mock.patch.object(engine, "_podman") as podman, \
                mock.patch.object(engine.runtimes, "detect", return_value=runtime), \
                mock.patch.object(engine, "get", return_value=desktop), \
                mock.patch.object(engine, "wait_ready", return_value=desktop):
            created = engine.create("demo", "800x600", self.image)

        self.assertIs(created, desktop)
        self.assertTrue(podman.called)
        for invocation in podman.call_args_list:
            self.assertNotIn("build", invocation.args[0])


if __name__ == "__main__":
    unittest.main()
