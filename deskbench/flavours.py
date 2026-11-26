"""Built-in desktop flavours as OCI image references.

A flavour is the choice of image a desktop starts from. Built-in flavours resolve to fully
qualified references under a registry that ``DESKBENCH_REGISTRY`` can redirect at call time, so a
development or test run can use locally built images. References are validated here before they
reach the container runtime.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass

DEFAULT_REGISTRY = "ghcr.io/nhermosilla14/agent-deskbench"
TAG_VERSION = "1"
EXAMPLE_IMAGE = f"{DEFAULT_REGISTRY}/desktop:{TAG_VERSION}"

_TAG = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9._-]{0,127}$")
_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
_WHITESPACE = re.compile(r"\s")

# name -> (image name under the registry, summary)
_BUILTINS: dict[str, tuple[str, str]] = {
    "base": (
        "desktop",
        "Bare Debian with X, openbox and the viewer. Bring your own packages.",
    ),
    "firefox": (
        "desktop-firefox",
        "Base plus Firefox ESR and its fonts. For web UIs that behave better in Firefox.",
    ),
    "chromium": (
        "desktop-chromium",
        "Base plus Chromium and a chromium-desk wrapper (sandbox on, dev-shm workaround).",
    ),
}


class UnknownFlavour(ValueError):
    """The caller asked for a flavour that does not exist."""


class InvalidImage(ValueError):
    """A caller-supplied image reference is not a fully qualified OCI reference."""


class FlavourConfigError(ValueError):
    """The flavour configuration in the environment is unusable."""


@dataclass(frozen=True)
class Flavour:
    """One built-in flavour: the name a caller uses and the image it starts."""

    name: str
    summary: str
    image: str
    source: str = "builtin"


def registry() -> str:
    """Return the registry prefix for built-in flavours.

    Read from ``DESKBENCH_REGISTRY`` on every call; the environment is the configuration. A blank
    value is an error instead of a silent fallback, so a typo cannot pull from somewhere
    unexpected.
    """
    value = os.environ.get("DESKBENCH_REGISTRY")
    if value is None:
        return DEFAULT_REGISTRY
    value = value.strip().rstrip("/")
    if not value:
        raise FlavourConfigError(
            "DESKBENCH_REGISTRY is set but blank; set it to a registry prefix such as "
            f"{DEFAULT_REGISTRY}, or unset it"
        )
    return value


def names() -> list[str]:
    return sorted(_BUILTINS)


def get(name: str) -> Flavour:
    try:
        image_name, summary = _BUILTINS[name]
    except KeyError:
        raise UnknownFlavour(
            f"unknown flavour {name!r}; choose one of: {', '.join(names())}"
        ) from None
    return Flavour(
        name=name,
        summary=summary,
        image=f"{registry()}/{image_name}:{TAG_VERSION}",
    )


def _invalid(value: str, problem: str) -> InvalidImage:
    return InvalidImage(
        f"invalid image reference {value!r}: {problem}; "
        f"expected a fully qualified reference such as {EXAMPLE_IMAGE}"
    )


def validate_image_ref(value: str) -> str:
    """Return ``value`` if it is a fully qualified OCI reference with a tag or digest.

    A fully qualified reference starts with a registry host (a component containing a dot or a
    colon, or ``localhost``), includes at least one slash, and ends in a tag or a ``sha256``
    digest. Short names such as ``debian:12`` are rejected because the registry would be
    ambiguous.
    """
    if not value or not value.strip():
        raise _invalid(value, "the reference is empty")
    if _WHITESPACE.search(value):
        raise _invalid(value, "whitespace is not allowed")

    host, separator, remainder = value.partition("/")
    if not separator:
        raise _invalid(value, "a registry host and repository are required")
    if not (host == "localhost" or "." in host or ":" in host):
        raise _invalid(value, f"{host!r} is not a registry host")

    name_part, at, digest = remainder.partition("@")
    if at and not _DIGEST.match(digest):
        raise _invalid(
            value,
            f"digest {digest!r} is malformed (expected sha256:<64 lowercase hex>)",
        )

    slash = name_part.rfind("/")
    colon = name_part.rfind(":")
    tag = None
    if colon > slash:
        name_part, tag = name_part[:colon], name_part[colon + 1:]
        if not _TAG.match(tag):
            raise _invalid(value, f"tag {tag!r} is not valid")

    if not name_part:
        raise _invalid(value, "the repository is empty")
    if tag is None and not at:
        raise _invalid(value, "a tag or digest is required")
    return value
