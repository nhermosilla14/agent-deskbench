"""The agent-facing artefacts must not drift from the CLI.

If a verb is renamed or removed, the skill is wrong and this test says so before an agent
discovers it the hard way.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import tomllib
import unittest
from pathlib import Path

from deskbench.cli import build_parser

ROOT = Path(__file__).resolve().parent.parent
SKILL = ROOT / "skill" / "SKILL.md"
PYPROJECT = ROOT / "pyproject.toml"


def frontmatter(text: str) -> dict[str, str]:
    if not text.startswith("---\n"):
        raise AssertionError("SKILL.md must start with YAML frontmatter")
    block = text.split("---\n", 2)[1]
    fields: dict[str, str] = {}
    current = None
    for line in block.splitlines():
        if not line.strip():
            continue
        if not line.startswith((" ", "\t")) and ":" in line:
            current, _, value = line.partition(":")
            fields[current.strip()] = value.strip()
        elif current and line.startswith((" ", "\t")):
            fields[current] = (fields[current] + " " + line.strip()).strip()
    return fields


class SkillFile(unittest.TestCase):
    def test_frontmatter_names_the_skill(self):
        fields = frontmatter(SKILL.read_text())
        self.assertEqual(fields.get("name"), "agent-deskbench")
        self.assertGreater(len(fields.get("description", "")), 200,
                           "the description is the trigger; it must say when to use the skill")

    def test_triggering_mentions_the_situations_that_matter(self):
        description = frontmatter(SKILL.read_text())["description"].lower()
        for phrase in ("gui", "screenshot", "display"):
            self.assertIn(phrase, description)
        self.assertIn("do not use", description, "a skill needs negative cases too")

    def test_documented_verbs_match_the_parser(self):
        documented = set(re.findall(r"^\| `([a-z]+)", SKILL.read_text(), flags=re.MULTILINE))
        parser = build_parser()
        subparsers = next(
            action for action in parser._actions if hasattr(action, "choices") and action.choices
        )
        implemented = set(subparsers.choices) - {"tray"}
        self.assertTrue(documented, "no verbs found in the skill table")
        self.assertEqual(
            documented,
            implemented,
            "the skill's verb table and the CLI parser disagree",
        )


class Packaging(unittest.TestCase):
    def test_console_script_is_declared(self):
        project = tomllib.loads(PYPROJECT.read_text())
        self.assertEqual(project["project"]["scripts"]["deskbench"], "deskbench.cli:main")

    def test_installed_command_works_if_present(self):
        if shutil.which("deskbench") is None:
            self.skipTest("deskbench is not installed; run `task install-cli`")
        result = subprocess.run(["deskbench", "--version"], capture_output=True, text=True,
                                timeout=30, cwd="/tmp")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("deskbench", result.stdout)


if __name__ == "__main__":
    unittest.main()
