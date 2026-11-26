"""The built-in flavours are image references, not local build recipes."""

from __future__ import annotations

import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from deskbench import cli, flavours

DIGEST = "sha256:" + "a" * 64
IMAGE = "localhost/example/desktop:1"


@contextlib.contextmanager
def registry_env(value: str | None):
    """Run with ``DESKBENCH_REGISTRY`` set to ``value`` (or removed when ``None``).

    The flavour directory is pointed at a path that does not exist, so a developer's real
    ``~/.config/agent-deskbench/flavours`` cannot shadow a built-in during these tests.
    """
    env = {key: item for key, item in os.environ.items() if key != "DESKBENCH_REGISTRY"}
    env["DESKBENCH_FLAVOURS_DIR"] = "/nonexistent/deskbench-test-flavours"
    if value is not None:
        env["DESKBENCH_REGISTRY"] = value
    with mock.patch.dict(os.environ, env, clear=True):
        yield


@contextlib.contextmanager
def location_env(**values: str):
    """Run with only ``values`` deciding the flavour directory location."""
    keys = ("DESKBENCH_FLAVOURS_DIR", "XDG_CONFIG_HOME", "HOME")
    env = {key: item for key, item in os.environ.items() if key not in keys}
    env.update(values)
    with mock.patch.dict(os.environ, env, clear=True):
        yield


def write_manifest(root: Path, name: str, body: str) -> Path:
    """Create ``<root>/<name>/flavour.toml`` and return the manifest path."""
    directory = root / name
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "flavour.toml"
    path.write_text(body, encoding="utf-8")
    return path


class Registry(unittest.TestCase):
    def test_builtin_names_are_the_three_supported_flavours(self):
        self.assertEqual(flavours.names(), ["base", "chromium", "firefox"])

    def test_builtins_resolve_to_the_default_registry(self):
        with registry_env(None):
            self.assertEqual(
                flavours.get("base").image,
                "ghcr.io/nhermosilla14/agent-deskbench/desktop:1",
            )
            self.assertEqual(
                flavours.get("firefox").image,
                "ghcr.io/nhermosilla14/agent-deskbench/desktop-firefox:1",
            )
            self.assertEqual(
                flavours.get("chromium").image,
                "ghcr.io/nhermosilla14/agent-deskbench/desktop-chromium:1",
            )

    def test_every_builtin_has_a_summary_and_is_a_builtin_source(self):
        with registry_env(None):
            for name in flavours.names():
                with self.subTest(flavour=name):
                    flavour = flavours.get(name)
                    self.assertEqual(flavour.name, name)
                    self.assertTrue(flavour.summary)
                    self.assertEqual(flavour.source, "builtin")

    def test_no_builtin_exposes_a_dockerfile_path(self):
        with registry_env(None):
            for name in flavours.names():
                with self.subTest(flavour=name):
                    flavour = flavours.get(name)
                    self.assertFalse(hasattr(flavour, "dockerfile"))
                    self.assertFalse(hasattr(flavour, "base"))

    def test_registry_override_is_read_at_call_time(self):
        with registry_env("example.com/team"):
            self.assertEqual(
                flavours.get("firefox").image,
                "example.com/team/desktop-firefox:1",
            )
            with registry_env("localhost:5000/other"):
                self.assertEqual(
                    flavours.get("chromium").image,
                    "localhost:5000/other/desktop-chromium:1",
                )

    def test_trailing_slashes_are_stripped(self):
        with registry_env("localhost/agent-deskbench///"):
            self.assertEqual(flavours.registry(), "localhost/agent-deskbench")
            self.assertEqual(
                flavours.get("base").image,
                "localhost/agent-deskbench/desktop:1",
            )

    def test_blank_registry_is_a_configuration_error(self):
        with registry_env("   "):
            with self.assertRaises(flavours.FlavourConfigError) as caught:
                flavours.registry()
        self.assertIn("DESKBENCH_REGISTRY", str(caught.exception))
        self.assertIn("blank", str(caught.exception))

    def test_unknown_flavour_lists_the_valid_ones(self):
        with self.assertRaises(flavours.UnknownFlavour) as caught:
            flavours.get("netscape")
        for name in flavours.names():
            self.assertIn(name, str(caught.exception))


