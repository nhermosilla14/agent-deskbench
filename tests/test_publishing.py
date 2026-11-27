"""Publishing must derive its tags and image names from the CLI.

A release is only trustworthy if the tags the workflow pushes are the tags the CLI pulls. These
tests run the shared shell mapping, drive the local publisher with a fake ``podman``, and compare
the workflow with the built-in flavour references. No container and no network are needed.
"""

from __future__ import annotations

import os
import re
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from deskbench import flavours

ROOT = Path(__file__).resolve().parent.parent
IMAGE_TAGS = ROOT / "scripts" / "image-tags.sh"
PUBLISH_IMAGES = ROOT / "scripts" / "publish-images.sh"
WORKFLOW = ROOT / ".github" / "workflows" / "publish.yml"
TASKFILE = ROOT / "Taskfile.yml"

SAMPLE_TAGS = ("1.2.3", "1.2", "1", "latest")


def run_tags(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(IMAGE_TAGS), *args],
        capture_output=True,
        text=True,
        timeout=30,
        cwd=ROOT,
    )


class Tags(unittest.TestCase):
    """The version-to-tag mapping is shared by the workflow, the task and these tests."""

    def test_semver_mapping(self):
        result = run_tags("1.2.3")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "1.2.3\n1.2\n1\nlatest\n")

    def test_v_prefix_is_stripped(self):
        self.assertEqual(run_tags("v1.2.3").stdout, run_tags("1.2.3").stdout)

    def test_sha_adds_a_tag(self):
        result = run_tags("1.2.3", "abc1234")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "1.2.3\n1.2\n1\nlatest\nsha-abc1234\n")

    def test_invalid_versions_are_rejected(self):
        for version in ("1", "1.2", "1.2.3.4", "v", "main", "1.2.3-rc1", ""):
            with self.subTest(version=version):
                result = run_tags(version)
                self.assertEqual(result.returncode, 2)
                self.assertTrue(result.stderr.strip(), "an invalid version must explain itself")


class PublishScript(unittest.TestCase):
    """The local publisher builds once per image and then applies every tag."""

    def test_builds_tags_and_pushes_every_image(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            log = directory / "podman.log"
            podman = directory / "podman"
            podman.write_text(
                "#!/bin/sh\n"
                f'echo "$*" >> "{log}"\n'
                "exit 0\n",
                encoding="utf-8",
            )
            podman.chmod(0o755)

            env = dict(os.environ)
            env["PATH"] = f"{directory}{os.pathsep}{env.get('PATH', '')}"
            result = subprocess.run(
                [str(PUBLISH_IMAGES), "localhost/example", "1.2.3", "abc1234"],
                capture_output=True,
                text=True,
                timeout=60,
                cwd=ROOT,
                env=env,
            )
            self.assertEqual(result.returncode, 0, result.stderr)

            calls = log.read_text(encoding="utf-8").splitlines()

        for name, context in (
            ("desktop", "image"),
            ("desktop-firefox", "image/flavours/firefox"),
            ("desktop-chromium", "image/flavours/chromium"),
        ):
            with self.subTest(image=name):
                self.assertTrue(
                    any(
                        line.startswith("build ") and f"localhost/example/{name}:1.2.3" in line
                        and line.endswith(f" {context}")
                        for line in calls
                    ),
                    f"no build for {name} from {context}: {calls}",
                )

        for name in ("desktop-firefox", "desktop-chromium"):
            with self.subTest(base=name):
                self.assertTrue(
                    any(
                        f"--build-arg BASE=localhost/example/desktop:1.2.3" in line
                        and f"localhost/example/{name}:1.2.3" in line
                        for line in calls
                    ),
                    f"{name} must build on the published base: {calls}",
                )

        tags = (*SAMPLE_TAGS, "sha-abc1234")
        for name in ("desktop", "desktop-firefox", "desktop-chromium"):
            for tag in tags:
                reference = f"localhost/example/{name}:{tag}"
                with self.subTest(image=name, tag=tag):
                    self.assertTrue(
                        any(line.startswith("tag ") and line.endswith(f" {reference}")
                            for line in calls),
                        f"{reference} was never tagged: {calls}",
                    )
                    self.assertIn(f"push {reference}", calls)


class Workflow(unittest.TestCase):
    """The workflow must publish exactly the references the CLI resolves."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.text = WORKFLOW.read_text(encoding="utf-8")

    def test_release_and_manual_triggers(self):
        self.assertIn("v*", self.text)
        self.assertIn("workflow_dispatch:", self.text)
        self.assertIn("pull_request:", self.text)
        self.assertIn("packages: write", self.text)

    def test_image_names_and_major_tag_match_the_cli(self):
        self.assertIn(flavours.DEFAULT_REGISTRY, self.text)
        self.assertEqual(len(flavours.names()), 3)

        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, clear=False):
            os.environ["DESKBENCH_FLAVOURS_DIR"] = tmp
            os.environ.pop("DESKBENCH_REGISTRY", None)
            images = [flavours.get(name).image for name in flavours.names()]

        prefix = f"{flavours.DEFAULT_REGISTRY}/"
        for image in images:
            self.assertTrue(image.startswith(prefix), image)
            repository = image[len(prefix):].rsplit(":", 1)[0]
            with self.subTest(repository=repository):
                self.assertIn(repository, self.text)

        major = run_tags("1.0.0").stdout.splitlines()[2]
        self.assertEqual(major, flavours.TAG_VERSION)

    def test_tags_have_a_single_source(self):
        self.assertIn("scripts/image-tags.sh", self.text)
        self.assertNotIn(":latest", self.text)
        self.assertIsNone(
            re.search(r":\d+\.\d+", self.text),
            "the workflow must not hardcode a second tag list",
        )

    def test_pull_requests_build_without_pushing(self):
        _, _, publish_job = self.text.partition("\n  publish:")
        before = self.text[: self.text.index("\n  publish:")]

        self.assertIn("pull_request", before)
        self.assertIn("docker build", before)
        self.assertNotIn("docker push", before)
        self.assertNotIn("packages: write", before)

        self.assertIn("docker push", publish_job)


class Taskfile(unittest.TestCase):
    def test_publish_task_uses_the_shared_script(self):
        text = TASKFILE.read_text(encoding="utf-8")
        match = re.search(
            r"^  publish:\n(.*?)(?=^  \w[\w-]*:\n|\Z)",
            text,
            flags=re.MULTILINE | re.DOTALL,
        )
        self.assertIsNotNone(match, "Taskfile has no publish task")
        section = match.group(1)
        self.assertIn("scripts/publish-images.sh", section)
        self.assertIn("VERSION", section)
        self.assertIn("ghcr.io/nhermosilla14/agent-deskbench", section)


if __name__ == "__main__":
    unittest.main()
