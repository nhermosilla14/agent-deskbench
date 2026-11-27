"""The live capability probe and the install-route message. Pure functions, no I/O.

The probe is one shell script run inside the desktop. Its output is parsed here, and the
message for a missing tool is built from that report, so no route assumes a distribution.
"""

from __future__ import annotations

PROBE_SCRIPT = """\
for tool in sh sudo tmux scrot import deskbench-capture apt-get dnf zypper apk pacman brew; do
  printf '%s\\t%s\\n' "$tool" "$(command -v "$tool" 2>/dev/null)"
done
if command -v sudo >/dev/null 2>&1 && sudo -n true >/dev/null 2>&1; then
  check=sudo
  probe="sudo -n test -w /usr"
else
  check=user
  probe="test -w /usr"
fi
if $probe; then writable=yes; else writable=no; fi
printf 'write\\t%s\\t%s\\n' "$check" "$writable"
"""

PACKAGE_MANAGERS = ("apt-get", "dnf", "zypper", "apk", "pacman", "brew")
SCREENSHOT_TOOLS = ("deskbench-capture", "scrot", "import")

# Native managers in preference order, each with the command that installs tmux.
NATIVE_INSTALL = {
    "apt-get": "sudo apt-get update && sudo apt-get install -y tmux",
    "dnf": "sudo dnf install -y tmux",
    "zypper": "sudo zypper install -y tmux",
    "apk": "sudo apk add tmux",
    "pacman": "sudo pacman -S --noconfirm tmux",
}


def parse_report(text: str) -> dict:
    """Turn the probe's output into the ``capabilities`` report.

    Raises ``ValueError`` when the output lacks the privileged-write line, which means the probe
    did not run to the end.
    """
    found: dict[str, str] = {}
    write: list[str] | None = None
    for line in text.splitlines():
        fields = line.split("\t")
        if fields[0] == "write" and len(fields) == 3:
            write = fields
        elif len(fields) == 2:
            found[fields[0]] = fields[1]
    if write is None:
        raise ValueError("could not read the capability report from the desktop")

    def path(tool: str) -> str | None:
        return found.get(tool) or None

    screenshot = next((path(tool) for tool in SCREENSHOT_TOOLS if path(tool)), None)
    return {
        "shell": path("sh"),
        "screenshot": screenshot,
        "tmux": path("tmux"),
        "sudo": path("sudo"),
        "package_managers": {manager: path(manager) for manager in PACKAGE_MANAGERS},
        "privileged_write": {"possible": write[2] == "yes", "measured_with": write[1]},
    }


def tmux_install_message(report: dict, where: str) -> str:
    """Say how to install tmux in ``where`` (a flavour or image, already named), from the report."""
    managers = report["package_managers"]
    native = next((name for name in NATIVE_INSTALL if managers.get(name)), None)
    privileged = report["privileged_write"]["possible"]
    measured = report["privileged_write"]["measured_with"]

    if native and privileged:
        route = f"install it with the image's native manager: {NATIVE_INSTALL[native]}"
    elif managers.get("brew"):
        if native:
            reason = (
                f"{native} is present but the root filesystem is not writable "
                f"(checked with {measured})"
            )
        else:
            reason = "the image has no native package manager"
        route = f"{reason}; use Homebrew instead: brew install tmux"
    else:
        route = (
            "the image cannot install packages the usual way: no native package manager can "
            "write to the root filesystem and there is no brew; tmux must come from the image itself"
        )
    return f"tmux is missing in {where} (capability: tmux, needed by term start); {route}"