class Validation(unittest.TestCase):
    def test_fully_qualified_references_are_accepted(self):
        accepted = (
            "ghcr.io/nhermosilla14/agent-deskbench/desktop:1",
            "docker.io/library/debian:12",
            "localhost:5000/foo:1",
            f"registry.example.com/a/b@sha256:{'f' * 64}",
            f"registry.example.com/a/b:1@sha256:{'0' * 64}",
        )
        for value in accepted:
            with self.subTest(value=value):
                self.assertEqual(flavours.validate_image_ref(value), value)

    def test_short_names_and_missing_tags_are_rejected(self):
        rejected = (
            "",
            "   ",
            "debian:12",
            "ghcr.io/foo",
            "ghcr.io/foo:",
            "ghcr.io/:1",
            "ghcr.io/foo:bad tag",
            " ghcr.io/foo:1",
            "ghcr.io/foo:1 ",
            "ghcr.io/foo@sha256:abc",
            f"ghcr.io/foo@sha512:{'a' * 64}",
            f"ghcr.io/foo@sha256:{'A' * 64}",
            "ghcr.io/foo:tag!",
        )
        for value in rejected:
            with self.subTest(value=value):
                with self.assertRaises(flavours.InvalidImage) as caught:
                    flavours.validate_image_ref(value)
                self.assertIn(flavours.EXAMPLE_IMAGE, str(caught.exception))

    def test_digest_reference_is_accepted_without_a_tag(self):
        value = f"registry.example.com/a/b@sha256:{DIGEST.split(':', 1)[1]}"
        self.assertEqual(flavours.validate_image_ref(value), value)


class Location(unittest.TestCase):
    """Where user flavours are looked for; no directory has to exist."""

    def test_explicit_directory_beats_xdg_and_home(self):
        with location_env(
            DESKBENCH_FLAVOURS_DIR="/srv/flavours",
            XDG_CONFIG_HOME="/xdg",
            HOME="/home/demo",
        ):
            self.assertEqual(flavours.flavours_dir(), Path("/srv/flavours"))

    def test_xdg_beats_the_home_default(self):
        with location_env(XDG_CONFIG_HOME="/xdg", HOME="/home/demo"):
            self.assertEqual(
                flavours.flavours_dir(), Path("/xdg/agent-deskbench/flavours")
            )

    def test_home_default_when_nothing_is_set(self):
        with location_env(HOME="/home/demo"):
            self.assertEqual(
                flavours.flavours_dir(),
                Path("/home/demo/.config/agent-deskbench/flavours"),
            )

    def test_tilde_is_expanded(self):
        with location_env(DESKBENCH_FLAVOURS_DIR="~/flavours", HOME="/home/demo"):
            self.assertEqual(flavours.flavours_dir(), Path("/home/demo/flavours"))

    def test_blank_override_is_a_configuration_error(self):
        with location_env(DESKBENCH_FLAVOURS_DIR="   "):
            with self.assertRaises(flavours.FlavourConfigError) as caught:
                flavours.flavours_dir()
        self.assertIn("DESKBENCH_FLAVOURS_DIR", str(caught.exception))
        self.assertIn("blank", str(caught.exception))

    def test_manifest_path_hangs_off_the_flavours_directory(self):
        with location_env(DESKBENCH_FLAVOURS_DIR="/srv/flavours"):
            self.assertEqual(
                flavours.manifest_path("custom"),
                Path("/srv/flavours/custom/flavour.toml"),
            )


