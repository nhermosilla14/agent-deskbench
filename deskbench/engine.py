"""The only module that talks to Podman.

Everything else in the package treats this as the database: containers labelled
``deskbench=1`` are the desktops, their names are the desktop names, and their published
port is the viewer URL.
"""

from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from . import sessions

IMAGE = os.environ.get("DESKBENCH_IMAGE", "localhost/agent-deskbench/desktop:1")
IMAGE_CONTEXT = Path(__file__).resolve().parent.parent / "image"
SHOT_PATH_TEMPLATE = "/tmp/deskbench-shot-{unique}.png"


class EngineError(RuntimeError):
    """The container runtime refused, or is missing."""


@dataclass(frozen=True)
class Desktop:
    name: str
    container: str
    state: str
    url: str
    id: str

    def as_dict(self) -> dict[str, str]:
        return {"name": self.name, "url": self.url, "id": self.id, "state": self.state}


def _podman(args: list[str], *, capture: bool = True, check: bool = True) -> subprocess.CompletedProcess:
    exe = shutil.which("podman")
    if exe is None:
        raise EngineError("podman was not found on PATH; install podman to use deskbench")
    proc = subprocess.run(
        [exe, *args],
        capture_output=capture,
        text=True,
        check=False,
    )
    if check and proc.returncode != 0:
        detail = [line for line in (proc.stderr or proc.stdout or "").strip().splitlines() if line.strip()]
        if detail:
            message = detail[-1] if len(detail) == 1 else " | ".join(detail[-3:])
        elif not capture:
            message = f"podman {args[0]} failed; see the output above"
        else:
            message = f"podman {' '.join(args[:2])} failed"
        raise EngineError(message)
    return proc


def _host_port(entries: list[dict]) -> int | None:
    for entry in entries:
        if entry.get("container_port") == sessions.WEB_PORT and entry.get("protocol", "tcp") == "tcp":
            port = entry.get("host_port")
            return int(port) if port else None
    return None


def list_desktops() -> list[Desktop]:
    proc = _podman(["ps", "--filter", f"label={sessions.LABEL}", "--format", "json"])
    raw = (proc.stdout or "").strip() or "[]"
    try:
        entries = json.loads(raw)
    except json.JSONDecodeError as exc:  # pragma: no cover - defensive
        raise EngineError(f"could not read podman output: {exc}") from exc

    desktops = []
    for entry in entries:
        names = entry.get("Names") or []
        container = names[0] if names else ""
        if not container:
            continue
        port = _host_port(entry.get("Ports") or [])
        desktops.append(
            Desktop(
                name=sessions.desktop_name(container),
                container=container,
                state=entry.get("State", "unknown"),
                url=sessions.viewer_url(port) if port else "",
                id=entry.get("Id", ""),
            )
        )
    return sorted(desktops, key=lambda desktop: desktop.name)


def get(name: str) -> Desktop:
    for desktop in list_desktops():
        if desktop.name == name:
            return desktop
    raise EngineError(f"no desktop named {name!r}; run `deskbench ls` to see what exists")


def image_exists(image: str = IMAGE) -> bool:
    return _podman(["image", "exists", image], check=False).returncode == 0


def ensure_image(image: str = IMAGE) -> None:
    if image_exists(image):
        return
    if image != IMAGE:
        raise EngineError(f"image {image!r} is not present; build or pull it first")
    if not (IMAGE_CONTEXT / "Dockerfile").is_file():
        raise EngineError(f"no image {image!r} and no Dockerfile at {IMAGE_CONTEXT}")
    print(f"deskbench: building {image} (first run only) ...", file=sys.stderr, flush=True)
    _podman(["build", "-t", image, str(IMAGE_CONTEXT)], capture=False)


def create(name: str, size: str = sessions.DEFAULT_SIZE, image: str = IMAGE) -> Desktop:
    container = sessions.container_name(name)
    ensure_image(image)
    _podman(
        [
            "run",
            "-d",
            "--rm",
            "--name",
            container,
            "--label",
            sessions.LABEL,
            "-p",
            f"127.0.0.1::{sessions.WEB_PORT}",
            "-e",
            f"DESKBENCH_SIZE={size}",
            image,
        ]
    )
    return get(name)


def stop(name: str) -> None:
    container = get(name).container
    _podman(["stop", "--time", "2", container])


def exec_in(name: str, command: list[str]) -> int:
    container = get(name).container
    proc = _podman(["exec", container, "sh", "-lc", shlex.join(command)], capture=False, check=False)
    return proc.returncode


def shot(name: str, destination: Path, settle_ms: int = 250) -> Path:
    """Capture the desktop, waiting for a mapped window and a still frame.

    ``settle_ms`` is how long the screen must stay unchanged; the total wait is bounded inside
    the container so an animation cannot hang the caller.
    """
    container = get(name).container
    unique = f"{os.getpid()}-{int(time.time() * 1000)}"
    remote = SHOT_PATH_TEMPLATE.format(unique=unique)
    _podman(["exec", container, "deskbench-capture", remote, str(settle_ms)])
    destination.parent.mkdir(parents=True, exist_ok=True)
    _podman(["cp", f"{container}:{remote}", str(destination)])
    return destination


def logs(name: str, tail: int = 40) -> str:
    container = get(name).container
    proc = _podman(["logs", "--tail", str(tail), container], capture=True, check=False)
    return (proc.stdout or "") + (proc.stderr or "")
