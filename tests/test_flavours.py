"""The built-in flavours are image references, not local build recipes."""

from __future__ import annotations

import contextlib
import os
import unittest
from unittest import mock

from deskbench import flavours

DIGEST = "sha256:" + "a" * 64


@contextlib.contextmanager
def registry_env(value: str | None):
    """Run with ``DESKBENCH_REGISTRY`` set to ``value`` (or removed when ``None``)."""
    env = {key: item for key, item in os.environ.items() if key != "DESKBENCH_REGISTRY"}
    if value is not None:
        env["DESKBENCH_REGISTRY"] = value
    with mock.patch.dict(os.environ, env, clear=True):
        yield


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


if __name__ == "__main__":
    unittest.main()
