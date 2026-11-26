# agent-deskbench

Disposable graphical Linux desktops for a coding agent, on the developer's own machine. The agent
creates and drives a containerised desktop through a CLI; a tray icon appears only while a desktop
exists, so a human can look in and type when the agent asks. Nothing stays resident when idle.

See [`docs/vision.md`](docs/vision.md) for goals, and
[`docs/diagrams/agent-desktop-flow.html`](docs/diagrams/agent-desktop-flow.html) for how the pieces
talk to each other.

## Prerequisites

- Linux with a StatusNotifierItem panel (KDE Plasma or GNOME with the AppIndicator extension).
- Python 3.11 or newer (`3.14` is what it is developed against). No third-party Python packages.
- **Podman (rootless is fine) or Docker**, with the binary on `PATH`. Podman is used when both are
  installed; set `DESKBENCH_RUNTIME=docker` to force Docker. Docker must be rootful for bind mounts
  to keep their ownership.
- `python3-gi` with GTK 3 and `AyatanaAppIndicator3` — only for the tray and notifications.

```sh
sudo apt install podman python3-gi gir1.2-gtk-3.0 gir1.2-ayatanaappindicator3-0.1
```

## Getting started

```sh
git clone git@github.com:nhermosilla14/agent-deskbench.git
cd agent-deskbench
python3 -m deskbench new --name alpha --size 1600x1000   # pulls the base image on first use
```

`new` prints JSON with the desktop name, its viewer URL and the container id. Open the URL in a
browser, or click the tray icon and choose *Open viewer*. The first run pulls the image; `task image`
builds the three images locally if you prefer to avoid the pull.

## Usage

```
deskbench new [--name NAME] [--size WxH] [--flavour F | --image REF] [--pull P]
              [--bind SRC[:DST][:ro]]      start a desktop
deskbench images [--json]                  list image flavours and local presence
deskbench ls [--json]                      list desktops
deskbench url NAME                         print the viewer URL
deskbench exec NAME -- CMD...              run a command inside the desktop
deskbench shot NAME [-o PATH]              capture the desktop to a PNG
deskbench logs NAME [-n N]                 last N lines of the desktop's log
deskbench stop NAME                        stop one desktop
deskbench ask NAME [-t SECONDS] MESSAGE    notify the human and block until they are done
```

### Image flavours

`new --flavour NAME` starts from an image that already carries what your application needs:

```
base      Bare Debian with X, openbox and the viewer (default)
firefox   base + Firefox ESR
chromium  base + Chromium, with a chromium-desk wrapper that adds --disable-dev-shm-usage;
          the renderer sandbox stays on
```

The built-in references live under `ghcr.io/nhermosilla14/agent-deskbench` by default. Set
`DESKBENCH_REGISTRY` to use a local build or a fork. `new` pulls a missing image and never builds;
`--pull=always` refreshes it and `--pull=never` refuses to pull.

```sh
deskbench images                          # what exists, and whether it is present locally
deskbench new --name web --flavour chromium
deskbench new --name custom --image registry.example.com/team/desktop:1
```

#### Adding a flavour

Create a directory under the user config directory whose name is the flavour name, and give it a
`flavour.toml` that names the image:

```toml
# ~/.config/agent-deskbench/flavours/web/flavour.toml
image = "registry.example.com/team/web:1"   # required, fully qualified, tagged or digest
summary = "Our web app image"                # optional
```

`deskbench images` lists it with source `user`, and `deskbench new --flavour web` starts it with the
same pull policy. `DESKBENCH_FLAVOURS_DIR` overrides the directory (otherwise `$XDG_CONFIG_HOME/agent-deskbench/flavours`,
then `~/.config/agent-deskbench/flavours`). A name is 1–31 lowercase letters, digits or hyphens and
may not shadow a built-in. A malformed manifest is reported on stderr by `images` and fails `new`
with the path; a directory without `flavour.toml` is ignored.

A manifest may also describe how the image presents its desktop. Both tables are optional; the
defaults reproduce the built-in image.

```toml
[viewer]                    # where the browser viewer lives inside the container
port = 6080                 # published on 127.0.0.1
path = "/vnc.html?autoconnect=1&resize=scale"
scheme = "http"             # or "https"
timeout = 30                # seconds `new` waits for the viewer to answer

[run]                       # how the desktop process starts, as uid:gid
user = "1000:1000"
entrypoint = ["/usr/local/bin/my-entrypoint"]
command = ["--flag"]
env = { MY_SIZE = "{width}x{height}" }   # {width}/{height} come from --size

[screenshot]                # how `shot` captures the screen
command = ["/usr/local/bin/my-shot", "{output}"]  # {output} required; {settle} optional
settle = true               # capture until two frames match (default: true for custom commands)
```

