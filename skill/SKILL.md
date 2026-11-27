---
name: agent-deskbench
description: |
  Give yourself a graphical Linux desktop of your own: a disposable container with an X server, a
  window manager and a browser-viewable screen that you can launch, screenshot and drive without
  touching the human's mouse, keyboard or screen. Use this whenever a task needs a real display for a
  GUI application: launching a windowed program, taking a screenshot of an app, testing or debugging a
  desktop UI, reproducing a visual bug, or when something "needs a display" and the machine has none
  free. Also use it when you must hand control to a human for a moment and wait for them, or when an
  interactive program needs a real terminal you can read as text.
  Do not use it for web-only testing (a browser devtools protocol is far faster), for non-Linux GUI
  toolkits, or for terminal-only work that your own shell can already do.
metadata:
  version: 0.1.0
---

# agent-deskbench

One command creates a private X desktop in a container; another takes a screenshot of it. The human
can watch and type into the same desktop from a browser tab whenever they choose, and you never take
over their screen.

## Check it is available

```sh
deskbench --version
```

If that fails, the tool is not installed on this machine. Do not try to install it yourself; say so
and stop, because the container image build and the tray need a human's environment.

It drives Podman by default and Docker when that is what exists; either way the commands are the
same. If both are installed and you need Docker for a specific reason, set
`DESKBENCH_RUNTIME=docker` for the command.

## The loop

```sh
deskbench new --name check --size 1280x800
# {"name": "check", "url": "http://127.0.0.1:41234/vnc.html?...", "id": "..."}

deskbench exec check -- ./my-app --some-flag     # start the thing under test
deskbench logs check                             # cheap: did it crash?
deskbench shot check -o /tmp/check.png           # then open the PNG to actually see it
```

`shot` waits for the window to appear and the screen to stop changing, so you do not need to sleep
first: shoot straight after launching. It costs about a second when something is drawn and about
three seconds on an empty desktop, because it has to give up waiting.

`shot` only writes a file — you learn nothing until you look at it. Prefer `logs` first: a stack
trace is cheaper and faster than a screenshot. If the PNG is black, nothing was ever painted: the
application died or never mapped a window.

Iterate by re-running `exec` (or restarting the app), then `shot` again. Stop when finished:

```sh
deskbench stop check
```

## Verbs

| Verb | Use |
|---|---|
| `new [--name N] [--size WxH] [--flavour F \| --image REF] [--pull P]` | Create a desktop; prints JSON with `name`, `url`, `id` |
| `images [--json]` | Built-in and user image flavours, and whether they are present locally |
| `ls [--json]` | What exists right now, with URLs |
| `url NAME` | Just the viewer URL |
| `exec NAME -- CMD...` | Run a command inside the desktop; streams output, returns its exit code |
| `shot NAME [-o PATH]` | PNG of the current screen; prints the path |
| `logs NAME [-n N]` | Tail of the container log |
| `stop NAME` | Destroy it, including everything you created inside |
| `ask NAME MESSAGE` | Notify the human and block until they answer |
| `capabilities NAME [--json]` | What the desktop has right now: shell, screenshot tool, tmux, sudo, package managers |
| `term start NAME --cells WxH [--session S]` | Open a session you can read and type into |
| `term screen NAME [--session S] [--history N]` | The session's visible screen, as plain text |
| `term send NAME -- TEXT` or `--key K` | Type text plus Enter, or one named key |
| `term list NAME [--json]` | Sessions, their grid and how many clients are attached |
| `term stop NAME [--session S]` | End one session and keep the desktop |

Names are lowercase letters, digits and hyphens. Without `--name` you get `desk1`, `desk2`, and so on.

## Choosing a desktop image

`new` starts from a named flavour, or from a fully qualified image reference with `--image`:

```sh
deskbench images
```

| Flavour | Pick it when |
|---|---|
| `base` (default) | You will install your own packages, or the app is a binary you mount in. Nothing preinstalled means nothing to second-guess |
| `firefox` | The thing under test is a web UI, or you need a browser to log in, read docs or drive a site |
| `chromium` | Same, but the page expects Blink behaviour or you want devtools |

Rules of thumb:

- Use a browser flavour instead of installing a browser yourself. The base image is bare on purpose,
  so installing one by hand costs a network round trip *every* session.
- Stay on `base` when you are going to install packages anyway, or when the app is native. A flavour
  costs one pull the first time; installing by hand costs minutes every time.
- `--pull=missing` (the default) uses a local image and pulls only when needed; `--pull=always`
  refreshes the tag and `--pull=never` refuses to pull. No path builds an image.
- Use `--image registry.example.com/team/desktop:1` for an image that is not listed by
  `deskbench images`; the reference must be fully qualified and carry a tag or digest.
- A user flavour is a directory under `~/.config/agent-deskbench/flavours` with a `flavour.toml`.
  `images` shows it with source `user`; `new --flavour NAME` uses it exactly like a built-in.
- A third-party image may need `[viewer]`, `[run]` and `[screenshot]` in its manifest. `new` refuses
  an image it cannot view, capture or exec into, so a successful `new` means all three work.
