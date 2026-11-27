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
  runs the image's login shell, fixes its grid to the requested size (`--cells`, default `100x35`),
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
- `new` records whether the image provides tmux as a container label; a desktop whose image lacks it
  fails `term` with exit 1 naming the flavour and the missing capability, before changing anything.
- The base image ships tmux from distribution packages, so every built-in flavour satisfies the
  terminal contract.
- `term` against an unknown desktop fails before touching anything.

## Spec changes

- Adds: `terminal.md` / Terminal sessions
- Changes: `images.md` / the desktop contract (the tmux capability and its label)

## Out of scope

- A terminal window on the desktop; the human's view is a local terminal (separate intent).
- Persistent working directory and environment for `exec`; a terminal session is the answer to that
  need.
- stdin and TTY flags on `exec`.
- Session recording (asciinema-style casts), mouse input, and colour-preserving capture.
- Starting a session automatically from `new`.

## Open questions

- Is `100x35` the right default grid? It fits 800x600 at a typical 8x17 cell and covers a full-screen
  TUI, but it is a visible default.
- Should `new` refuse an image with no tmux, as it refuses one with no screenshot tool, or accept it
  and let `term` name the missing capability? Refusing is consistent with failing fast, but breaks
  every third-party flavour that works today and contradicts the README promise that a successful
  `new` means the desktop is fully usable.
