"""Desktop flavours as OCI image references.

A flavour is the choice of image a desktop starts from, plus the contract that image satisfies:
where its viewer is and which user, argv and environment it needs. Built-in flavours resolve to
fully qualified references under a registry that ``DESKBENCH_REGISTRY`` can redirect at call
time, so a development or test run can use locally built images. A user flavour is a directory
under the user config directory whose ``flavour.toml`` describes the image and any differences
from the built-in contract, so a third-party image can be added without editing the project.
References and contract values are validated here before they reach the container runtime.
"""

from __future__ import annotations

import os
import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from . import sessions

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

_MANIFEST_KEYS = frozenset({"image", "summary", "viewer", "run", "screenshot"})
_VIEWER_KEYS = frozenset({"port", "path", "scheme", "timeout"})
_RUN_KEYS = frozenset({"user", "entrypoint", "command", "env"})
_SCREENSHOT_KEYS = frozenset({"command", "settle"})
CAPTURE_COMMAND = ("/usr/local/bin/deskbench-capture", "{output}", "{settle}")
_SCHEMES = ("http", "https")
_MAX_ID = 2**31 - 1

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
class Viewer:
    """Where a desktop's HTTP viewer listens inside the container.

    The defaults reproduce the built-in image, so a manifest only states what differs.
    """

    port: int = sessions.WEB_PORT
    path: str = sessions.DEFAULT_VIEWER_PATH
    scheme: str = "http"
    timeout: int = 30


@dataclass(frozen=True)
class Run:
    """The identity, argv and environment a desktop's process needs.

    ``user`` is ``uid:gid`` inside the container and is also the identity used for ``exec``.
    ``{width}`` and ``{height}`` in an environment value are replaced with the requested size.
    """

    user: str = "1000:1000"
    entrypoint: tuple[str, ...] = ()
    command: tuple[str, ...] = ()
    env: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class Screenshot:
    """How to capture a desktop's screen.

    ``command`` is an argv with ``{output}`` and ``{settle}`` placeholders. ``settle`` says
    whether ``shot`` should capture until two frames match; ``None`` uses the manifest default.
    A flavour without a command resolves one of the tools the image is known to ship.
    """

    command: tuple[str, ...] | None = None
    settle: bool | None = None


@dataclass(frozen=True)
class Flavour:
    """One flavour: the name a caller uses, the image it starts and its desktop contract."""

    name: str
    summary: str
    image: str
    source: str = "builtin"
    viewer: Viewer = field(default_factory=Viewer)
    run: Run = field(default_factory=Run)
    screenshot: Screenshot = field(default_factory=Screenshot)


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
        screenshot=Screenshot(command=CAPTURE_COMMAND, settle=False),
    )


def adhoc(image: str) -> Flavour:
    """Return a flavour for a bare ``--image`` reference: the defaults, plus that image."""
    return Flavour(
        name="image",
        summary="",
        image=validate_image_ref(image),
        source="image",
    )


def parse_user(value: str) -> tuple[int, int]:
    """Parse ``uid`` or ``uid:gid`` into a pair of ids.

    Both sides are decimal digits, the gid defaults to the uid, and neither may exceed the
    largest value Linux accepts. Anything else is rejected instead of being handed to the
    runtime, where the failure would be opaque.
    """
    parts = value.split(":")
    if len(parts) > 2:
        raise ValueError(
            f"invalid user {value!r}: expected UID or UID:GID, for example 1000:1000"
        )
    numbers: list[int] = []
    for part in parts:
        if not part.isascii() or not part.isdigit():
            raise ValueError(
                f"invalid user {value!r}: {part!r} is not a non-negative decimal number"
            )
        number = int(part)
        if number > _MAX_ID:
            raise ValueError(f"invalid user {value!r}: ids must not exceed {_MAX_ID}")
        numbers.append(number)
    uid = numbers[0]
    gid = numbers[1] if len(numbers) == 2 else uid
    return uid, gid


def _table(
    document: dict[str, object], key: str, allowed: frozenset[str]
) -> dict[str, object]:
    """Return the ``[key]`` table, rejecting unknown keys so a typo cannot be ignored."""
    table = document.get(key)
    if table is None:
        return {}
    if not isinstance(table, dict):
        raise ManifestError(f"'{key}' must be a table, not {type(table).__name__}")
    unknown = sorted(set(table) - allowed)
    if unknown:
        keys = ", ".join(repr(item) for item in unknown)
        raise ManifestError(
            f"unknown key{'s' if len(unknown) > 1 else ''} {keys} in [{key}]; "
            f"this version accepts only {', '.join(repr(item) for item in sorted(allowed))}"
        )
    return table


