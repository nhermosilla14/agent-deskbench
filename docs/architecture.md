# Architecture

One Python package, one container image, one container runtime. Nothing runs when no desktop exists.

```
agent ──shell──► deskbench CLI ──podman──► desktop container ──► app under test
                      │                          ▲
                      │ spawns (first only)      │ noVNC over one port
                      ▼                          │
                  tray process ──xdg-open──► browser viewer
                      ▲
   human ──notifications──┘
```

Open [`diagrams/agent-desktop-flow.html`](diagrams/agent-desktop-flow.html) for the explorable
version.

## Processes

| Process | Lifetime | Responsibility |
|---|---|---|
| `deskbench` (CLI) | one invocation | create, list, exec, capture, stop; spawns the tray on first desktop |
| `deskbench tray` | first desktop → last desktop | StatusNotifierItem, menu, refresh on Podman events, exit at zero |
| `podman` | always | container lifecycle and the authoritative list of desktops |
| desktop container | per desktop | `Xvnc` + `openbox` + `websockify`/noVNC |

## State

There is no local state. `podman ps --filter label=deskbench=1` is the list of desktops; the
container's published port is the viewer URL; the container name is the desktop name. A tray process
that outlives its containers is impossible to observe as stale: it recounts on every event and exits
at zero.

## Module map

| Module | Role |
|---|---|
| `deskbench.cli` | argument parsing and the verb implementations |
| `deskbench.engine` | the only module that talks to Podman |
| `deskbench.sessions` | naming, URL derivation, size parsing |
| `deskbench.tray` | GTK/AppIndicator icon, menu, event loop, flock |
| `deskbench.notify` | `ask`: notification with actions, blocking until done |

## Boundaries

- The container is the only isolated unit; the host shares its kernel with it.
- The viewer port is published on `127.0.0.1` only.
- The tray and the CLI share no state and never call each other; both read Podman.
