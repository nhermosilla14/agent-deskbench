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
| `deskbench` (CLI) | one invocation | create, list, exec, capture, run terminal sessions, probe capabilities, stop; spawns the tray on first desktop |
| `deskbench tray` | first desktop → last desktop | StatusNotifierItem, menu (viewer, terminals, private shell, settings), refresh on Podman events, exit at zero |
| `podman` | always | container lifecycle and the authoritative list of desktops |
| desktop container | per desktop | `Xvnc` + `openbox` + `websockify`/noVNC |

## State

There is no local state. `podman ps --filter label=deskbench=1` is the list of desktops and the
container name is the desktop name. The container also carries the resolved contract as labels:
`deskbench.viewer.port`, `deskbench.viewer.path`, `deskbench.viewer.scheme`,
`deskbench.screenshot` (compact JSON with `command` and `settle`) and `deskbench.run.user`. `ls`,
`url`, `exec` and `shot` read them, so a manifest edited later cannot mutate a running desktop.
Containers without those labels fall back to the built-in layout (port 6080, the noVNC path,
`http`, user `1000:1000`) and, for screenshots, to probing the image for `deskbench-capture`,
`scrot` or `import`.

Terminal sessions are state too, and they live inside the container: a tmux server owned by the
container's run user holds them and dies with the `--rm` container. Nothing on the host records which
sessions exist; `term list` asks tmux, so a session cannot survive its desktop and a stale host file
cannot invent one. Capabilities are the opposite kind of fact: they are probed on every
`capabilities` call and whenever `term start` needs tmux, because an agent can install into a
container at any time and a recorded answer would go stale. Only facts frozen at creation — the
viewer, the screenshot command, the run user, the flavour name — are labels.

The one host file is the user's preferences, `$XDG_CONFIG_HOME/agent-deskbench/settings.toml`, beside
the flavour manifests. It holds a preference that cannot be derived from the runtime (today, the
default grid for tray-started terminals), never desktop state, and the tray is its only writer. The
desktop rule above is unchanged: a preference cannot invent a desktop, list one or outlive one.

## Images

The built-in flavours are OCI image references (`base`, `firefox`, `chromium`) under
`ghcr.io/nhermosilla14/agent-deskbench`, redirected at call time by `DESKBENCH_REGISTRY`. `new`
pulls a missing reference and never builds. `image/` and `image/flavours/*` are the build inputs for
`task image` and the publishing pipeline, not a runtime dependency. The base image ships `tmux` from
Debian so every built-in satisfies the terminal contract; a third-party image may not, which is why
`term start` probes before it starts and `capabilities` reports the package managers that image
actually has.

User flavours live in `$XDG_CONFIG_HOME/agent-deskbench/flavours/<name>/flavour.toml` (default
`~/.config/...`, overridable with `DESKBENCH_FLAVOURS_DIR`). Each manifest names one image reference,
an optional summary, and optional `[viewer]`, `[run]` and `[screenshot]` tables describing a
third-party image's contract: `port`, `path`, `scheme` and `timeout` for the viewer; `user`,
`entrypoint`, `command` and `env` for the process, with `{width}`/`{height}` substituted from
`--size`; and a capture `command` with `{output}`/`{settle}` placeholders plus a `settle` flag. A
command-less flavour resolves `deskbench-capture`, `scrot` or `import` from the image. `new` probes
the shell and the screenshot before reporting success and removes the container when either fails.
`flavours.discover()` merges valid manifests with the built-ins for `images`, reporting bad
candidates as problems, and `get()` resolves a user name at `new` time. A directory that shadows a
built-in is an error.

## Publishing

A release publishes the built-ins. `.github/workflows/publish.yml` runs on `v*` tags and manual
dispatch; it logs in with `GITHUB_TOKEN` (`packages: write`), derives the tags with
`scripts/image-tags.sh`, and pushes the base then Firefox and Chromium with `BASE` set to it. Each
image gets `:X.Y.Z`, `:X.Y`, `:X`, `:latest` and `:sha-<short>`; `:X` is the moving major line the
CLI resolves. Pull requests touching `image/**` or the publish scripts build all three without
pushing. `task publish REGISTRY=... VERSION=...` does the same locally through Podman. The mapping
lives only in `scripts/image-tags.sh`, shared by the workflow, the task and the tests.

## Module map

| Module | Role |
|---|---|
| `deskbench.cli` | argument parsing and the verb implementations |
| `deskbench.engine` | the only module that talks to Podman |
| `deskbench.flavours` | built-in and user flavour discovery, manifests, registry override and reference validation |
| `deskbench.sessions` | naming, URL derivation, size parsing |
| `deskbench.term` | tmux argument builders, grid rules and the session-list parser, with no I/O |
| `deskbench.capabilities` | the live probe script, its report parser and the install-route message, with no I/O |
| `deskbench.hostterm` | terminal-emulator lookup and the argv to run a command in one, with no I/O |
| `deskbench.settings` | the XDG preferences file: read, validate, atomic write |
| `deskbench.lock` | tray singleton and liveness via a lifetime-held flock |
| `deskbench.tray` | GTK/AppIndicator icon, worker polling, menu rendering, settings dialog, flock |
| `deskbench.tray_menu` | the tray's menu content as data, plus the signature that decides a rebuild |
| `deskbench.settings_window` | the GTK dialog that edits the user's settings |
| `deskbench.notify` | `ask`: notification with actions, blocking until done |

## Boundaries

- The container is the only isolated unit; the host shares its kernel with it.
- The CLI never builds an image: it pulls according to `--pull`. Images are produced by `task image`
  locally and by the publishing workflow on a release.
- Inside a built-in image everything runs as `agent` (uid 1000). A manifest may set `[run].user` to
  another uid; the runtime maps that uid to whoever invoked the tool, so bind-mounted files keep
  their ownership in both directions only when the configured uid matches the host mapping.
- `sudo` inside the container escalates to the namespace root, which is not the host root: it cannot
  touch host files the invoking user does not already own.
- The viewer port is published on `127.0.0.1` only.
- The tray and the CLI share no state and never call each other; both read Podman. The tray spawns
  processes only through the same functions the CLI uses (`xdg-open` for the viewer, the attach path
  for a terminal), and writes exactly one host file, the user's settings.
