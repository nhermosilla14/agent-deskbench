"""The only module that talks to Podman.

Everything else in the package treats this as the database: containers labelled
``deskbench=1`` are the desktops, their names are the desktop names, and their published
port is the viewer URL.
"""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

from . import flavours, runtime as runtimes, sessions

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
    labels: dict[str, str] = field(default_factory=dict)

    def as_dict(self) -> dict[str, str]:
        return {"name": self.name, "url": self.url, "id": self.id, "state": self.state}


def _podman(args: list[str], *, capture: bool = True, check: bool = True) -> subprocess.CompletedProcess:
    try:
        runtime = runtimes.detect()
    except runtimes.MissingRuntime as exc:
        raise EngineError(str(exc)) from exc
    proc = subprocess.run(
        [runtime.binary, *args],
        capture_output=capture,
        text=True,
        check=False,
    )
    if check and proc.returncode != 0:
        detail = [line for line in (proc.stderr or proc.stdout or "").strip().splitlines() if line.strip()]
        if detail:
            message = detail[-1] if len(detail) == 1 else " | ".join(detail[-3:])
        elif not capture:
            message = f"{runtime.name} {args[0]} failed; see the output above"
        else:
            message = f"{runtime.name} {' '.join(args[:2])} failed"
        raise EngineError(message)
    return proc


def list_desktops() -> list[Desktop]:
    runtime = runtimes.detect()
    proc = _podman(["ps", "--filter", f"label={sessions.LABEL}", "--format", "json"])
    try:
        rows = runtimes.parse_ps(proc.stdout or "", runtime)
    except json.JSONDecodeError as exc:  # pragma: no cover - defensive
        raise EngineError(f"could not read {runtime.name} output: {exc}") from exc

    desktops = []
    for row in rows:
        port = row["host_port"]
        labels = row["labels"]
        scheme = labels.get(sessions.VIEWER_SCHEME_LABEL, "http")
        path = labels.get(sessions.VIEWER_PATH_LABEL, sessions.DEFAULT_VIEWER_PATH)
        desktops.append(
            Desktop(
                name=sessions.desktop_name(row["name"]),
                container=row["name"],
                state=row["state"],
                url=sessions.viewer_url(port, scheme=scheme, path=path) if port else "",
                id=row["id"],
                labels=dict(labels),
            )
        )
    return sorted(desktops, key=lambda desktop: desktop.name)


def get(name: str) -> Desktop:
    for desktop in list_desktops():
        if desktop.name == name:
            return desktop
    raise EngineError(f"no desktop named {name!r}; run `deskbench ls` to see what exists")


def image_exists(image: str) -> bool:
    runtime = runtimes.detect()
    return _podman(runtimes.image_exists_args(runtime, image), check=False).returncode == 0


def ensure_image(image: str, policy: str = "missing") -> None:
    """Make ``image`` locally available according to ``policy``.

    ``missing`` (the default) pulls only when the image is absent, ``always`` refreshes it, and
    ``never`` refuses to pull. Pull progress goes to stderr so stdout stays machine-readable.
    """
    if policy not in ("missing", "always", "never"):
        raise ValueError(f"unknown pull policy {policy!r}; use missing, always or never")

    present = image_exists(image)
    if policy == "never":
        if not present:
            raise EngineError(
                f"image {image!r} is not present and --pull=never forbids pulling"
            )
        return
    if policy == "missing" and present:
        return

    print(f"deskbench: pulling {image} ...", file=sys.stderr, flush=True)
    _podman(["pull", image], capture=False)


def _viewer_answers(url: str) -> bool:
    """Whether ``url`` serves a viewer.

    A viewer that asks for credentials before it renders is reachable: a 401 or 403 means
    something is listening and speaking HTTP, which is all readiness can require.
    """
    try:
        with urllib.request.urlopen(url, timeout=2) as response:
            return 200 <= response.status < 400
    except urllib.error.HTTPError as exc:
        return exc.code in (401, 403)
    except (OSError, urllib.error.URLError):
        return False