- Launch Chromium through `chromium-desk`. It only adds `--disable-dev-shm-usage` (containers have a
  64 MB `/dev/shm`); the renderer sandbox stays on. If a hardened host blocks unprivileged user
  namespaces Chromium will refuse to start and say so — then pass `--no-sandbox` yourself and know
  that you weakened the boundary.
- The image is fixed when the container starts; choose before you install anything you care about.

## Your project inside the desktop

The desktop starts as a bare Debian; mount the code you are working on:

```sh
deskbench new --name dev --bind .                      # → /mnt/<directory name>
deskbench new --name dev --bind ~/src/app:/work        # explicit destination
deskbench new --name dev --bind ~/datasets:/data:ro    # read-only

deskbench exec dev -- sh -c 'cd /mnt/app && ./build/my-app'
```

Mounts are read-write unless you say `:ro`, and changes round-trip to the host, so an edit on the
host is visible inside without restarting the desktop.

## Terminal sessions

`exec` is one command per call and keeps nothing: no working directory, no way to answer a prompt, no
view of a full-screen program. When you need those, open a session.

```sh
deskbench term start dev --cells 120x40          # the grid is required: columns x rows
deskbench term send dev -- ./installer --flag    # types it, then presses Enter
deskbench term screen dev                        # the visible screen, as text
deskbench term screen dev --history 200          # plus scrollback above it
deskbench term send dev --key C-c                # one key: a prompt, a stuck program, a TUI
deskbench term stop dev                          # when you are done with it
```

- `80x24` is the grid every program was designed for; widen it for diffs and logs. Whatever you pick
  is pinned, so nothing that happens on the other side reflows what you read.
- `screen` is a text screenshot: the visible pane, which is what a human would be reading. There is
  no image to interpret and no OCR.
- It is a real shell, so `cd`, `export` and an activated virtualenv survive between commands. Answer
  a prompt with `send`, including control keys.
- Full-screen programs are readable this way (`top`, `htop`, `less`, a TUI you are testing): you get
  the frame, not escape soup.
- The session ends when its shell exits. After that, `screen` and `send` tell you so; start a new one.
- `term list` shows what exists; a session outlives your detaching from it.

## Handing control to a human

Use `ask` when a decision, a login, a CAPTCHA or a visual judgement is beyond you. It shows a desktop
notification containing the viewer URL, makes the tray icon pulse, and blocks:

```sh
deskbench ask check --timeout 120 "The Save dialog is asking for a filename; please choose one"
```

Exit codes matter: `0` the human pressed *I'm done*, `4` they did not answer in time, `5` the request
was dismissed or the desktop or notification service went away. After `0`, take a fresh `shot` — the
screen has changed underneath you.

## Gotchas that waste a run

- **The first `new` pulls the image** and can take a couple of minutes, printing progress to stderr.
  Later desktops start in about a second. Do not kill it early; `--pull=always` refreshes the tag.
- **There is no GPU.** Rendering is software (`llvmpipe`). Fine for widgets, forms and text; expect
  slow or missing WebGL, video and animations. An odd-looking blur or shader may be the bench, not a
  bug in the app.
- **A black screenshot means nothing was painted.** `shot` already waited for a window to appear and
  for the screen to settle, so a uniform image means the application died or never mapped a window:
  check `logs` and that you launched it inside the desktop.
- **`stop` destroys everything.** The container is `--rm`, so files, installed packages and app state
  vanish. Do not stop until you have what you need.
- **You are not root inside.** Built-in images run everything as the unprivileged user `agent`
  (uid 1000), so applications behave as they would on a workstation instead of hitting root-only
  paths and sandbox refusals. A third-party flavour can choose another `[run].user`; `exec` and
  `term` use the user recorded at creation. When you genuinely need packages, `sudo` is passwordless.
- **Install the way the image expects, not the way you remember.** Run
  `deskbench capabilities NAME` first: it reports the package managers the image actually has, whether
  a privileged write is possible, and whether tmux and a screenshot tool are there. Use the image's
  native manager. Fall back to Homebrew only when the image cannot write to its root filesystem, which
  is what immutable distributions look like. Never assume `apt-get`.
- **Bind mounts keep their ownership**: files you create inside a mount are owned by you on the
  host, and host files keep their owner inside.
- **Always create desktops through `deskbench new`.** A bare `podman run` has no label, so `ls` and the
  tray will not see it.
- **One desktop can be asked about at a time**, and the human sees one notification per request.
- No audio, no clipboard sharing, no native VNC client: the browser viewer is the interface.

## Details

- `exec` runs `sh -lc` with your arguments quoted, so pipes, `&&` and redirection work, and
  `$DISPLAY` is already `:1` inside the container.
- `term start` runs `sh -l` as the recorded user; `term send` quotes nothing for you, so pass the
  command exactly as you would type it.
- Launch long-running apps with a trailing `&`; `exec` returns when the command returns.
- A session is not a log: `screen` shows the visible pane. For a long build, `--history`, or run it
  under `exec` and read `logs`.
- A desktop with the same name as an existing one is refused; pick another or stop the old one.
