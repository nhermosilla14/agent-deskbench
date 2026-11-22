"""The flavour registry must match the Dockerfiles actually shipped."""

from __future__ import annotations

import unittest

from deskbench import flavours


class Registry(unittest.TestCase):
    def test_every_flavour_has_a_dockerfile(self):
        for name in flavours.names():
            with self.subTest(flavour=name):
                self.assertTrue(flavours.get(name).dockerfile.is_file(),
                                f"{name} points at a missing Dockerfile")

    def test_derived_flavours_build_on_the_base_tag(self):
        for name in flavours.names():
            if name == "base":
                continue
            with self.subTest(flavour=name):
                text = flavours.get(name).dockerfile.read_text()
                self.assertIn(flavours.base_tag(), text,
                              "a flavour must default its BASE argument to the base tag")

    def test_tags_are_distinct(self):
        tags = [flavours.tag_for(name) for name in flavours.names()]
        self.assertEqual(len(tags), len(set(tags)))

    def test_unknown_flavour_lists_the_valid_ones(self):
        with self.assertRaises(flavours.UnknownFlavour) as caught:
            flavours.get("netscape")
        for name in flavours.names():
            self.assertIn(name, str(caught.exception))

    def test_chromium_wrapper_keeps_the_sandbox(self):
        text = flavours.get("chromium").dockerfile.read_text()
        self.assertNotIn("--no-sandbox", text,
                         "the renderer sandbox must stay on now that we run unprivileged")

    def test_base_is_the_default(self):
        self.assertIn("base", flavours.names())
        self.assertEqual(flavours.tag_for("base"), flavours.base_tag())


if __name__ == "__main__":
    unittest.main()
