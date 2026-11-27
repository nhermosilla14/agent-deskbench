# Vision

## Purpose

Give a coding agent graphical desktops of its own on the developer's machine, so GUI applications
can be built and exercised without the agent ever touching the human's mouse, keyboard or screen,
while leaving the human a cheap way to look in and type whenever the agent needs them.

## Users

- **The agent** (primary): an LLM coding agent that needs a real X display to launch, screenshot and
  drive a GUI application, and needs to know when a human has taken over.
- **The developer** (secondary): wants to watch, take over, and be interrupted only when necessary.

## Goals

1. One command creates a disposable desktop; it is reachable from a browser with full input.
2. The human can attach to any running desktop at any time, without disturbing the agent.
3. The agent can ask for a human and block until the human says they are done.
4. Between sessions the machine has no extra processes and no tray icon.
5. Podman is the only state store; there is no daemon, no database and no privileged helper.
6. Every behaviour is provable through the CLI, which is the only supported entry point.
7. A flavour is an OCI image reference: a developer can add one under the user config directory,
   and any image that satisfies the viewer, screenshot and shell contract can run.

## Non-goals

- Multi-user, remote or LAN access, and TLS termination.
- Windows or macOS guests.
- GPU passthrough or 3D acceleration.
- A virtual-machine backend (kept possible, not built).
- An in-container control daemon for semantic (AT-SPI) automation; the agent uses `exec` and `shot`.
- Managing the application under test: no build, no dependency installation, no test runner.

## Success criteria

- From a cold start, an agent goes from no desktop to a screenshot of its own application in under
  15 seconds, having typed nothing but `deskbench new` and `deskbench shot`, once the image is local
  (the first pull is a one-time cost).
- A release publishes the built-in images, so a fresh machine needs no local build.
- Stopping the last desktop leaves zero `deskbench` processes and zero containers.
- A human takes over a running session in one click and hands it back in one click.
- The end-to-end suite runs against real Podman and passes unattended.

## Constraints

- Rootless Podman on the developer's machine; no root, no system services installed.
- No third-party Python packages: the host may not have a working package index.
- The panel is a StatusNotifierItem host (KDE Plasma is the reference environment).
- The desktop image must build from distribution packages only, with no external apt repositories.
- The CLI pulls images; building belongs to maintainers (`task image`, `task publish`) and the
  release workflow.
