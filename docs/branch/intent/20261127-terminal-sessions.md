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

- `deskbench term start NAME [--session S] [--cells WxH]` starts a session inside the desktop that
  runs the image's login shell, fixes its grid to the requested size (`--cells`, default `80x24`),
  and returns only once the session answers.
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
  The answer reflects the container as it is now, so it is still true after the agent installs
  something.
- `term start` probes tmux at first use rather than trusting a recorded answer. When it is absent it
  exits 1 naming the flavour, the missing capability and the command that installs it
  (`sudo apt-get install -y tmux`); installing it in the session makes the next call succeed.
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
- Installing packages on the agent's behalf; a failure names the command and the agent decides.

## Open questions

- Is `80x24` the right default grid, or should `term start` require `--cells`? `80x24` is the
  VT100/xterm/tmux default, it is what programs are written against, and any human terminal can show
  the whole shared session uncropped; it is narrower than a modern developer terminal for logs and
  wide diffs, which is what `--cells` is for. `100x35` came from converting an 800x600 window to
  cells and matches no standard.
