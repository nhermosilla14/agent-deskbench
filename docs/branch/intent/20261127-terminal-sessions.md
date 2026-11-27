# Terminal sessions the agent can read and type into

- Status: Proposed
- Date: 2026-11-27
- Owner: Nicolás Hermosilla Polanco

## Goal

An agent can open a persistent shell inside a running desktop, read its visible screen as plain text
instead of as a pixel screenshot, and send it commands and keystrokes. Interactive prompts and
full-screen terminal programs become drivable without wrapping every step in one `exec` call, and
the working directory, environment and background jobs survive between calls.

## Acceptance criteria

- `deskbench term start NAME --cells WxH [--session S]` starts a session inside the desktop that
  runs the image's login shell, fixes its grid to exactly the requested size, and returns only once
  the session answers. The grid is required: the caller states the size the program needs instead of
  inheriting a default the program was not designed for.
- Several sessions may exist per desktop (`--session`, default `main`); a duplicate name exits 1
  naming the session.
- `deskbench term screen NAME [--session S] [--history N]` prints the visible screen as plain text
  and nothing else; `--history N` prepends up to N lines of scrollback; the default is the visible
  area only.
- A full-screen program started in a session (`top`) is readable in `term screen`: the frame a human
  would see, with layout intact and without escape sequences.
- `deskbench term send NAME [--session S] -- TEXT` types TEXT and presses Enter; `--key C-c` sends
  one named key. Answering a prompt inside a session works.
- `deskbench term list NAME [--json]` reports each session's name and the number of attached
  clients; `deskbench term stop NAME [--session S]` ends one session and leaves the desktop running.
- `term screen` reads a snapshot and never blocks, including while a program in the session is
  waiting for input or looping.
- A session outlives its attached clients: with nobody attached it stays readable and writable, and
  the agent's reads do not disturb whoever is attached.
- `deskbench capabilities NAME [--json]` reports, from a live probe, whether the desktop has the
  shell, the screenshot tool, tmux, a terminal emulator and sudo, with the resolved path for each.
  It also reports which package managers the image offers (`apt-get`, `dnf`, `zypper`, `apk`,
  `pacman`, `brew`) and whether the root filesystem is writable, so an agent installs what is missing
  the way that image expects instead of assuming Debian. The answer reflects the container as it is
  now, so it is still true after the agent installs something.
- `term start` probes tmux at first use rather than trusting a recorded answer. When it is absent it
  exits 1 naming the flavour, the missing capability and how to obtain it on that image: the
  distribution's own package manager when the root is writable, Homebrew as the fallback for
  immutable images. No message assumes apt.
- The skill's package-installation guidance names no single package manager: it tells the agent to
  read the distribution, prefer the image's native manager, and fall back to Homebrew only when the
  image cannot install packages the usual way.
- `new` does not probe, record or refuse anything about terminals: capability is discovered live, and
  the creation contract still covers exactly the viewer, the screenshot and the shell.
- The base image ships tmux from distribution packages, so every built-in flavour has the capability
  without a network round trip.
- `term` against an unknown desktop fails before touching anything.

## Spec changes

- Adds: `terminal.md` / Terminal sessions
- Adds: `cli.md` / Capabilities
- Changes: `cli.md` / the verb index

## Out of scope

- A terminal window on the desktop; the human's view is a local terminal (separate intent).
- Persistent working directory and environment for `exec`; a terminal session is the answer to that
  need.
- stdin and TTY flags on `exec`.
- Session recording (asciinema-style casts), mouse input, and colour-preserving capture.
- Starting a session automatically from `new`.
- Installing packages on the agent's behalf; a failure names the capability and the supported way to
  install it, and the agent decides.

## Open questions

None. The grid is a required argument, so no default has to be defended.