def wait_ready(desktop: Desktop, timeout: float = 30.0) -> Desktop:
    """Block until the desktop's viewer answers.

    ``podman run`` returns as soon as the container starts, which is well before the X server and
    the window manager are usable. A caller that follows ``new`` with a GUI command would race the
    entrypoint and lose, with no error anyone can see. Waiting here removes the race for everybody.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if desktop.url and _viewer_answers(desktop.url):
            return desktop
        time.sleep(0.2)
    raise EngineError(f"desktop {desktop.name!r} did not become reachable within {timeout:.0f}s")


def _size_values(size: str) -> tuple[str, str]:
    width, _, height = size.partition("x")
    return width, height


def _env_args(flavour: flavours.Flavour, size: str) -> list[str]:
    """``-e`` arguments for the manifest environment, with the size substituted in."""
    width, height = _size_values(size)
    args = ["-e", f"DESKBENCH_SIZE={size}"]
    for key, value in flavour.run.env.items():
        resolved = value.replace("{width}", width).replace("{height}", height)
        args.extend(["-e", f"{key}={resolved}"])
    return args


def _label_args(flavour: flavours.Flavour) -> list[str]:
    """The effective contract, recorded on the container so later calls need no manifest."""
    labels = (
        (sessions.VIEWER_PORT_LABEL, str(flavour.viewer.port)),
        (sessions.VIEWER_PATH_LABEL, flavour.viewer.path),
        (sessions.VIEWER_SCHEME_LABEL, flavour.viewer.scheme),
        (sessions.RUN_USER_LABEL, flavour.run.user),
    )
    args: list[str] = []
    for key, value in labels:
        args.extend(["--label", f"{key}={value}"])
    return args


def _run_args(
    flavour: flavours.Flavour,
    container: str,
    size: str,
    volumes: list[str],
) -> list[str]:
    """Build the ``run`` arguments: identity, mounts, viewer port, environment and argv."""
    uid, gid = flavours.parse_user(flavour.run.user)
    runtime = runtimes.detect()
    args = [
        "run",
        "-d",
        "--rm",
        "--name",
        container,
        "--label",
        sessions.LABEL,
        *runtimes.user_args(runtime, uid, gid),
        *volumes,
        "-p",
        f"127.0.0.1::{flavour.viewer.port}",
        *_env_args(flavour, size),
        *_label_args(flavour),
    ]
    if flavour.run.entrypoint:
        args.extend(["--entrypoint", flavour.run.entrypoint[0]])
    args.append(flavour.image)
    if flavour.run.entrypoint:
        args.extend(flavour.run.entrypoint[1:])
    args.extend(flavour.run.command)
    return args


def _discard(container: str) -> None:
    """Remove a container after a failed ``new``, so nothing is left behind."""
    try:
        if _podman(["stop", "--time", "2", container], check=False).returncode != 0:
            _podman(["rm", "-f", container], check=False)
    except EngineError:  # pragma: no cover - the runtime itself is gone
        pass


def _probe_shell(desktop: Desktop, flavour: flavours.Flavour) -> None:
    """Refuse a container where ``exec`` could never run a command."""
    proc = _podman(
        ["exec", "--user", flavour.run.user, desktop.container, "sh", "-lc", "true"],
        check=False,
    )
    if proc.returncode != 0:
        raise EngineError(
            f"flavour {flavour.name!r} has no usable 'sh' for exec as user "
            f"{flavour.run.user}"
        )


def create(
    name: str,
    size: str,
    flavour: flavours.Flavour,
    binds: list[sessions.Bind] | None = None,
    pull: str = "missing",
) -> Desktop:
    """Start ``flavour`` as a desktop and prove it satisfies the desktop contract.

    The container is the record of what was started: the viewer port, path, scheme and the
    process user become labels. A failure after ``podman run`` — an unreachable viewer, a
    missing shell — removes the container instead of leaving a desktop that cannot be used.
    """
    container = sessions.container_name(name)
    ensure_image(flavour.image, pull)
    volumes: list[str] = []
    for bind in binds or []:
        volumes.extend(["-v", bind.as_volume()])
    try:
        _podman(_run_args(flavour, container, size, volumes))
        desktop = wait_ready(get(name), timeout=flavour.viewer.timeout)
        _probe_shell(desktop, flavour)
    except BaseException:
        _discard(container)
        raise
    return desktop


def stop(name: str) -> None:
    container = get(name).container
    _podman(["stop", "--time", "2", container])


def exec_in(name: str, command: list[str]) -> int:
    """Run ``command`` inside the desktop as the user it was started with.

    The user comes from the container's labels, so a manifest edited after ``new`` cannot move
    a running desktop to another identity.
    """
    desktop = get(name)
    args = ["exec"]
    user = desktop.labels.get(sessions.RUN_USER_LABEL)
    if user:
        args.extend(["--user", user])
    args.extend([desktop.container, "sh", "-lc", shlex.join(command)])
    proc = _podman(args, capture=False, check=False)
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
