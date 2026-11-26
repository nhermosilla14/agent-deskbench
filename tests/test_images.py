"""Built-in flavours name OCI references; ``new`` pulls instead of building."""

from __future__ import annotations

import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
import urllib.request
from pathlib import Path
from unittest import mock

from deskbench import engine, flavours
from deskbench import runtime as runtimes
from deskbench.cli import build_parser

from support import call, e2e_skip_reason

BASE_IMAGE = "ghcr.io/nhermosilla14/agent-deskbench/desktop:1"
ADAPTER_IMAGE = "localhost/agent-deskbench/adapter-fixture:1"
REPO_ROOT = Path(__file__).resolve().parent.parent


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


ADAPTER_MANIFEST = """\
image = "localhost/agent-deskbench/adapter-fixture:1"
summary = "Adapter fixture"

[viewer]
port = 3000
path = "/"

[run]
entrypoint = ["/usr/local/bin/adapter-entrypoint"]
env = { ADAPTER_MARKER = "from-manifest", ADAPTER_SIZE = "{width}x{height}" }
"""

ADAPTER_SCREENSHOT_MANIFEST = """\
image = "localhost/agent-deskbench/adapter-fixture:1"
summary = "Adapter fixture with a custom screenshot command"

[viewer]
port = 3000
path = "/"

[run]
entrypoint = ["/usr/local/bin/adapter-entrypoint"]

[screenshot]
command = ["/usr/local/bin/adapter-shot", "{output}"]
settle = false
"""

ADAPTER_BAD_SCREENSHOT_MANIFEST = """\
image = "localhost/agent-deskbench/adapter-fixture:1"
summary = "Adapter fixture whose screenshot always fails"

[viewer]
port = 3000
path = "/"

[run]
entrypoint = ["/usr/local/bin/adapter-entrypoint"]

[screenshot]
command = ["/bin/false", "{output}"]
settle = false
"""


