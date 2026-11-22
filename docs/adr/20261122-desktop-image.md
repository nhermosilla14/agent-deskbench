# Desktop image: TigerVNC plus openbox plus noVNC on one published port

- Status: Accepted
- Date: 2026-11-22
- Deciders: Nicolás Hermosilla Polanco
- Approved by: Nicolás Hermosilla Polanco

## Context

The desktop needs an X server with no physical display, a window manager so that focus and dialogs
behave, and a viewer a human can open in a browser without installing anything. The obvious stack is
`Xvfb` + a VNC server + (optionally) a WebSocket bridge, which is two or three processes and two
ports.

KasmVNC collapses this to one process and one port (it is an X server that also serves its own web
client), and it handles clipboard and dynamic resize better. It is, however, distributed from an
external apt repository maintained by Kasm, which adds a third-party trust and availability
dependency to every image build.

## Decision

Build on Debian slim with distribution packages only: `tigervnc-standalone-server` (`Xvnc` as the X
server), `openbox` as the window manager, and `novnc` served by `websockify`. Publish **one** port,
`6080`, which serves the browser viewer; `Xvnc` listens on the container's loopback only. VNC
authentication is disabled because the port is bound to `127.0.0.1` on the host.

The entrypoint runs the three processes directly as root inside the container; Podman's rootless
mapping keeps them unprivileged on the host.

## Alternatives considered

- **KasmVNC** — fewer processes, better viewer. Rejected for now because of the external apt
  repository; revisit if viewer quality becomes the limiting factor.
- **`Xvfb` + `x11vnc` + `websockify`** — three processes and no ability to resize the screen at
  runtime; `Xvnc` gives the same footprint with resize support.
- **Publishing both the VNC and the web port** — a native client is not the primary path, and every
  extra published port is another thing to bind correctly.

## Consequences

The image builds offline-reproducibly from a Debian mirror. A human who wants a native VNC client
must use the browser viewer or `podman exec` a client inside the container; this is a deliberate
trade. Dynamic resize works, clipboard is limited by noVNC.