class Discovery(unittest.TestCase):
    """A user flavour is a directory with a manifest; bad candidates are reported, not fatal."""

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        env = mock.patch.dict(
            os.environ, {"DESKBENCH_FLAVOURS_DIR": str(self.root)}
        )
        env.start()
        self.addCleanup(env.stop)

    def test_valid_manifest_is_a_user_flavour(self):
        write_manifest(
            self.root, "custom", f'image = "{IMAGE}"\nsummary = "My custom desktop"\n'
        )
        discovery = flavours.discover()
        self.assertEqual(discovery.problems, [])
        found = {flavour.name: flavour for flavour in discovery.flavours}
        self.assertEqual(set(found), set(flavours.names()) | {"custom"})
        self.assertEqual(found["custom"].source, "user")
        self.assertEqual(found["custom"].image, IMAGE)
        self.assertEqual(found["custom"].summary, "My custom desktop")
        self.assertEqual(
            [flavour.name for flavour in discovery.flavours],
            ["base", "chromium", "custom", "firefox"],
        )

    def test_summary_defaults_when_absent(self):
        write_manifest(self.root, "custom", f'image = "{IMAGE}"\n')
        found = {flavour.name: flavour for flavour in flavours.discover().flavours}
        self.assertEqual(found["custom"].summary, flavours.USER_SUMMARY)

    def test_invalid_directory_name_is_a_problem(self):
        manifest = write_manifest(self.root, "Bad_Name", f'image = "{IMAGE}"\n')
        discovery = flavours.discover()
        self.assertEqual(
            [(problem.path, "invalid flavour name" in problem.message)
             for problem in discovery.problems],
            [(manifest, True)],
        )
        self.assertNotIn("Bad_Name", {flavour.name for flavour in discovery.flavours})

    def test_malformed_toml_is_a_problem_and_other_flavours_survive(self):
        write_manifest(self.root, "custom", f'image = "{IMAGE}"\n')
        broken = write_manifest(self.root, "broken", "image = \n")
        discovery = flavours.discover()
        self.assertEqual([problem.path for problem in discovery.problems], [broken])
        self.assertIn("invalid TOML", discovery.problems[0].message)
        self.assertIn("custom", {flavour.name for flavour in discovery.flavours})

    def test_missing_image_is_a_problem(self):
        write_manifest(self.root, "broken", 'summary = "no image here"\n')
        problem = flavours.discover().problems[0]
        self.assertIn("image", problem.message)
        self.assertEqual(problem.path, self.root / "broken" / "flavour.toml")

    def test_invalid_image_reference_is_a_problem(self):
        write_manifest(self.root, "broken", 'image = "debian:12"\n')
        problem = flavours.discover().problems[0]
        self.assertIn("fully qualified", problem.message)

    def test_unknown_key_is_a_problem(self):
        write_manifest(
            self.root, "broken", f'image = "{IMAGE}"\ncolour = "never"\n'
        )
        problem = flavours.discover().problems[0]
        self.assertIn("unknown key", problem.message)
        self.assertIn("colour", problem.message)

    def test_non_string_values_are_problems(self):
        for body in (f"image = {1}\n", f'image = "{IMAGE}"\nsummary = 1\n'):
            with self.subTest(body=body):
                write_manifest(self.root, "broken", body)
                problems = flavours.discover().problems
                self.assertEqual(len(problems), 1)
                self.assertIn("must be a string", problems[0].message)

    def test_directory_without_a_manifest_is_ignored(self):
        (self.root / "empty").mkdir()
        discovery = flavours.discover()
        self.assertEqual(discovery.problems, [])
        self.assertEqual(
            [flavour.name for flavour in discovery.flavours], flavours.names()
        )

    def test_hidden_directory_is_ignored(self):
        write_manifest(self.root, ".scratch", f'image = "{IMAGE}"\n')
        discovery = flavours.discover()
        self.assertEqual(discovery.problems, [])
        self.assertEqual(
            [flavour.name for flavour in discovery.flavours], flavours.names()
        )

    def test_shadowing_a_builtin_is_a_problem_and_the_builtin_survives(self):
        manifest = write_manifest(self.root, "firefox", f'image = "{IMAGE}"\n')
        discovery = flavours.discover()
        self.assertEqual(
            [(problem.path, "shadows" in problem.message)
             for problem in discovery.problems],
            [(manifest, True)],
        )
        found = {flavour.name: flavour for flavour in discovery.flavours}
        self.assertEqual(found["firefox"].source, "builtin")
        self.assertNotEqual(found["firefox"].image, IMAGE)

    def test_get_rejects_a_shadowing_directory(self):
        manifest = write_manifest(self.root, "firefox", f'image = "{IMAGE}"\n')
        with self.assertRaises(flavours.ManifestError) as caught:
            flavours.get("firefox")
        self.assertIn(str(manifest), str(caught.exception))
        self.assertIn("shadows", str(caught.exception))

    def test_images_warns_about_shadowing_and_keeps_the_builtin(self):
        manifest = write_manifest(self.root, "firefox", f'image = "{IMAGE}"\n')
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(cli.engine, "image_exists", return_value=False), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main(["images", "--json"])
        self.assertEqual(code, 0)
        rows = {row["name"]: row for row in json.loads(out.getvalue())}
        self.assertEqual(rows["firefox"]["source"], "builtin")
        self.assertNotEqual(rows["firefox"]["image"], IMAGE)
        self.assertIn(f"deskbench: ignoring {manifest}", err.getvalue())
        self.assertIn("shadows", err.getvalue())

    def test_new_rejects_a_shadowing_directory_before_creating_a_container(self):
        manifest = write_manifest(self.root, "firefox", f'image = "{IMAGE}"\n')
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(cli.engine, "list_desktops", return_value=[]), \
                mock.patch.object(cli.engine, "create") as create, \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main(["new", "--flavour", "firefox"])
        self.assertEqual(code, 1)
        create.assert_not_called()
        self.assertEqual(out.getvalue(), "")
        self.assertIn("firefox", err.getvalue())
        self.assertIn(str(manifest), err.getvalue())
        self.assertIn("shadows", err.getvalue())

    def test_get_returns_a_user_flavour(self):
        write_manifest(self.root, "custom", f'image = "{IMAGE}"\n')
        flavour = flavours.get("custom")
        self.assertEqual(flavour.name, "custom")
        self.assertEqual(flavour.image, IMAGE)
        self.assertEqual(flavour.source, "user")
        self.assertEqual(flavour.summary, flavours.USER_SUMMARY)

    def test_get_reports_a_malformed_manifest_with_its_path(self):
        manifest = write_manifest(self.root, "broken", "image = \n")
        with self.assertRaises(flavours.ManifestError) as caught:
            flavours.get("broken")
        self.assertIn(str(manifest), str(caught.exception))
        self.assertIn("invalid TOML", str(caught.exception))

    def test_get_unknown_lists_available_names(self):
        write_manifest(self.root, "custom", f'image = "{IMAGE}"\n')
        with self.assertRaises(flavours.UnknownFlavour) as caught:
            flavours.get("missing")
        for name in (*flavours.names(), "custom"):
            self.assertIn(name, str(caught.exception))

    def test_missing_explicit_directory_is_reported(self):
        missing = self.root / "does-not-exist"
        with mock.patch.dict(
            os.environ, {"DESKBENCH_FLAVOURS_DIR": str(missing)}
        ):
            discovery = flavours.discover()
        self.assertEqual([problem.path for problem in discovery.problems], [missing])
        self.assertIn("DESKBENCH_FLAVOURS_DIR", discovery.problems[0].message)

    def test_missing_default_directory_is_silent(self):
        with location_env(HOME=str(self.root / "nobody")):
            discovery = flavours.discover()
        self.assertEqual(discovery.problems, [])
        self.assertEqual(
            [flavour.name for flavour in discovery.flavours], flavours.names()
        )


