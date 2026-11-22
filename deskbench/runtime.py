"""Which container runtime to use, and the few places where Podman and Docker differ.

Podman is preferred. Only three things genuinely differ: how a non-root user maps to the host uid,
the shape of ``ps --format json`` (an array versus one object per line), and how to ask whether an
image exists.
"""

from __future__ import annotations

import json
import os
import re
import shutil
from dataclasses import dataclass

PODMAN = "podman"
DOCKER = "docker"
WEB_PORT = 6080
IMAGE_UID = 1000


class MissingRuntime(RuntimeError):
    """No usable container runtime was found."""


@dataclass(frozen=True)
class Runtime:
    name: str
    binary: str

    @property
    def is_podman(self) -> bool:
        return self.name == PODMAN


def detect() -> Runtime:
    """Return the runtime to use: ``DESKBENCH_RUNTIME`` if set, else Podman, else Docker."""
    forced = os.environ.get("DESKBENCH_RUNTIME", "").strip()
    if forced:
        binary = shutil.which(forced)
        if binary is None:
            raise MissingRuntime(f"{forced} was requested in DESKBENCH_RUNTIME but is not on PATH")
        return Runtime(name=forced, binary=binary)
    for name in (PODMAN, DOCKER):
        binary = shutil.which(name)
        if binary is not None:
            return Runtime(name=name, binary=binary)
    raise MissingRuntime("no container runtime found: install podman (preferred) or docker")


def user_args(runtime: Runtime) -> list[str]:
    """Map the in-image user (uid 1000) to the invoking host user.

    Podman can express this exactly. Docker cannot: rootful Docker maps container uid 1000 to host
    uid 1000 directly, so ``--user`` is enough on the common single-user machine, and rootless
    Docker needs its own userns-remap configuration.
    """
    if runtime.is_podman:
        return [f"--userns=keep-id:uid={IMAGE_UID},gid={IMAGE_UID}"]
    return ["--user", f"{IMAGE_UID}:{IMAGE_UID}"]


def image_exists_args(runtime: Runtime, image: str) -> list[str]:
    if runtime.is_podman:
        return ["image", "exists", image]
    return ["image", "inspect", image]


def events_command(runtime: Runtime, label: str) -> list[str]:
    if runtime.is_podman:
        return ["events", "--filter", "type=container", "--filter", f"label={label}",
                "--format", "json"]
    return ["events", "--filter", "type=container", "--filter", f"label={label}",
            "--format", "{{json .}}"]


_DOCKER_PORT = re.compile(r":(\d+)->(\d+)/tcp")


def _podman_host_port(entries: object) -> int | None:
    for entry in entries or []:  # type: ignore[union-attr]
        if entry.get("container_port") == WEB_PORT and entry.get("protocol", "tcp") == "tcp":
            port = entry.get("host_port")
            if port:
                return int(port)
    return None


def _docker_host_port(ports: object) -> int | None:
    for match in _DOCKER_PORT.finditer(str(ports or "")):
        if int(match.group(2)) == WEB_PORT:
            return int(match.group(1))
    return None


def parse_ps(output: str, runtime: Runtime) -> list[dict]:
    """Normalise ``ps --format json`` into ``[{name, state, host_port, id}]``."""
    rows: list[dict] = []
    if runtime.is_podman:
        for item in json.loads(output or "[]"):
            names = item.get("Names") or []
            if not names:
                continue
            rows.append({
                "name": names[0],
                "state": item.get("State", "unknown"),
                "host_port": _podman_host_port(item.get("Ports")),
                "id": item.get("Id", ""),
            })
        return rows

    for line in (output or "").splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        name = item.get("Names") or ""
        if not name:
            continue
        rows.append({
            "name": name,
            "state": item.get("State", "unknown"),
            "host_port": _docker_host_port(item.get("Ports")),
            "id": item.get("ID", ""),
        })
    return rows