`new` publishes the configured viewer port, waits for that scheme and path (2xx, 3xx, 401 or 403),
and records the effective port, path, scheme, user and screenshot command as container labels, so
`ls`, `url`, `exec` and `shot` keep the configuration the desktop started with even if the manifest
changes later. Before reporting success, `new` proves the contract inside the container: `sh -lc
true` must succeed and the screenshot command must write a non-empty file. If either probe fails,
`new` removes the container and exits 1 naming the flavour and the missing capability. A
command-less flavour — including a bare `--image` — probes for `deskbench-capture`, `scrot` or
`import`, in that order. `shot` runs the recorded command once when `settle = false`, or captures
until two consecutive frames match, bounded in time, when `settle = true`. Unknown keys and
out-of-range values are errors, so a typo cannot fall back to a default.

#### Publishing images

Releases publish the three built-ins to GHCR. Tag the repository `vX.Y.Z`; the `publish` workflow
builds the base, then Firefox and Chromium on top of it, and pushes `:X.Y.Z`, `:X.Y`, `:X`,
`:latest` and `:sha-<short>` for each. The major tag (`:1` today) is what the built-in flavours pull.
From a checkout:

```sh
task publish VERSION=1.2.3
task publish REGISTRY=ghcr.io/you/agent-deskbench VERSION=1.2.3
```

`scripts/image-tags.sh` is the single source of the tag list. Pull requests touching `image/` build
all three without pushing. GHCR packages are private by default even for a public repository: open
each package's settings and make it public after the first release (one-time). Until then,
`podman login ghcr.io` is required.

The CLI is the only supported entry point for creating desktops. The tray only observes.

Built-in images run everything as the unprivileged user `agent` (uid 1000), not root, so
applications behave as they would on a workstation. `sudo` is available without a password when root
is genuinely needed. A third-party flavour sets its own `[run].user`; when that uid maps to yours,
bind-mounted files keep their ownership.

## Project structure

```
agent-deskbench/
├── docs/                     vision, architecture, spec, ADRs, diagrams, branch records
├── image/                    container images: TigerVNC + openbox + noVNC, plus flavour builds
├── deskbench/                the CLI, the engine wrapper and the tray
├── tests/                    end-to-end tests through the CLI
├── scripts/                  branch-docs merge gate and image publishing
└── .agents/skills/           the vendored general-software-development skill
```

## For agents

`skill/SKILL.md` is a skill that teaches a coding agent to use this tool: the verbs, the loop, and
the traps. Install it and the CLI with:

```sh
task install-cli     # uv tool install --editable . → deskbench in ~/.local/bin
task install-skill   # copy skill/ to ~/.agents/skills/agent-deskbench
```

## Development

```sh
task test        # python3 -m unittest discover -s tests
task e2e         # container-backed tests (builds the three images, starts desktops)
task lint        # python3 -m compileall + branch-docs check
task image       # rebuild the three images
task publish VERSION=1.2.3   # build and push the three images to GHCR
```

Environment variables for automation:

| Variable | Effect |
|---|---|
| `DESKBENCH_E2E=1` | Run the container-backed tests instead of skipping them |
| `DESKBENCH_NO_TRAY=1` | Do not spawn the tray (headless test runs) |
| `DESKBENCH_RUNTIME=podman\|docker` | Force a runtime instead of detecting one |
| `DESKBENCH_REGISTRY=...` | Registry prefix for built-in image references (default `ghcr.io/nhermosilla14/agent-deskbench`) |
| `DESKBENCH_FLAVOURS_DIR=...` | Directory searched for user flavour manifests (default `$XDG_CONFIG_HOME/agent-deskbench/flavours`) |

`ask` exits `0` when the human pressed *I'm done*, `4` on timeout and `5` when the notification was
dismissed without an answer.

Work follows the loop in `.agents/skills/general-software-development/`: intents → ADRs → vertical
slices, one slice at a time, each with an end-to-end test through the CLI.

## Documentation

- [`docs/README.md`](docs/README.md) — index of everything.
- [`docs/spec/`](docs/spec/) — what the system does today, and the tests that prove it.

## License

GPL-3.0-or-later. See [`LICENSE`](LICENSE).

If you would rather pin the licence to version 3 only, change this line and the SPDX identifier to
`GPL-3.0-only`; the licence text in `LICENSE` is the same either way.