class Adapter(unittest.TestCase):
    """A third-party image with its own viewer, entrypoint, environment and port is usable."""

    desktop = "e2e-adapter"
    flavour = "adapter"
    size = "800x600"

    @classmethod
    def setUpClass(cls) -> None:
        reason = e2e_skip_reason()
        if reason:
            raise unittest.SkipTest(reason)
        cls.registry = os.environ["DESKBENCH_REGISTRY"]
        base = f"{cls.registry}/desktop:1"
        if not engine.image_exists(base):
            raise unittest.SkipTest(
                f"{base} is absent; build it with `task image` first"
            )
        if not engine.image_exists(ADAPTER_IMAGE):
            try:
                subprocess.run(
                    ["podman", "build", "-t", ADAPTER_IMAGE, "tests/fixtures/adapter"],
                    cwd=REPO_ROOT,
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=600,
                )
            except subprocess.CalledProcessError as exc:
                raise unittest.SkipTest(
                    f"could not build the adapter fixture: {exc.stderr.strip()}"
                ) from exc

        cls._tempdir = tempfile.TemporaryDirectory()
        directory = Path(cls._tempdir.name)
        (directory / cls.flavour).mkdir()
        (directory / cls.flavour / "flavour.toml").write_text(
            ADAPTER_MANIFEST, encoding="utf-8"
        )
        cls._env = mock.patch.dict(
            os.environ, {"DESKBENCH_FLAVOURS_DIR": str(directory)}
        )
        cls._env.start()
        try:
            call("stop", cls.desktop)
            code, out, err = call(
                "new", "--name", cls.desktop, "--size", cls.size,
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

    def test_custom_viewer_port_path_and_entrypoint(self):
        url = self.created["url"]
        self.assertTrue(url.startswith("http://127.0.0.1:"), url)
        self.assertTrue(url.endswith("/"), url)

        with urllib.request.urlopen(url, timeout=10) as response:
            self.assertEqual(response.status, 200)
            body = response.read().decode("utf-8", "replace")
        self.assertIn("adapter viewer", body.lower())

        code, out, err = call("url", self.desktop)
        self.assertEqual(code, 0, err)
        self.assertEqual(out.strip(), url)

        code, out, err = call("ls", "--json")
        self.assertEqual(code, 0, err)
        rows = {row["name"]: row for row in json.loads(out)}
        self.assertEqual(rows[self.desktop]["url"], url)

        # The fixture's default entrypoint is /bin/false; running at all proves the override.
        result = subprocess.run(
            ["podman", "inspect", "--format", "{{json .Config.Entrypoint}}",
             self.created["id"]],
            capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("/usr/local/bin/adapter-entrypoint", result.stdout)
        self.assertNotIn("/bin/false", result.stdout)

    def cli(self, *argv: str) -> subprocess.CompletedProcess:
        """Run the real entry point, so child output is captured rather than inherited."""
        return subprocess.run(
            [sys.executable, "-m", "deskbench", *argv],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=120,
        )

    def test_custom_environment_and_size_are_applied(self):
        result = self.cli("exec", self.desktop, "--", "env")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("ADAPTER_MARKER=from-manifest", result.stdout)
        self.assertIn("ADAPTER_SIZE=800x600", result.stdout)

        result = self.cli("exec", self.desktop, "--", "id", "-u")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "1000")

    def test_default_screenshot_still_works(self):
        handle, path = tempfile.mkstemp(prefix="deskbench-adapter-", suffix=".png")
        os.close(handle)
        self.addCleanup(lambda: os.path.exists(path) and os.unlink(path))
        code, out, err = call("shot", self.desktop, "-o", path)
        self.assertEqual(code, 0, err)
        self.assertEqual(out.strip(), path)
        with open(path, "rb") as stream:
            self.assertEqual(stream.read(8), b"\x89PNG\r\n\x1a\n")
        self.assertGreater(os.path.getsize(path), 8)

    def test_effective_configuration_is_stored_as_labels(self):
        result = subprocess.run(
            ["podman", "inspect", "--format", "{{json .Config.Labels}}",
             self.created["id"]],
            capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        labels = json.loads(result.stdout)
        self.assertEqual(labels["deskbench"], "1")
        self.assertEqual(labels["deskbench.viewer.port"], "3000")
        self.assertEqual(labels["deskbench.viewer.path"], "/")
        self.assertEqual(labels["deskbench.viewer.scheme"], "http")
        self.assertEqual(labels["deskbench.run.user"], "1000:1000")


class Listing(unittest.TestCase):
    """``ls`` and ``exec`` read the container labels, and older containers keep working."""

    runtime = runtimes.Runtime(name="podman", binary="podman")

    def desktops(self, labels: dict[str, str] | None) -> list[engine.Desktop]:
        item = {
            "Names": ["deskbench-alpha"],
            "State": "running",
            "Id": "abc",
            "Ports": [
                {"host_ip": "127.0.0.1", "container_port": 6080,
                 "host_port": 41234, "protocol": "tcp"},
            ],
        }
        if labels is not None:
            item["Labels"] = labels
        proc = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=json.dumps([item]), stderr="",
        )
        with mock.patch.object(engine, "_podman", return_value=proc), \
                mock.patch.object(engine.runtimes, "detect", return_value=self.runtime):
            return engine.list_desktops()

    def test_a_container_without_labels_keeps_the_default_url(self):
        desktop = self.desktops(None)[0]
        self.assertEqual(
            desktop.url,
            "http://127.0.0.1:41234/vnc.html?autoconnect=1&resize=scale",
        )
        self.assertEqual(desktop.labels, {})

    def test_labels_decide_the_url(self):
        desktop = self.desktops({
            "deskbench.viewer.port": "6080",
            "deskbench.viewer.path": "/desk/",
            "deskbench.viewer.scheme": "https",
        })[0]
        self.assertEqual(desktop.url, "https://127.0.0.1:41234/desk/")

    def exec_args(self, labels: dict[str, str]) -> list[str]:
        desktop = engine.Desktop(
            name="alpha", container="deskbench-alpha", state="running",
            url="", id="abc", labels=labels,
        )
        ok = subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")
        with mock.patch.object(engine, "get", return_value=desktop), \
                mock.patch.object(engine, "_podman", return_value=ok) as podman:
            self.assertEqual(engine.exec_in("alpha", ["id", "-u"]), 0)
        return podman.call_args.args[0]

    def test_exec_uses_the_labelled_user(self):
        self.assertEqual(
            self.exec_args({"deskbench.run.user": "1234:5678"}),
            ["exec", "--user", "1234:5678", "deskbench-alpha", "sh", "-lc", "id -u"],
        )

    def test_exec_without_a_label_uses_the_container_default(self):
        self.assertEqual(
            self.exec_args({}),
            ["exec", "deskbench-alpha", "sh", "-lc", "id -u"],
        )


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
        flavour = flavours.Flavour(name="demo", summary="", image=self.image, source="image")
        runtime = runtimes.Runtime(name="podman", binary="podman")
        ok = subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")
        with mock.patch.object(engine, "image_exists", return_value=True), \
                mock.patch.object(engine, "_podman", return_value=ok) as podman, \
                mock.patch.object(engine.runtimes, "detect", return_value=runtime), \
                mock.patch.object(engine, "get", return_value=desktop), \
                mock.patch.object(engine, "wait_ready", return_value=desktop):
            created = engine.create("demo", "800x600", flavour)

        self.assertIs(created, desktop)
        self.assertTrue(podman.called)
        for invocation in podman.call_args_list:
            self.assertNotIn("build", invocation.args[0])


class CommandLine(unittest.TestCase):
    """The manifest reaches the runtime as the right flags, and nothing else."""

    image = BASE_IMAGE

    def run_args(self, flavour: flavours.Flavour, size: str = "800x600") -> list[str]:
        desktop = engine.Desktop(
            name="demo",
            container="deskbench-demo",
            state="running",
            url="http://127.0.0.1:3000/",
            id="abc",
        )
        runtime = runtimes.Runtime(name="podman", binary="podman")
        ok = subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")
        with mock.patch.object(engine, "image_exists", return_value=True), \
                mock.patch.object(engine, "_podman", return_value=ok) as podman, \
                mock.patch.object(engine.runtimes, "detect", return_value=runtime), \
                mock.patch.object(engine, "get", return_value=desktop), \
                mock.patch.object(engine, "wait_ready", return_value=desktop):
            engine.create("demo", size, flavour)
        return podman.call_args_list[0].args[0]

    def test_the_viewer_port_and_contract_become_flags_and_labels(self):
        flavour = flavours.Flavour(
            name="adapter",
            summary="",
            image=self.image,
            source="user",
            viewer=flavours.Viewer(port=3000, path="/desk/", scheme="https", timeout=5),
        )
        args = self.run_args(flavour)
        self.assertEqual(args[:2], ["run", "-d"])
        self.assertIn("127.0.0.1::3000", args)
        self.assertNotIn("127.0.0.1::6080", args)
        for label in (
            "deskbench.viewer.port=3000",
            "deskbench.viewer.path=/desk/",
            "deskbench.viewer.scheme=https",
            "deskbench.run.user=1000:1000",
        ):
            with self.subTest(label=label):
                self.assertIn(label, args)
        self.assertEqual(args[-1], self.image)

    def test_entrypoint_and_command_follow_the_image(self):
        flavour = flavours.Flavour(
            name="adapter",
            summary="",
            image=self.image,
            source="user",
            run=flavours.Run(entrypoint=("/bin/init", "--fast"), command=("serve", "3000")),
            screenshot=flavours.Screenshot(command=("/usr/bin/shot", "{output}")),
        )
        args = self.run_args(flavour)
        entrypoint = args.index("--entrypoint")
        self.assertEqual(args[entrypoint + 1], "/bin/init")
        # The label is before the image; entrypoint arguments and the command follow it.
        self.assertEqual(args[-4:], [self.image, "--fast", "serve", "3000"])

    def test_a_user_screenshot_command_becomes_a_compact_label(self):
        command = ("/usr/local/bin/adapter-shot", "{output}")
        flavour = flavours.Flavour(
            name="adapter",
            summary="",
            image=self.image,
            source="user",
            screenshot=flavours.Screenshot(command=command, settle=False),
        )
        expected = "deskbench.screenshot=" + json.dumps(
            {"command": list(command), "settle": False}, separators=(",", ":"),
        )
        self.assertIn(expected, self.run_args(flavour))

    def test_a_screenshot_command_without_settle_is_labelled_as_settled(self):
        command = ("/usr/bin/shot", "{output}")
        flavour = flavours.Flavour(
            name="adapter",
            summary="",
            image=self.image,
            source="user",
            screenshot=flavours.Screenshot(command=command),
        )
        expected = "deskbench.screenshot=" + json.dumps(
            {"command": list(command), "settle": True}, separators=(",", ":"),
        )
        self.assertIn(expected, self.run_args(flavour))

    def test_a_builtin_screenshot_command_is_labelled_with_settle_false(self):
        command = ("/usr/local/bin/deskbench-capture", "{output}", "{settle}")
        flavour = flavours.Flavour(
            name="base",
            summary="",
            image=self.image,
            source="builtin",
            screenshot=flavours.Screenshot(command=command, settle=False),
        )
        expected = "deskbench.screenshot=" + json.dumps(
            {"command": list(command), "settle": False}, separators=(",", ":"),
        )
        self.assertIn(expected, self.run_args(flavour))

    def test_a_flavour_without_a_screenshot_command_omits_the_label(self):
        flavour = flavours.Flavour(
            name="adapter", summary="", image=self.image, source="user",
        )
        args = self.run_args(flavour)
        self.assertFalse(
            [value for value in args if value.startswith("deskbench.screenshot=")],
            "a command-less flavour must let shot resolve the image's own tool",
        )

    def test_command_alone_needs_no_entrypoint(self):
        flavour = flavours.Flavour(
            name="adapter", summary="", image=self.image, source="user",
            run=flavours.Run(command=("serve",)),
        )
        args = self.run_args(flavour)
        self.assertNotIn("--entrypoint", args)
        self.assertEqual(args[-2:], [self.image, "serve"])

    def test_environment_substitutes_the_size(self):
        flavour = flavours.Flavour(
            name="adapter",
            summary="",
            image=self.image,
            source="user",
            run=flavours.Run(env={
                "ADAPTER_MARKER": "from-manifest",
                "ADAPTER_SIZE": "{width}x{height}",
                "NOT_A_PLACEHOLDER": "a{other}",
            }),
        )
        args = self.run_args(flavour, size="1024x768")
        environment = [args[index + 1] for index, item in enumerate(args[:-1])
                       if item == "-e"]
        self.assertIn("DESKBENCH_SIZE=1024x768", environment)
        self.assertIn("ADAPTER_MARKER=from-manifest", environment)
        self.assertIn("ADAPTER_SIZE=1024x768", environment)
        self.assertIn("NOT_A_PLACEHOLDER=a{other}", environment)

    def test_a_manifest_can_override_the_size_variable(self):
        flavour = flavours.Flavour(
            name="adapter",
            summary="",
            image=self.image,
            source="user",
            run=flavours.Run(env={"DESKBENCH_SIZE": "{width}:{height}"}),
        )
        args = self.run_args(flavour, size="640x480")
        sizes = [args[index + 1] for index, item in enumerate(args[:-1])
                 if item == "-e" and args[index + 1].startswith("DESKBENCH_SIZE=")]
        self.assertEqual(sizes[-1], "DESKBENCH_SIZE=640:480")


class ContractProbe(unittest.TestCase):
    """``new`` refuses a desktop whose shell cannot run a command, and cleans it up."""

    image = BASE_IMAGE

    def create(self, shell_returns: int) -> tuple[engine.EngineError, mock.Mock]:
        desktop = engine.Desktop(
            name="demo",
            container="deskbench-demo",
            state="running",
            url="http://127.0.0.1:6080/",
            id="abc",
        )
        runtime = runtimes.Runtime(name="podman", binary="podman")

        def podman(args, **kwargs):
            return subprocess.CompletedProcess(
                args=args,
                returncode=shell_returns if args[0] == "exec" else 0,
                stdout="",
                stderr="",
            )

        with mock.patch.object(engine, "image_exists", return_value=True), \
                mock.patch.object(engine, "_podman", side_effect=podman) as call_mock, \
                mock.patch.object(engine.runtimes, "detect", return_value=runtime), \
                mock.patch.object(engine, "get", return_value=desktop), \
                mock.patch.object(engine, "wait_ready", return_value=desktop):
            with self.assertRaises(engine.EngineError) as caught:
                engine.create("demo", "800x600", flavours.adhoc(self.image))
        return caught.exception, call_mock

    def test_a_missing_shell_is_an_error_naming_the_flavour(self):
        error, _ = self.create(shell_returns=127)
        self.assertIn("image", str(error))
        self.assertIn("'sh'", str(error))

    def test_the_shell_probe_runs_as_the_configured_user(self):
        _, calls = self.create(shell_returns=127)
        probe = [entry.args[0] for entry in calls.call_args_list if entry.args[0][0] == "exec"]
        self.assertEqual(
            probe,
            [["exec", "--user", "1000:1000", "deskbench-demo", "sh", "-lc", "true"]],
        )

    def test_a_failed_new_leaves_no_container(self):
        _, calls = self.create(shell_returns=127)
        invocations = [entry.args[0] for entry in calls.call_args_list]
        self.assertIn(["stop", "--time", "2", "deskbench-demo"], invocations)

    def test_a_shell_less_viewer_timeout_also_cleans_up(self):
        desktop = engine.Desktop(
            name="demo", container="deskbench-demo", state="running", url="", id="abc",
        )
        runtime = runtimes.Runtime(name="podman", binary="podman")
        ok = subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")
        with mock.patch.object(engine, "image_exists", return_value=True), \
                mock.patch.object(engine, "_podman", return_value=ok) as calls, \
                mock.patch.object(engine.runtimes, "detect", return_value=runtime), \
                mock.patch.object(engine, "get", return_value=desktop), \
                mock.patch.object(engine, "wait_ready",
                                  side_effect=engine.EngineError("no viewer")):
            with self.assertRaises(engine.EngineError):
                engine.create("demo", "800x600", flavours.adhoc(self.image))
        invocations = [entry.args[0] for entry in calls.call_args_list]
        self.assertIn(["stop", "--time", "2", "deskbench-demo"], invocations)

    def test_a_failing_screenshot_command_is_an_error_naming_the_capability(self):
        flavour = flavours.Flavour(
            name="bad-shot", summary="", image=self.image, source="user",
            screenshot=flavours.Screenshot(
                command=("/bin/false", "{output}"), settle=False,
            ),
        )
        desktop = engine.Desktop(
            name="demo", container="deskbench-demo", state="running",
            url="http://127.0.0.1:6080/", id="abc",
        )
        runtime = runtimes.Runtime(name="podman", binary="podman")
        ok = subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")
        failed = subprocess.CompletedProcess(
            args=[], returncode=1, stdout="", stderr="capture broke",
        )

        def podman(args, **kwargs):
            if args[0] == "exec" and args[-1] == "true":
                return ok
            if args[0] == "exec":
                return failed
            return ok

        with mock.patch.object(engine, "image_exists", return_value=True), \
                mock.patch.object(engine, "_podman", side_effect=podman) as calls, \
                mock.patch.object(engine.runtimes, "detect", return_value=runtime), \
                mock.patch.object(engine, "get", return_value=desktop), \
                mock.patch.object(engine, "wait_ready", return_value=desktop), \
                mock.patch.object(engine.time, "sleep"):
            with self.assertRaises(engine.EngineError) as caught:
                engine.create("demo", "800x600", flavour)

        message = str(caught.exception)
        self.assertIn("bad-shot", message)
        self.assertIn("screenshot", message)
        self.assertIn("capture broke", message)
        invocations = [entry.args[0] for entry in calls.call_args_list]
        self.assertIn(["stop", "--time", "2", "deskbench-demo"], invocations)
        attempts = [
            invocation for invocation in invocations
            if invocation[0] == "exec" and invocation[-1] != "true"
        ]
        self.assertEqual(len(attempts), 3, "the probe should retry before refusing")

    def test_a_flavour_with_no_known_tool_is_refused_and_cleaned_up(self):
        desktop = engine.Desktop(
            name="demo", container="deskbench-demo", state="running",
            url="http://127.0.0.1:6080/", id="abc",
        )
        runtime = runtimes.Runtime(name="podman", binary="podman")
        ok = subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")
        missing = subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr="")

        def podman(args, **kwargs):
            if args[0] == "exec" and args[-1] == "true":
                return ok
            if args[0] == "exec" and args[-1].startswith("command -v"):
                return missing
            return ok

        with mock.patch.object(engine, "image_exists", return_value=True), \
                mock.patch.object(engine, "_podman", side_effect=podman) as calls, \
                mock.patch.object(engine.runtimes, "detect", return_value=runtime), \
                mock.patch.object(engine, "get", return_value=desktop), \
                mock.patch.object(engine, "wait_ready", return_value=desktop):
            with self.assertRaises(engine.EngineError) as caught:
                engine.create("demo", "800x600", flavours.adhoc(self.image))

        message = str(caught.exception)
        self.assertIn("image", message)
        self.assertIn("screenshot", message)
        self.assertIn("[screenshot].command", message)
        invocations = [entry.args[0] for entry in calls.call_args_list]
        self.assertIn(["stop", "--time", "2", "deskbench-demo"], invocations)

        probes = [
            invocation for invocation in invocations
            if invocation[0] == "exec" and invocation[-1].startswith("command -v")
        ]
        self.assertEqual(
            [probe[-1] for probe in probes],
            ["command -v deskbench-capture", "command -v scrot", "command -v import"],
        )