class Defaults(unittest.TestCase):
    """A flavour that says nothing about the contract behaves like the built-in image."""

    def test_viewer_defaults_reproduce_the_base_layout(self):
        viewer = flavours.Viewer()
        self.assertEqual(viewer.port, 6080)
        self.assertEqual(viewer.path, "/vnc.html?autoconnect=1&resize=scale")
        self.assertEqual(viewer.scheme, "http")
        self.assertEqual(viewer.timeout, 30)

    def test_run_defaults_reproduce_the_base_layout(self):
        run = flavours.Run()
        self.assertEqual(run.user, "1000:1000")
        self.assertEqual(run.entrypoint, ())
        self.assertEqual(run.command, ())
        self.assertEqual(run.env, {})

    def test_builtins_use_the_default_contract(self):
        with registry_env(None):
            for name in flavours.names():
                with self.subTest(flavour=name):
                    flavour = flavours.get(name)
                    self.assertEqual(flavour.viewer, flavours.Viewer())
                    self.assertEqual(flavour.run, flavours.Run())

    def test_adhoc_uses_the_default_contract(self):
        flavour = flavours.adhoc(IMAGE)
        self.assertEqual(flavour.name, "image")
        self.assertEqual(flavour.summary, "")
        self.assertEqual(flavour.image, IMAGE)
        self.assertEqual(flavour.source, "image")
        self.assertEqual(flavour.viewer, flavours.Viewer())
        self.assertEqual(flavour.run, flavours.Run())

    def test_adhoc_validates_the_reference(self):
        with self.assertRaises(flavours.InvalidImage) as caught:
            flavours.adhoc("debian:12")
        self.assertIn(flavours.EXAMPLE_IMAGE, str(caught.exception))


