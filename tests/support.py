"""Shared helpers for the container-backed tests."""

from __future__ import annotations

import atexit
import contextlib
import io
import json
import os
import shutil
import tempfile
import unittest
import zlib
from pathlib import Path

from deskbench import cli

_EMPTY_FLAVOURS: str | None = None


def _empty_flavours_dir() -> str:
    """A persistent empty directory, so container tests ignore the developer's flavours."""
    global _EMPTY_FLAVOURS
    if _EMPTY_FLAVOURS is None:
        _EMPTY_FLAVOURS = tempfile.mkdtemp(prefix="deskbench-e2e-flavours-")
        atexit.register(shutil.rmtree, _EMPTY_FLAVOURS, True)
    return _EMPTY_FLAVOURS


def png_colour_count(path: str | Path, max_rows: int = 400) -> int:
    """Number of distinct pixel colours in the top rows of an 8-bit PNG.

    A screenshot of a blank desktop is one colour; anything drawn adds more. Kept in the test
    suite so asserting "something was actually rendered" needs no image library.
    """
    data = Path(path).read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("not a PNG")
    pos = 8
    width = height = depth = colour_type = None
    idat = bytearray()
    while pos < len(data):
        length = int.from_bytes(data[pos:pos + 4], "big")
        kind = data[pos + 4:pos + 8]
        chunk = data[pos + 8:pos + 8 + length]
        if kind == b"IHDR":
            width = int.from_bytes(chunk[0:4], "big")
            height = int.from_bytes(chunk[4:8], "big")
            depth, colour_type = chunk[8], chunk[9]
        elif kind == b"IDAT":
            idat += chunk
        elif kind == b"IEND":
            break
        pos += 12 + length
    if depth != 8 or colour_type not in (2, 6):
        raise ValueError(f"unsupported PNG: depth={depth} colour type={colour_type}")

    raw = zlib.decompress(bytes(idat))
    bytes_per_pixel = 3 if colour_type == 2 else 4
    stride = width * bytes_per_pixel
    previous = bytearray(stride)
    colours: set[bytes] = set()
    offset = 0
    for _ in range(min(height, max_rows)):
        filter_type = raw[offset]
        offset += 1
        line = bytearray(raw[offset:offset + stride])
        offset += stride
        if filter_type == 1:
            for i in range(bytes_per_pixel, stride):
                line[i] = (line[i] + line[i - bytes_per_pixel]) & 0xFF
        elif filter_type == 2:
            for i in range(stride):
                line[i] = (line[i] + previous[i]) & 0xFF
        elif filter_type == 3:
            for i in range(stride):
                left = line[i - bytes_per_pixel] if i >= bytes_per_pixel else 0
                line[i] = (line[i] + ((left + previous[i]) >> 1)) & 0xFF
        elif filter_type == 4:
            for i in range(stride):
                a = line[i - bytes_per_pixel] if i >= bytes_per_pixel else 0
                b = previous[i]
                c = previous[i - bytes_per_pixel] if i >= bytes_per_pixel else 0
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                predictor = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                line[i] = (line[i] + predictor) & 0xFF
        for i in range(0, stride, bytes_per_pixel):
            colours.add(bytes(line[i:i + bytes_per_pixel]))
            if len(colours) > 1:
                return len(colours)
        previous = line
    return len(colours)


def e2e_skip_reason() -> str | None:
    """Return why a container test cannot run, or ``None`` when it can.

    When the suite is enabled, point the built-in flavours at the locally built images
    (``localhost/agent-deskbench``) unless the caller already chose a registry, so container
    tests are hermetic and never pull from the published registry.
    """
    if os.environ.get("DESKBENCH_E2E") != "1":
        return "set DESKBENCH_E2E=1 to run the container tests"
    os.environ.setdefault("DESKBENCH_REGISTRY", "localhost/agent-deskbench")
    os.environ.setdefault("DESKBENCH_FLAVOURS_DIR", _empty_flavours_dir())
    if shutil.which("podman") is None:
        return "podman is not installed"
    return None


def call(*argv: str) -> tuple[int, str, str]:
    """Run the CLI in-process and return (code, stdout, stderr)."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = cli.main(list(argv))
    return code, out.getvalue(), err.getvalue()


class ContainerTest(unittest.TestCase):
    """One desktop per test class, started through the public interface and always cleaned up."""

    desktop = "e2e"
    size = "1024x768"

    @classmethod
    def setUpClass(cls) -> None:
        reason = e2e_skip_reason()
        if reason:
            raise unittest.SkipTest(reason)
        call("stop", cls.desktop)  # left over from a crashed run
        code, out, err = call("new", "--name", cls.desktop, "--size", cls.size)
        if code != 0:
            raise unittest.SkipTest(f"could not start {cls.desktop}: {err.strip() or out.strip()}")
        cls.created = json.loads(out)

    @classmethod
    def tearDownClass(cls) -> None:
        call("stop", cls.desktop)