class ScreenshotCommand(unittest.TestCase):
    """Placeholder substitution, the tool fallback chain and the label contract."""

    desktop = engine.Desktop(
        name="demo", container="deskbench-demo", state="running", url="", id="abc",
    )

    def test_placeholders_are_substituted_and_other_text_survives(self):
        self.assertEqual(
            engine._substitute_capture(
                ("tool", "{output}", "{settle}", "a{other}"), "/tmp/x.png", 250,
            ),
            ["tool", "/tmp/x.png", "250", "a{other}"],
        )

    def test_a_configured_command_wins_without_probing(self):
        with mock.patch.object(engine, "_podman") as podman:
            resolved = engine._resolve_screenshot(
                self.desktop,
                flavours.Screenshot(command=("tool", "{output}"), settle=False),
                "1000:1000",
            )
        self.assertEqual(resolved, (("tool", "{output}"), False))
        podman.assert_not_called()

    def test_the_fallback_chain_returns_the_first_tool_found(self):
        ok = subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")
        missing = subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr="")

        def podman(args, **kwargs):
            return ok if args[-1] == "command -v scrot" else missing

        with mock.patch.object(engine, "_podman", side_effect=podman) as calls:
            resolved = engine._resolve_screenshot(self.desktop, None, "1000:1000")
        self.assertEqual(resolved, (("scrot", "-o", "{output}"), True))
        self.assertEqual(
            [call.args[0][-1] for call in calls.call_args_list],
            ["command -v deskbench-capture", "command -v scrot"],
        )


