---
name: agent-deskbench
description: |
  Give yourself a graphical Linux desktop of your own: a disposable container with an X server, a
  window manager and a browser-viewable screen that you can launch, screenshot and drive without
  touching the human's mouse, keyboard or screen. Use this whenever a task needs a real display for a
  GUI application: launching a windowed program, taking a screenshot of an app, testing or debugging a
  desktop UI, reproducing a visual bug, or when something "needs a display" and the machine has none
  free. Also use it when you must hand control to a human for a moment and wait for them.
  Do not use it for web-only testing (a browser devtools protocol is far faster), for non-Linux GUI
  toolkits, or for terminal-only work.
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
| `new [--name N] [--size WxH]` | Create a desktop; prints JSON with `name`, `url`, `id` |
| `ls [--json]` | What exists right now, with URLs |
| `url NAME` | Just the viewer URL |
| `exec NAME -- CMD...` | Run a command inside the desktop; streams output, returns its exit code |
| `shot NAME [-o PATH]` | PNG of the current screen; prints the path |
| `logs NAME [-n N]` | Tail of the container log |
| `stop NAME` | Destroy it, including everything you created inside |
| `ask NAME MESSAGE` | Notify the human and block until they answer |

Names are lowercase letters, digits and hyphens. Without `--name` you get `desk1`, `desk2`, and so on.

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

- **The first `new` builds the image** and takes a couple of minutes, printing a progress line to
  stderr. Later desktops start in about a second. Do not kill it early.
- **There is no GPU.** Rendering is software (`llvmpipe`). Fine for widgets, forms and text; expect
  slow or missing WebGL, video and animations. An odd-looking blur or shader may be the bench, not a
  bug in the app.
- **A black screenshot means nothing was painted.** `shot` already waited for a window to appear and
  for the screen to settle, so a uniform image means the application died or never mapped a window:
  check `logs` and that you launched it inside the desktop.
- **`stop` destroys everything.** The container is `--rm`, so files, installed packages and app state
  vanish. Do not stop until you have what you need.
- **The image is a bare Debian plus X tooling**, not your project. Bring the checkout in with
  `--bind` (next section) and install missing packages with
  `deskbench exec NAME -- sudo apt-get install -y ...` — you are root inside.
- **Always create desktops through `deskbench new`.** A bare `podman run` has no label, so `ls` and the
  tray will not see it.
- **One desktop can be asked about at a time**, and the human sees one notification per request.
- No audio, no clipboard sharing, no native VNC client: the browser viewer is the interface.

## Details

- `exec` runs `sh -lc` with your arguments quoted, so pipes, `&&` and redirection work, and
  `$DISPLAY` is already `:1` inside the container.
- Launch long-running apps with a trailing `&`; `exec` returns when the command returns.
- A desktop with the same name as an existing one is refused; pick another or stop the old one.
