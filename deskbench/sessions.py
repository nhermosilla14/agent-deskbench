"""Naming and URL rules. Pure functions, no I/O, so they are cheap to test."""

from __future__ import annotations

import re

PREFIX = "deskbench-"
LABEL = "deskbench=1"
WEB_PORT = 6080
DEFAULT_SIZE = "1600x1000"

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


def viewer_url(host_port: int, host: str = "127.0.0.1") -> str:
    return f"http://{host}:{host_port}/vnc.html?autoconnect=1&resize=scale"