class Users(unittest.TestCase):
    """``run.user`` is an id pair, and a bad one is caught before the runtime sees it."""

    def test_one_part_uses_the_uid_as_gid(self):
        self.assertEqual(flavours.parse_user("1000"), (1000, 1000))
        self.assertEqual(flavours.parse_user("0"), (0, 0))

    def test_two_parts_are_used_as_given(self):
        self.assertEqual(flavours.parse_user("1234:5678"), (1234, 5678))
        self.assertEqual(flavours.parse_user("0:0"), (0, 0))
        self.assertEqual(flavours.parse_user("1000:0"), (1000, 0))

    def test_rejected_values(self):
        for value in ("", "root", "1000:abc", "abc:1000", "-1", "1000:-1",
                      "1:2:3", "1000:", ":1000", " 1000", "1000 ", "1.0",
                      "\u0661\u0660\u0660\u0660",
                      str(2**31), f"{2**31}:0", f"0:{2**31}"):
            with self.subTest(value=value), self.assertRaises(ValueError) as caught:
                flavours.parse_user(value)
            self.assertIn("invalid user", str(caught.exception))

    def test_largest_accepted_id(self):
        limit = 2**31 - 1
        self.assertEqual(flavours.parse_user(f"{limit}:{limit}"), (limit, limit))