def _viewer(table: dict[str, object]) -> Viewer:
    viewer = Viewer()

    port = table.get("port", viewer.port)
    if isinstance(port, bool) or not isinstance(port, int):
        raise ManifestError(f"'viewer.port' must be an integer, not {type(port).__name__}")
    if not 1 <= port <= 65535:
        raise ManifestError(f"'viewer.port' must be between 1 and 65535, not {port}")

    path = table.get("path", viewer.path)
    if not isinstance(path, str):
        raise ManifestError(f"'viewer.path' must be a string, not {type(path).__name__}")
    if not path:
        raise ManifestError("'viewer.path' must not be empty")
    if not path.startswith("/"):
        raise ManifestError(f"'viewer.path' must start with '/': {path!r}")
    if _WHITESPACE.search(path):
        raise ManifestError(f"'viewer.path' must not contain whitespace: {path!r}")

    scheme = table.get("scheme", viewer.scheme)
    if not isinstance(scheme, str):
        raise ManifestError(f"'viewer.scheme' must be a string, not {type(scheme).__name__}")
    if scheme not in _SCHEMES:
        raise ManifestError(
            f"'viewer.scheme' must be one of {', '.join(repr(item) for item in _SCHEMES)}, "
            f"not {scheme!r}"
        )

    timeout = table.get("timeout", viewer.timeout)
    if isinstance(timeout, bool) or not isinstance(timeout, int):
        raise ManifestError(
            f"'viewer.timeout' must be an integer, not {type(timeout).__name__}"
        )
    if timeout < 1:
        raise ManifestError(f"'viewer.timeout' must be at least 1 second, not {timeout}")

    return Viewer(port=port, path=path, scheme=scheme, timeout=timeout)


def _argv(table: dict[str, object], key: str) -> tuple[str, ...]:
    value = table.get(key)
    if value is None:
        return ()
    if not isinstance(value, list):
        raise ManifestError(f"'run.{key}' must be a list of strings, not {type(value).__name__}")
    for index, item in enumerate(value):
        if not isinstance(item, str):
            raise ManifestError(
                f"'run.{key}[{index}]' must be a string, not {type(item).__name__}"
            )
        if not item:
            raise ManifestError(f"'run.{key}[{index}]' must not be empty")
    return tuple(value)


def _env(table: dict[str, object]) -> dict[str, str]:
    value = table.get("env")
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ManifestError(f"'run.env' must be a table, not {type(value).__name__}")
    env: dict[str, str] = {}
    for key, item in value.items():
        if not key:
            raise ManifestError("'run.env' keys must not be empty")
        if "=" in key:
            raise ManifestError(f"'run.env' key {key!r} must not contain '='")
        if not isinstance(item, str):
            raise ManifestError(
                f"'run.env.{key}' must be a string, not {type(item).__name__}"
            )
        env[key] = item
    return env


def _run(table: dict[str, object]) -> Run:
    run = Run()

    user = table.get("user", run.user)
    if not isinstance(user, str):
        raise ManifestError(f"'run.user' must be a string, not {type(user).__name__}")
    try:
        parse_user(user)
    except ValueError as exc:
        raise ManifestError(f"'run.user' is not usable: {exc}") from None

    return Run(
        user=user,
        entrypoint=_argv(table, "entrypoint"),
        command=_argv(table, "command"),
        env=_env(table),
    )


def _screenshot(table: dict[str, object]) -> Screenshot:
    """Validate ``[screenshot]``: an argv with ``{output}`` and an optional settle flag."""
    command = table.get("command")
    settle = table.get("settle")

    if command is None:
        if settle is not None:
            raise ManifestError(
                "'screenshot.settle' requires 'screenshot.command'; "
                "set a command or remove settle"
            )
        return Screenshot()

    if not isinstance(command, list):
        raise ManifestError(
            f"'screenshot.command' must be a list of strings, not {type(command).__name__}"
        )
    if not command:
        raise ManifestError("'screenshot.command' must not be empty")
    for index, item in enumerate(command):
        if not isinstance(item, str):
            raise ManifestError(
                f"'screenshot.command[{index}]' must be a string, not {type(item).__name__}"
            )
        if not item:
            raise ManifestError(f"'screenshot.command[{index}]' must not be empty")
    if not any("{output}" in item for item in command):
        raise ManifestError(
            "'screenshot.command' must contain '{output}' so the capture knows where to write"
        )

    if settle is None:
        settle = True
    elif not isinstance(settle, bool):
        raise ManifestError(
            f"'screenshot.settle' must be a boolean, not {type(settle).__name__}"
        )
    return Screenshot(command=tuple(command), settle=settle)


def _read_manifest(name: str, path: Path) -> Flavour:
    """Parse and validate one manifest into a complete user flavour.

    The path is not part of the error: discovery reports it separately, and ``get`` prefixes it.
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
            "this version accepts only 'image', 'summary', 'viewer', 'run' and 'screenshot'"
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

    return Flavour(
        name=name,
        summary=summary if summary is not None else USER_SUMMARY,
        image=image,
        source="user",
        viewer=_viewer(_table(document, "viewer", _VIEWER_KEYS)),
        run=_run(_table(document, "run", _RUN_KEYS)),
        screenshot=_screenshot(_table(document, "screenshot", _SCREENSHOT_KEYS)),
    )


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
            found[name] = _read_manifest(name, manifest)
        except ManifestError as exc:
            problems.append(ManifestProblem(manifest, str(exc)))
            continue

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
        return _read_manifest(name, manifest)
    except ManifestError as exc:
        raise ManifestError(f"{manifest}: {exc}") from None


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