class Settle(unittest.TestCase):
    """``shot`` with settle stops at two identical frames and is bounded when it never does."""

    desktop = engine.Desktop(
        name="demo",
        container="deskbench-demo",
        state="running",
        url="",
        id="abc",
        labels={"deskbench.run.user": "1000:1000"},
    )

    def run_shot(self, frames: list[bytes]) -> tuple[bytes, dict[str, int], list[Path], str]:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = Path(directory.name)
        destination = root / "out.png"
        created: list[Path] = []

        def mkstemp(**kwargs):
            path = root / f"frame-{len(created)}.png"
            fd = os.open(path, os.O_CREAT | os.O_WRONLY | os.O_TRUNC)
            created.append(path)
            return fd, str(path)

        state = {"captures": 0, "copies": 0}
        ok = subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")
        label = json.dumps({"command": ["/usr/bin/shot", "{output}"], "settle": True})

        def podman(args, **kwargs):
            if args[0] == "inspect":
                return subprocess.CompletedProcess(
                    args=args, returncode=0, stdout=label, stderr="",
                )
            if args[0] == "exec":
                state["captures"] += 1
                return ok
            if args[0] == "cp":
                Path(args[2]).write_bytes(frames[state["copies"]])
                state["copies"] += 1
                return ok
            return ok

        err = io.StringIO()
        with mock.patch.object(engine, "get", return_value=self.desktop), \
                mock.patch.object(engine, "_podman", side_effect=podman), \
                mock.patch.object(engine.tempfile, "mkstemp", side_effect=mkstemp), \
                mock.patch.object(engine.time, "sleep"), \
                contextlib.redirect_stderr(err):
            result = engine.shot("demo", destination, settle_ms=1)
        self.assertEqual(result, destination)
        return destination.read_bytes(), state, created, err.getvalue()

    def test_two_identical_frames_end_the_loop(self):
        data, state, created, err = self.run_shot([b"a", b"b", b"b"])
        self.assertEqual(data, b"b")
        self.assertEqual(state["captures"], 3)
        self.assertEqual(err, "")
        for frame in created:
            self.assertFalse(frame.exists(), "host frames must be cleaned up")

    def test_a_screen_that_never_settles_is_bounded_and_warns(self):
        frames = [bytes([index]) for index in range(10)]
        data, state, created, err = self.run_shot(frames)
        self.assertEqual(data, frames[-1])
        self.assertEqual(state["captures"], 10)
        self.assertIn("did not settle", err)
        for frame in created:
            self.assertFalse(frame.exists(), "host frames must be cleaned up")


