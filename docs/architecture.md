# Architecture

One Python package, three published desktop images, one container runtime. Nothing runs when no
desktop exists.

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

## Images

The built-in flavours are OCI image references (`base`, `firefox`, `chromium`) under
`ghcr.io/nhermosilla14/agent-deskbench`, redirected at call time by `DESKBENCH_REGISTRY`. `new`
pulls a missing reference and never builds. `image/` and `image/flavours/*` are the build inputs for
`task image` and the publishing pipeline, not a runtime dependency.

## Module map

| Module | Role |
|---|---|
| `deskbench.cli` | argument parsing and the verb implementations |
| `deskbench.engine` | the only module that talks to Podman |
| `deskbench.flavours` | built-in image references, registry override and reference validation |
| `deskbench.sessions` | naming, URL derivation, size parsing |
| `deskbench.lock` | tray singleton and liveness via a lifetime-held flock |
| `deskbench.tray` | GTK/AppIndicator icon, menu, event loop, flock |
| `deskbench.notify` | `ask`: notification with actions, blocking until done |

## Boundaries

- The container is the only isolated unit; the host shares its kernel with it.
- The CLI never builds an image: it pulls according to `--pull`. Images are produced by `task image`
  locally and by the publishing workflow on a release.
- Inside the container everything runs as `agent` (uid 1000). `--userns=keep-id:uid=1000` maps that
  uid to whoever invoked the tool, so bind-mounted files keep their ownership in both directions and
  host files never come back owned by a subuid.
- `sudo` inside the container escalates to the namespace root, which is not the host root: it cannot
  touch host files the invoking user does not already own.
- The viewer port is published on `127.0.0.1` only.
- The tray and the CLI share no state and never call each other; both read Podman.
