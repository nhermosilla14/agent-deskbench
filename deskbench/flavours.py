"""Desktop flavours as OCI image references.

A flavour is the choice of image a desktop starts from. Built-in flavours resolve to fully
qualified references under a registry that ``DESKBENCH_REGISTRY`` can redirect at call time, so a
development or test run can use locally built images. A user flavour is a directory under the
user config directory whose ``flavour.toml`` names the image, so a flavour can be added without
editing the project. References are validated here before they reach the container runtime.
"""

from __future__ import annotations

import os
import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_REGISTRY = "ghcr.io/nhermosilla14/agent-deskbench"
TAG_VERSION = "1"
EXAMPLE_IMAGE = f"{DEFAULT_REGISTRY}/desktop:{TAG_VERSION}"
FLAVOURS_ENV = "DESKBENCH_FLAVOURS_DIR"
XDG_ENV = "XDG_CONFIG_HOME"
MANIFEST_NAME = "flavour.toml"
USER_SUMMARY = "User-defined flavour"

_TAG = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9._-]{0,127}$")
_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
_WHITESPACE = re.compile(r"\s")
_FLAVOUR_NAME = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,29}[a-z0-9])?$")

_MANIFEST_KEYS = frozenset({"image", "summary"})

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


class ManifestError(ValueError):
    """A user flavour's directory name or manifest is not usable."""


@dataclass(frozen=True)
class Flavour:
    """One flavour: the name a caller uses and the image it starts."""

    name: str
    summary: str
    image: str
    source: str = "builtin"


@dataclass(frozen=True)
class ManifestProblem:
    """A candidate flavour that was skipped, and why."""

    path: Path
    message: str


@dataclass(frozen=True)
class Discovery:
    """What the built-in registry and the user directory together provide."""

    flavours: list[Flavour]
    problems: list[ManifestProblem] = field(default_factory=list)


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
    """Return the built-in flavour names, and only those."""
    return sorted(_BUILTINS)


def flavours_dir() -> Path:
    """Return the directory searched for user flavours, without creating it.

    ``DESKBENCH_FLAVOURS_DIR`` wins when set, then ``$XDG_CONFIG_HOME``, then ``~/.config``. A
    blank override is an error: silently ignoring it would read a different directory than the
    caller asked for.
    """
    explicit = os.environ.get(FLAVOURS_ENV)
    if explicit is not None:
        value = explicit.strip()
        if not value:
            raise FlavourConfigError(
                f"{FLAVOURS_ENV} is set but blank; point it at a flavours directory, or unset it"
            )
        return Path(value).expanduser()

    xdg = os.environ.get(XDG_ENV)
    if xdg is not None and xdg.strip():
        return Path(xdg.strip()).expanduser() / "agent-deskbench" / "flavours"
    return Path.home() / ".config" / "agent-deskbench" / "flavours"


def manifest_path(name: str) -> Path:
    """Return where the manifest for ``name`` would live."""
    return flavours_dir() / name / MANIFEST_NAME


def validate_flavour_name(name: str) -> str:
    """Return ``name`` if it is a legal flavour directory name, else raise.

    The rule matches desktop names: 1-31 lowercase letters, digits or hyphens, starting and
    ending with a letter or digit.
    """
    if not _FLAVOUR_NAME.match(name):
        raise ManifestError(
            f"invalid flavour name {name!r}: use 1-31 lowercase letters, digits or hyphens, "
            "starting and ending with a letter or digit"
        )
    return name


def _builtin(name: str) -> Flavour:
    image_name, summary = _BUILTINS[name]
    return Flavour(
        name=name,
        summary=summary,
        image=f"{registry()}/{image_name}:{TAG_VERSION}",
    )


def _read_manifest(path: Path) -> tuple[str, str | None]:
    """Parse and validate one manifest, raising :class:`ManifestError` without the path.

    The caller adds the path: discovery reports it separately, and ``get`` prefixes the error.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ManifestError(f"cannot read the manifest: {exc}") from exc
    try:
        document = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        raise ManifestError(f"invalid TOML: {exc}") from exc

    unknown = sorted(set(document) - _MANIFEST_KEYS)
    if unknown:
        keys = ", ".join(repr(key) for key in unknown)
        raise ManifestError(
            f"unknown key{'s' if len(unknown) > 1 else ''} {keys}; "
            "this version accepts only 'image' and 'summary'"
        )
    if "image" not in document:
        raise ManifestError("missing required key 'image'")

    image = document["image"]
    if not isinstance(image, str):
        raise ManifestError(f"'image' must be a string, not {type(image).__name__}")
    try:
        image = validate_image_ref(image)
    except InvalidImage as exc:
        raise ManifestError(str(exc)) from None

    summary = document.get("summary")
    if summary is not None and not isinstance(summary, str):
        raise ManifestError(f"'summary' must be a string, not {type(summary).__name__}")
    return image, summary


def _shadow_message(name: str) -> str:
    return (
        f"flavour name {name!r} shadows the built-in flavour; "
        "rename or remove the directory"
    )


def discover() -> Discovery:
    """Return the built-in flavours plus every valid user flavour, with problems reported.

    A candidate is an immediate, non-hidden subdirectory holding a ``flavour.toml``. One bad
    candidate never hides the others: its problem is returned alongside the usable flavours.
    """
    found: dict[str, Flavour] = {name: _builtin(name) for name in names()}
    problems: list[ManifestProblem] = []

    directory = flavours_dir()
    if not directory.is_dir():
        if os.environ.get(FLAVOURS_ENV) is not None:
            problems.append(
                ManifestProblem(
                    directory,
                    f"{FLAVOURS_ENV} points at a directory that does not exist",
                )
            )
        return Discovery(
            flavours=sorted(found.values(), key=lambda item: item.name),
            problems=problems,
        )

    for entry in sorted(directory.iterdir()):
        if entry.name.startswith(".") or not entry.is_dir():
            continue
        manifest = entry / MANIFEST_NAME
        if not manifest.is_file():
            continue
        try:
            name = validate_flavour_name(entry.name)
            if name in _BUILTINS:
                raise ManifestError(_shadow_message(name))
            image, summary = _read_manifest(manifest)
        except ManifestError as exc:
            problems.append(ManifestProblem(manifest, str(exc)))
            continue
        found[name] = Flavour(
            name=name,
            summary=summary if summary is not None else USER_SUMMARY,
            image=image,
            source="user",
        )

    return Discovery(
        flavours=sorted(found.values(), key=lambda item: item.name),
        problems=problems,
    )


def available_names() -> list[str]:
    """Return every flavour name that resolves right now."""
    return [flavour.name for flavour in discover().flavours]


def get(name: str) -> Flavour:
    """Resolve ``name`` to a built-in or user flavour.

    A user directory that shadows a built-in is an error rather than a silent fallback, so the
    caller learns that the flavour they configured is not the one that would start.
    """
    if name in _BUILTINS:
        manifest = manifest_path(name)
        if manifest.is_file():
            raise ManifestError(f"{manifest}: {_shadow_message(name)}")
        return _builtin(name)

    validate_flavour_name(name)
    manifest = manifest_path(name)
    if not manifest.is_file():
        raise UnknownFlavour(
            f"unknown flavour {name!r}; choose one of: {', '.join(available_names())}"
        )
    try:
        image, summary = _read_manifest(manifest)
    except ManifestError as exc:
        raise ManifestError(f"{manifest}: {exc}") from None
    return Flavour(
        name=name,
        summary=summary if summary is not None else USER_SUMMARY,
        image=image,
        source="user",
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