class AdapterScreenshot(unittest.TestCase):
    """A third-party image's own screenshot command, its failure, and the built-in fallback."""

    desktop = "e2e-adapter-shot"
    fallback_desktop = "e2e-adapter-fallback"
    bad_desktop = "e2e-adapter-bad"
    flavour = "adapter-shot"
    fallback_flavour = "adapter-fallback"
    bad_flavour = "adapter-bad"

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
        if not engine.image_exists(ADAPTER_IMAGE):
            try:
                subprocess.run(
                    ["podman", "build", "-t", ADAPTER_IMAGE, "tests/fixtures/adapter"],
                    cwd=REPO_ROOT,
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=600,
                )
            except subprocess.CalledProcessError as exc:
                raise unittest.SkipTest(
                    f"could not build the adapter fixture: {exc.stderr.strip()}"
                ) from exc

        cls._tempdir = tempfile.TemporaryDirectory()
        directory = Path(cls._tempdir.name)
        manifests = {
            cls.flavour: ADAPTER_SCREENSHOT_MANIFEST,
            cls.bad_flavour: ADAPTER_BAD_SCREENSHOT_MANIFEST,
            cls.fallback_flavour: (
                f'image = "{cls.base_image}"\nsummary = "Base image with the fallback"\n'
            ),
        }
        for name, body in manifests.items():
            (directory / name).mkdir()
            (directory / name / "flavour.toml").write_text(body, encoding="utf-8")

        cls._env = mock.patch.dict(
            os.environ, {"DESKBENCH_FLAVOURS_DIR": str(directory)}
        )
        cls._env.start()
        try:
            for name in (cls.desktop, cls.fallback_desktop, cls.bad_desktop):
                call("stop", name)
            code, out, err = call(
                "new", "--name", cls.desktop, "--size", "800x600",
                "--flavour", cls.flavour,
            )
            if code != 0:
                raise unittest.SkipTest(
                    f"could not start {cls.desktop}: {err.strip() or out.strip()}"
                )
            cls.created = json.loads(out)

            code, out, err = call(
                "new", "--name", cls.fallback_desktop, "--size", "800x600",
                "--flavour", cls.fallback_flavour,
            )
            if code != 0:
                raise unittest.SkipTest(
                    f"could not start {cls.fallback_desktop}: "
                    f"{err.strip() or out.strip()}"
                )
            cls.fallback_created = json.loads(out)
        except BaseException:
            cls._cleanup()
            raise

    @classmethod
    def _cleanup(cls) -> None:
        for name in (cls.desktop, cls.fallback_desktop, cls.bad_desktop):
            call("stop", name)
        cls._tempdir.cleanup()
        cls._env.stop()

    @classmethod
    def tearDownClass(cls) -> None:
        cls._cleanup()

    def shot(self, desktop: str) -> Path:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        destination = Path(directory.name) / "shot.png"
        code, out, err = call("shot", desktop, "-o", str(destination))
        self.assertEqual(code, 0, err)
        self.assertEqual(out.strip(), str(destination))
        data = destination.read_bytes()
        self.assertEqual(data[:8], b"\x89PNG\r\n\x1a\n")
        self.assertGreater(len(data), 8)
        return destination

    def labels(self, container_id: str) -> dict[str, str]:
        result = subprocess.run(
            ["podman", "inspect", "--format", "{{json .Config.Labels}}", container_id],
            capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_custom_screenshot_command(self):
        self.shot(self.desktop)
        labels = self.labels(self.created["id"])
        self.assertEqual(
            json.loads(labels["deskbench.screenshot"]),
            {
                "command": ["/usr/local/bin/adapter-shot", "{output}"],
                "settle": False,
            },
        )

    def test_unviable_screenshot_command_is_refused(self):
        code, out, err = call(
            "new", "--name", self.bad_desktop, "--size", "800x600",
            "--flavour", self.bad_flavour,
        )
        self.assertEqual(code, 1)
        self.assertEqual(out.strip(), "", "a failed new must not print a desktop JSON")
        self.assertIn(self.bad_flavour, err)
        self.assertIn("screenshot", err)

        code, out, err = call("ls", "--json")
        self.assertEqual(code, 0, err)
        names = {row["name"] for row in json.loads(out)}
        self.assertNotIn(self.bad_desktop, names)

        result = subprocess.run(
            ["podman", "container", "exists", f"deskbench-{self.bad_desktop}"],
            capture_output=True, text=True, timeout=30,
        )
        self.assertNotEqual(result.returncode, 0, "a refused desktop left a container behind")

    def test_default_capture_helper_is_the_fallback(self):
        self.shot(self.fallback_desktop)
        labels = self.labels(self.fallback_created["id"])
        self.assertNotIn("deskbench.screenshot", labels)


if __name__ == "__main__":
    unittest.main()
