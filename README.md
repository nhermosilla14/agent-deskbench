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
- Podman (rootless is fine), with `/usr/bin/podman` on `PATH`.
- `python3-gi` with GTK 3 and `AyatanaAppIndicator3` — only for the tray and notifications.

```sh
sudo apt install podman python3-gi gir1.2-gtk-3.0 gir1.2-ayatanaappindicator3-0.1
```

## Getting started

```sh
git clone <this repo> agent-deskbench
cd agent-deskbench
task image          # build the container image locally
python3 -m deskbench new --name alpha --size 1600x1000
```

`new` prints JSON with the desktop name, its viewer URL and the container id. Open the URL in a
browser, or click the tray icon and choose *Open viewer*.

## Usage

```
deskbench new [--name NAME] [--size WxH]   start a desktop, print {name, url, id}
deskbench ls [--json]                      list desktops
deskbench url NAME                         print the viewer URL
deskbench exec NAME -- CMD...              run a command inside the desktop
deskbench shot NAME [-o PATH]              capture the desktop to a PNG
deskbench logs NAME [-n N]                 last N lines of the desktop's log
deskbench stop NAME                        stop one desktop
deskbench ask NAME [-t SECONDS] MESSAGE    notify the human and block until they are done
```

The CLI is the only supported entry point for creating desktops. The tray only observes.

## Project structure

```
agent-deskbench/
├── docs/                     vision, architecture, spec, ADRs, diagrams, branch records
├── image/                    container image: TigerVNC + openbox + noVNC
├── src/deskbench/            the CLI, the engine wrapper and the tray
├── tests/                    end-to-end tests through the CLI
├── scripts/                  branch-docs merge gate
└── .agents/skills/           the vendored general-software-development skill
```

## Development

```sh
task test        # python3 -m unittest discover -s tests
task e2e         # the container-backed tests (builds the image, starts desktops)
task lint        # python3 -m compileall + branch-docs check
task image       # rebuild the container image
```

Two environment variables exist for automation:

| Variable | Effect |
|---|---|
| `DESKBENCH_E2E=1` | Run the container-backed tests instead of skipping them |
| `DESKBENCH_NO_TRAY=1` | Do not spawn the tray (headless test runs) |

`ask` exits `0` when the human pressed *I'm done*, `4` on timeout and `5` when the notification was
dismissed without an answer.

Work follows the loop in `.agents/skills/general-software-development/`: intents → ADRs → vertical
slices, one slice at a time, each with an end-to-end test through the CLI.

## Documentation

- [`docs/README.md`](docs/README.md) — index of everything.
- [`docs/spec/`](docs/spec/) — what the system does today, and the tests that prove it.

## License

Not decided yet.
