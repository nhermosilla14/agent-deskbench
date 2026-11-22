"""Named image variants shipped with the project.

A flavour is a thin Dockerfile that builds on top of the base desktop image. The list is declared
here rather than discovered from the filesystem so that it works from an installed copy, and a test
keeps the declarations honest.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

IMAGE_ROOT = Path(__file__).resolve().parent.parent / "image"
REGISTRY = "localhost/agent-deskbench"
TAG_VERSION = "1"


@dataclass(frozen=True)
class Flavour:
    name: str
    summary: str
    dockerfile: Path
    base: str | None = None


def base_tag() -> str:
    return f"{REGISTRY}/desktop:{TAG_VERSION}"


def _flavour(name: str, summary: str, dockerfile: Path) -> Flavour:
    return Flavour(name=name, summary=summary, dockerfile=dockerfile, base=base_tag())


FLAVOURS: dict[str, Flavour] = {
    "base": _flavour(
        "base",
        "Bare Debian with X, openbox and the viewer. Bring your own packages.",
        IMAGE_ROOT / "Dockerfile",
    ),
    "firefox": _flavour(
        "firefox",
        "Base plus Firefox ESR and its fonts. For web UIs that behave better in Firefox.",
        IMAGE_ROOT / "flavours" / "firefox" / "Dockerfile",
    ),
    "chromium": _flavour(
        "chromium",
        "Base plus Chromium and a chromium-desk wrapper (sandbox on, dev-shm workaround).",
        IMAGE_ROOT / "flavours" / "chromium" / "Dockerfile",
    ),
}


class UnknownFlavour(ValueError):
    """The caller asked for a flavour that does not exist."""


def names() -> list[str]:
    return sorted(FLAVOURS)


def get(name: str) -> Flavour:
    try:
        return FLAVOURS[name]
    except KeyError:
        raise UnknownFlavour(
            f"unknown flavour {name!r}; choose one of: {', '.join(names())}"
        ) from None


def tag_for(name: str) -> str:
    return base_tag() if name == "base" else f"{REGISTRY}/desktop-{name}:{TAG_VERSION}"
