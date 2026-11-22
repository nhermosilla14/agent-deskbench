"""Runtime differences: parsing, uid mapping, and selection."""

from __future__ import annotations

import json
import os
import unittest
from unittest import mock

from deskbench import runtime as runtimes

PODMAN = runtimes.Runtime(name="podman", binary="/usr/bin/podman")
DOCKER = runtimes.Runtime(name="docker", binary="/usr/bin/docker")

PODMAN_PS = json.dumps([
    {
        "Names": ["deskbench-alpha"],
        "State": "running",
        "Id": "abc123",
        "Ports": [
            {"host_ip": "127.0.0.1", "container_port": 6080, "host_port": 41234, "protocol": "tcp"},
        ],
    },
    {
        "Names": ["deskbench-beta"],
        "State": "exited",
        "Id": "def456",
        "Ports": [],
    },
])

# Docker prints one object per line, with a flat Ports string.
DOCKER_PS = "\n".join([
    json.dumps({"Names": "deskbench-alpha", "State": "running", "ID": "abc123",
                "Ports": "127.0.0.1:32768->6080/tcp"}),
    json.dumps({"Names": "deskbench-beta", "State": "exited", "ID": "def456", "Ports": ""}),
])


class Parsing(unittest.TestCase):
    def test_podman_array(self):
        rows = runtimes.parse_ps(PODMAN_PS, PODMAN)
        self.assertEqual(rows[0], {"name": "deskbench-alpha", "state": "running",
                                   "host_port": 41234, "id": "abc123"})
        self.assertIsNone(rows[1]["host_port"])

    def test_docker_lines(self):
        rows = runtimes.parse_ps(DOCKER_PS, DOCKER)
        self.assertEqual(rows[0], {"name": "deskbench-alpha", "state": "running",
                                   "host_port": 32768, "id": "abc123"})
        self.assertIsNone(rows[1]["host_port"])

    def test_empty_output_is_an_empty_list(self):
        self.assertEqual(runtimes.parse_ps("", PODMAN), [])
        self.assertEqual(runtimes.parse_ps("", DOCKER), [])

    def test_ignores_ports_that_are_not_the_viewer(self):
        # A native VNC port published by hand must not be mistaken for the viewer.
        rows = runtimes.parse_ps(
            json.dumps({"Names": "deskbench-x", "State": "running", "ID": "1",
                        "Ports": "0.0.0.0:5901->5901/tcp"}),
            DOCKER,
        )
        self.assertIsNone(rows[0]["host_port"])


class Mapping(unittest.TestCase):
    def test_podman_keeps_the_id(self):
        self.assertEqual(runtimes.user_args(PODMAN), ["--userns=keep-id:uid=1000,gid=1000"])

    def test_docker_uses_a_plain_user(self):
        self.assertEqual(runtimes.user_args(DOCKER), ["--user", "1000:1000"])

    def test_image_existence_uses_the_right_verb(self):
        self.assertEqual(runtimes.image_exists_args(PODMAN, "img:1"), ["image", "exists", "img:1"])
        self.assertEqual(runtimes.image_exists_args(DOCKER, "img:1"), ["image", "inspect", "img:1"])

    def test_events_format_differs(self):
        self.assertEqual(runtimes.events_command(PODMAN, "deskbench=1")[-1], "json")
        self.assertEqual(runtimes.events_command(DOCKER, "deskbench=1")[-1], "{{json .}}")


class Detection(unittest.TestCase):
    def test_prefers_podman_when_both_exist(self):
        with mock.patch.dict(os.environ, {}, clear=False), \
                mock.patch.object(runtimes.shutil, "which", side_effect=lambda name: f"/usr/bin/{name}"):
            os.environ.pop("DESKBENCH_RUNTIME", None)
            self.assertEqual(runtimes.detect().name, "podman")

    def test_falls_back_to_docker(self):
        os.environ.pop("DESKBENCH_RUNTIME", None)
        with mock.patch.object(runtimes.shutil, "which", side_effect=lambda name: "/usr/bin/docker" if name == "docker" else None):
            self.assertEqual(runtimes.detect().name, "docker")

    def test_explicit_choice_wins(self):
        with mock.patch.dict(os.environ, {"DESKBENCH_RUNTIME": "docker"}), \
                mock.patch.object(runtimes.shutil, "which", side_effect=lambda name: f"/usr/bin/{name}"):
            self.assertEqual(runtimes.detect().name, "docker")

    def test_nothing_installed_is_reported(self):
        os.environ.pop("DESKBENCH_RUNTIME", None)
        with mock.patch.object(runtimes.shutil, "which", return_value=None):
            with self.assertRaises(runtimes.MissingRuntime):
                runtimes.detect()


if __name__ == "__main__":
    unittest.main()