class Schema(unittest.TestCase):
    """The manifest describes the whole contract; unknown keys and bad values are refused."""

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        env = mock.patch.dict(
            os.environ, {"DESKBENCH_FLAVOURS_DIR": str(self.root)}
        )
        env.start()
        self.addCleanup(env.stop)

    def write(self, body: str) -> None:
        write_manifest(self.root, "custom", body)

    def error(self, body: str) -> str:
        self.write(body)
        with self.assertRaises(flavours.ManifestError) as caught:
            flavours.get("custom")
        return str(caught.exception)

    def test_full_viewer_and_run_tables_are_parsed(self):
        self.write(
            f'image = "{IMAGE}"\n'
            'summary = "Custom"\n'
            "\n"
            "[viewer]\n"
            "port = 3000\n"
            'path = "/desk/"\n'
            'scheme = "https"\n'
            "timeout = 12\n"
            "\n"
            "[run]\n"
            'user = "1234:5678"\n'
            'entrypoint = ["/bin/init", "--fast"]\n'
            'command = ["serve", "3000"]\n'
            'env = { WIDTH = "{width}", HEIGHT = "{height}" }\n'
        )
        flavour = flavours.get("custom")
        self.assertEqual(flavour.viewer, flavours.Viewer(
            port=3000, path="/desk/", scheme="https", timeout=12,
        ))
        self.assertEqual(flavour.run.user, "1234:5678")
        self.assertEqual(flavour.run.entrypoint, ("/bin/init", "--fast"))
        self.assertEqual(flavour.run.command, ("serve", "3000"))
        self.assertEqual(flavour.run.env, {"WIDTH": "{width}", "HEIGHT": "{height}"})

    def test_partial_tables_keep_the_defaults(self):
        self.write(
            f'image = "{IMAGE}"\n'
            "[viewer]\n"
            "port = 3000\n"
            "[run]\n"
            'user = "0:0"\n'
        )
        flavour = flavours.get("custom")
        self.assertEqual(flavour.viewer, flavours.Viewer(port=3000))
        self.assertEqual(flavour.run, flavours.Run(user="0:0"))

    def test_unknown_keys_inside_a_table_are_refused(self):
        cases = {
            "viewer": ('[viewer]\ncolour = "blue"\n', "colour"),
            "run": ('[run]\ncwd = "/"\n', "cwd"),
            "top": ('[screenshot]\ncommand = ["x"]\n', "screenshot"),
        }
        for label, (body, key) in cases.items():
            with self.subTest(table=label):
                message = self.error(f'image = "{IMAGE}"\n{body}')
                self.assertIn("unknown key", message)
                self.assertIn(key, message)

    def test_wrong_types_are_refused(self):
        bodies = (
            'viewer = "never"\n',
            "[viewer]\nport = \"3000\"\n",
            "[viewer]\nport = 3000.5\n",
            "[viewer]\npath = 1234\n",
            "[viewer]\nscheme = 1\n",
            "[viewer]\ntimeout = \"30\"\n",
            '[run]\nuser = 1000\n',
            '[run]\nentrypoint = "/bin/sh"\n',
            '[run]\ncommand = "serve"\n',
            '[run]\nenv = "A=B"\n',
        )
        for body in bodies:
            with self.subTest(body=body):
                message = self.error(f'image = "{IMAGE}"\n{body}')
                self.assertIn("must be", message)

    def test_viewer_values_are_validated(self):
        cases = (
            ("port", "0", "between 1 and 65535"),
            ("port", "65536", "between 1 and 65535"),
            ("port", "true", "must be an integer"),
            ("port", "false", "must be an integer"),
            ("path", '""', "must not be empty"),
            ("path", '"vnc.html"', "must start with '/'"),
            ("path", '"/a b"', "must not contain whitespace"),
            ("path", '"/vnc.html?x=1 2"', "must not contain whitespace"),
            ("scheme", '"ftp"', "must be one of"),
            ("timeout", "0", "at least 1"),
            ("timeout", "-1", "at least 1"),
            ("timeout", "true", "must be an integer"),
        )
        for key, value, expected in cases:
            with self.subTest(key=key, value=value):
                message = self.error(f'image = "{IMAGE}"\n[viewer]\n{key} = {value}\n')
                self.assertIn(expected, message)

    def test_bad_run_users_are_refused(self):
        for value in ("root", "1000:abc", "1:2:3", "-1", str(2**31)):
            with self.subTest(value=value):
                message = self.error(f'image = "{IMAGE}"\n[run]\nuser = "{value}"\n')
                self.assertIn("run.user", message)

    def test_entrypoint_and_command_items_are_validated(self):
        for key in ("entrypoint", "command"):
            with self.subTest(key=key, value="empty"):
                message = self.error(f'image = "{IMAGE}"\n[run]\n{key} = [""]\n')
                self.assertIn(key, message)
                self.assertIn("must not be empty", message)
            with self.subTest(key=key, value="non-string"):
                message = self.error(f'image = "{IMAGE}"\n[run]\n{key} = [1]\n')
                self.assertIn(key, message)
                self.assertIn("must be a string", message)

    def test_env_is_validated(self):
        message = self.error(f'image = "{IMAGE}"\n[run]\nenv = {{ "A=B" = "c" }}\n')
        self.assertIn("must not contain '='", message)

        for value in ("1", "true"):
            with self.subTest(value=value):
                message = self.error(f'image = "{IMAGE}"\n[run]\nenv = {{ A = {value} }}\n')
                self.assertIn("run.env.A", message)
                self.assertIn("must be a string", message)

    def test_a_screenshot_table_is_still_unknown(self):
        message = self.error(
            f'image = "{IMAGE}"\n[screenshot]\nsettle = false\n'
        )
        self.assertIn("unknown key", message)
        self.assertIn("screenshot", message)


if __name__ == "__main__":
    unittest.main()
