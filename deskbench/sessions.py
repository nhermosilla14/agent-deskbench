"""Naming and URL rules. Pure functions, no I/O, so they are cheap to test."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass

PREFIX = "deskbench-"
LABEL = "deskbench=1"
WEB_PORT = 6080
DEFAULT_SIZE = "1600x1000"
DEFAULT_VIEWER_PATH = "/vnc.html?autoconnect=1&resize=scale"

# Labels recording the effective contract of a running desktop. The runtime is the only state
# store, so a desktop keeps the configuration it started with even if its manifest changes.
VIEWER_PORT_LABEL = "deskbench.viewer.port"
VIEWER_PATH_LABEL = "deskbench.viewer.path"
VIEWER_SCHEME_LABEL = "deskbench.viewer.scheme"
RUN_USER_LABEL = "deskbench.run.user"

_NAME = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,29}[a-z0-9])?$")
_SIZE = re.compile(r"^(\d{3,5})x(\d{3,5})$")


class SessionError(ValueError):
    """A caller-supplied name or size is not usable."""


def validate_name(value: str) -> str:
    """Return the name if it is a legal desktop name, else raise."""
    if not _NAME.match(value):
        raise SessionError(
            f"invalid desktop name {value!r}: use 1-31 lowercase letters, digits or hyphens, "
            "starting and ending with a letter or digit"
        )
    return value


def validate_size(value: str) -> str:
    """Return ``WxH`` if both sides are plausible, else raise."""
    match = _SIZE.match(value)
    if not match or not (320 <= int(match.group(1)) <= 7680 and 240 <= int(match.group(2)) <= 4320):
        raise SessionError(f"invalid size {value!r}: expected WIDTHxHEIGHT, for example 1600x1000")
    return value


def container_name(name: str) -> str:
    return f"{PREFIX}{validate_name(name)}"


def desktop_name(container: str) -> str:
    """Inverse of :func:`container_name`; tolerates foreign names."""
    return container[len(PREFIX):] if container.startswith(PREFIX) else container


def next_free_name(taken: list[str]) -> str:
    """Lowest ``desk<N>`` not already in use."""
    used = set(taken)
    index = 1
    while f"desk{index}" in used:
        index += 1
    return f"desk{index}"


def viewer_url(
    host_port: int,
    host: str = "127.0.0.1",
    scheme: str = "http",
    path: str = DEFAULT_VIEWER_PATH,
) -> str:
    """Return the viewer URL for a published host port.

    The path defaults to the built-in image's noVNC page; a third-party image may publish
    anything else. A path without a leading slash is still addressed from the root.
    """
    if not path.startswith("/"):
        path = f"/{path}"
    return f"{scheme}://{host}:{host_port}{path}"


@dataclass(frozen=True)
class Bind:
    """One host path made visible inside the desktop."""

    source: str
    target: str
    read_only: bool = False

    def as_volume(self) -> str:
        return f"{self.source}:{self.target}" + (":ro" if self.read_only else "")


def parse_bind(value: str) -> Bind:
    """Parse ``SRC[:DST][:ro]``.

    The destination defaults to ``/mnt/<basename>`` because requiring the caller to repeat the
    name is noise for the common case.
    """
    parts = value.split(":")
    if len(parts) > 3:
        raise SessionError(f"invalid --bind {value!r}: expected SRC[:DST][:ro]")

    source = os.path.abspath(os.path.expanduser(parts[0]))
    if not os.path.exists(source):
        raise SessionError(f"--bind source does not exist: {source}")

    read_only = False
    if len(parts) == 3:
        mode = parts[2]
        if mode not in ("ro", "rw"):
            raise SessionError(f"invalid --bind mode {mode!r}: use ro or rw")
        read_only = mode == "ro"

    target = parts[1] if len(parts) >= 2 and parts[1] else f"/mnt/{os.path.basename(source)}"
    if not target.startswith("/"):
        raise SessionError(f"--bind destination must be absolute: {target!r}")

    return Bind(source=source, target=target.rstrip("/") or "/", read_only=read_only)
