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
import tempfile
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


def _podman(
    args: list[str],
    *,
    capture: bool = True,
    check: bool = True,
    timeout: float | None = None,
) -> subprocess.CompletedProcess:
    try:
        runtime = runtimes.detect()
    except runtimes.MissingRuntime as exc:
        raise EngineError(str(exc)) from exc
    try:
        proc = subprocess.run(
            [runtime.binary, *args],
            capture_output=capture,
            text=True,
            check=False,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise EngineError(
            f"{runtime.name} {' '.join(args[:2])} timed out after {timeout:g}s"
        ) from exc
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
    labels = [
        (sessions.VIEWER_PORT_LABEL, str(flavour.viewer.port)),
        (sessions.VIEWER_PATH_LABEL, flavour.viewer.path),
        (sessions.VIEWER_SCHEME_LABEL, flavour.viewer.scheme),
        (sessions.RUN_USER_LABEL, flavour.run.user),
    ]
    if flavour.screenshot.command is not None:
        settle = True if flavour.screenshot.settle is None else flavour.screenshot.settle
        payload = json.dumps(
            {"command": list(flavour.screenshot.command), "settle": settle},
            separators=(",", ":"),
        )
        labels.append((sessions.SCREENSHOT_LABEL, payload))
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


# Tools a third-party image is known to ship, in preference order. A manifest command always
# wins; this chain is what makes a bare ``--image`` usable without a manifest.
_CAPTURE_FALLBACKS = (
    (
        "deskbench-capture",
        ("/usr/local/bin/deskbench-capture", "{output}", "{settle}"),
        False,
    ),
    ("scrot", ("scrot", "-o", "{output}"), True),
    ("import", ("import", "-window", "root", "{output}"), True),
)

_PROBE_ATTEMPTS = 3
_SETTLE_ATTEMPTS = 10


def _resolve_screenshot(
    desktop: Desktop,
    configured: flavours.Screenshot | None,
    user: str | None,
) -> tuple[tuple[str, ...], bool] | None:
    """Return the capture argv and settle flag, or ``None`` when the image ships no tool.

    A command recorded in the manifest (or its label) wins. Otherwise the image is probed for the
    tools deskbench knows how to drive, because image metadata never says which one exists.
    """
    if configured is not None and configured.command is not None:
        settle = True if configured.settle is None else configured.settle
        return configured.command, settle

    for tool, command, settle in _CAPTURE_FALLBACKS:
        args = ["exec"]
        if user:
            args.extend(["--user", user])
        args.extend([desktop.container, "sh", "-lc", f"command -v {tool}"])
        if _podman(args, check=False).returncode == 0:
            return command, settle
    return None


def _substitute_capture(
    argv: tuple[str, ...], output: str, settle_ms: int
) -> list[str]:
    """Replace the capture placeholders, leaving every other character alone."""
    settle = str(settle_ms)
    return [argument.replace("{output}", output).replace("{settle}", settle) for argument in argv]


def _run_capture(
    desktop: Desktop,
    user: str | None,
    command: list[str],
    timeout: float = 30,
) -> None:
    """Run one capture command as the desktop's user, surfacing its stderr on failure."""
    args = ["exec"]
    if user:
        args.extend(["--user", user])
    args.extend([desktop.container, *command])
    proc = _podman(args, check=False, timeout=timeout)
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip()
        message = f"screenshot command {shlex.join(command)} failed"
        if detail:
            message = f"{message}: {detail}"
        raise EngineError(message)


def _remote_has_file(desktop: Desktop, user: str | None, path: str) -> bool:
    """Whether ``path`` exists inside the container with a non-zero size."""
    args = ["exec"]
    if user:
        args.extend(["--user", user])
    args.extend([desktop.container, "test", "-s", path])
    return _podman(args, check=False, timeout=10).returncode == 0


def _probe_screenshot(desktop: Desktop, flavour: flavours.Flavour) -> None:
    """Refuse a container whose screenshot command cannot write a non-empty file.

    A third-party X server may still be warming up, so a first failure is retried a few times
    before the flavour is declared unviable.
    """
    resolved = _resolve_screenshot(desktop, flavour.screenshot, flavour.run.user)
    if resolved is None:
        raise EngineError(
            f"flavour {flavour.name!r} has no screenshot tool; "
            "add [screenshot].command to its manifest"
        )
    command, _ = resolved
    unique = f"{os.getpid()}-{int(time.time() * 1000)}"
    remote = f"/tmp/deskbench-probe-{unique}.png"
    last = "the command wrote no file"
    for attempt in range(_PROBE_ATTEMPTS):
        try:
            _run_capture(
                desktop, flavour.run.user, _substitute_capture(command, remote, 250)
            )
            if _remote_has_file(desktop, flavour.run.user, remote):
                return
            last = "the command wrote no file"
        except EngineError as exc:
            last = str(exc)
        if attempt + 1 < _PROBE_ATTEMPTS:
            time.sleep(0.5)
    raise EngineError(f"flavour {flavour.name!r} cannot take a screenshot: {last}")


def create(
    name: str,
    size: str,
    flavour: flavours.Flavour,
    binds: list[sessions.Bind] | None = None,
    pull: str = "missing",
) -> Desktop:
    """Start ``flavour`` as a desktop and prove it satisfies the desktop contract.

    The container is the record of what was started: the viewer port, path, scheme, screenshot
    command and process user become labels. A failure after ``podman run`` — an unreachable
    viewer, a missing shell, a screenshot that writes nothing — removes the container instead of
    leaving a desktop that cannot be used.
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
        _probe_screenshot(desktop, flavour)
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


def _stored_screenshot(desktop: Desktop) -> flavours.Screenshot | None:
    """Read the screenshot contract recorded on the container, or ``None`` when absent.

    An unparseable label is treated like a missing one: the image still gets the fallback
    chain, so a container created before this feature keeps taking screenshots.
    """
    template = f'{{{{ index .Config.Labels "{sessions.SCREENSHOT_LABEL}" }}}}'
    proc = _podman(["inspect", "--format", template, desktop.container], check=False)
    if proc.returncode != 0:
        return None
    text = (proc.stdout or "").strip()
    if not text or text == "<no value>":
        return None
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    command = data.get("command")
    settle = data.get("settle", True)
    if not isinstance(command, list) or not command:
        return None
    if not all(isinstance(item, str) and item for item in command):
        return None
    if not any("{output}" in item for item in command):
        return None
    if not isinstance(settle, bool):
        return None
    return flavours.Screenshot(command=tuple(command), settle=settle)


def _capture_until_still(
    desktop: Desktop,
    user: str | None,
    command: tuple[str, ...],
    settle_ms: int,
    destination: Path,
) -> None:
    """Capture until two consecutive frames match, bounded, then copy the frame to ``destination``.

    Compares on the host because the image may ship any capture tool; the remote paths stay
    distinct so a slow copy cannot overwrite the frame being compared.
    """
    frames: list[Path] = []
    chosen: Path | None = None
    previous: bytes | None = None
    unique = f"{os.getpid()}-{int(time.time() * 1000)}"
    try:
        for attempt in range(_SETTLE_ATTEMPTS):
            remote = SHOT_PATH_TEMPLATE.format(unique=f"{unique}-{attempt}")
            _run_capture(
                desktop, user, _substitute_capture(command, remote, settle_ms)
            )
            handle, path = tempfile.mkstemp(prefix="deskbench-shot-", suffix=".png")
            os.close(handle)
            frame = Path(path)
            frames.append(frame)
            _podman(["cp", f"{desktop.container}:{remote}", str(frame)])
            data = frame.read_bytes()
            chosen = frame
            if previous is not None and data == previous:
                break
            previous = data
            if attempt + 1 < _SETTLE_ATTEMPTS and settle_ms > 0:
                time.sleep(settle_ms / 1000)
        else:
            print(
                f"deskbench: the screen did not settle after {_SETTLE_ATTEMPTS} captures; "
                "using the last frame",
                file=sys.stderr,
            )
        if chosen is None:  # pragma: no cover - _SETTLE_ATTEMPTS is positive
            raise EngineError("the screenshot command produced no frames")
        shutil.copyfile(chosen, destination)
    finally:
        for frame in frames:
            try:
                frame.unlink()
            except FileNotFoundError:  # pragma: no cover - defensive
                pass


def shot(name: str, destination: Path, settle_ms: int = 250) -> Path:
    """Capture the desktop using the contract recorded when it was created.

    A manifest or label command wins; otherwise a known tool in the image is used. With
    ``settle`` the screen must stay unchanged for ``settle_ms``, bounded so an animation cannot
    hang the caller; without it the command's own waiting is trusted and it runs once.
    """
    desktop = get(name)
    user = desktop.labels.get(sessions.RUN_USER_LABEL)
    configured = _stored_screenshot(desktop)
    resolved = _resolve_screenshot(desktop, configured, user)
    if resolved is None:
        raise EngineError(
            f"flavour for desktop {desktop.name!r} has no screenshot tool; "
            "add [screenshot].command to its manifest"
        )
    command, settle = resolved
    destination.parent.mkdir(parents=True, exist_ok=True)
    if settle:
        _capture_until_still(desktop, user, command, settle_ms, destination)
        return destination

    unique = f"{os.getpid()}-{int(time.time() * 1000)}"
    remote = SHOT_PATH_TEMPLATE.format(unique=unique)
    _run_capture(desktop, user, _substitute_capture(command, remote, settle_ms))
    _podman(["cp", f"{desktop.container}:{remote}", str(destination)])
    return destination


def logs(name: str, tail: int = 40) -> str:
    container = get(name).container
    proc = _podman(["logs", "--tail", str(tail), container], capture=True, check=False)
    return (proc.stdout or "") + (proc.stderr or "")
