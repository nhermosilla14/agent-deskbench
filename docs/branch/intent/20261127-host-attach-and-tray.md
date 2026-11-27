# Join a session from the developer's own terminal, and list sessions in the tray

- Status: Proposed
- Date: 2026-11-27
- Owner: Nicolás Hermosilla Polanco
- Depends on: 20261127-terminal-sessions

## Goal

A developer can see the live terminal sessions of every desktop from the tray icon and join one in
their own terminal emulator, with one command or one click, sharing that session with the agent. A
private shell stays available for anything the agent must not read.

## Acceptance criteria

- `deskbench term attach NAME [--session S]` opens the session in a terminal emulator on the host,
  running `exec -it … tmux attach` against the container, and returns without waiting for the
  emulator to exit.
- The emulator is resolved in a documented order (`$TERMINAL`, `xdg-terminal-exec`,
  `x-terminal-emulator`, then the common emulators); with none available, `term attach` exits 1
  naming what it looked for.
- `term attach --print` writes the argv it would spawn and spawns nothing, so the wiring is provable
  without a GUI; `DESKBENCH_TERMINAL` overrides the emulator and the tests use it.
- The human's terminal attaches to the same session the agent reads: what they type appears in
  `term screen`, and what the agent causes appears in their terminal.
- `deskbench shell NAME` opens a private interactive shell (a login shell via `exec -it`) that no
  multiplexer manages; it appears in neither `term list` nor the tray.
- The tray shows, per desktop, a Terminals submenu with each live session and its attached count;
  selecting one attaches locally. It also offers "New terminal…", which starts the default session
  when absent and attaches, and "Open private shell".
- Sessions that start or end appear or disappear without restarting the tray.
- The tray calls the same attach code as the CLI; there is no second implementation.
- The tray rebuilds its menu only when what it displays changed, so items no longer flicker when the
  two-second poll finds nothing new.
- The skill and the README state that a listed session is readable by the agent, so secrets belong
  in a private shell.

## Spec changes

- Adds: `terminal.md` / Attaching from the host
- Adds: `terminal.md` / The private shell
- Changes: `lifecycle.md` / the tray's menu (it now lists sessions and attaches to them)
- Changes: `cli.md` / the verb index

## Out of scope

- A terminal window inside the desktop (xterm over VNC).
- Asking which emulator to use when several exist; the documented order decides.
- Attaching several sessions in one call or in tabs.

## Open questions

- With no sessions, should the Terminals submenu be hidden, or shown with only "New terminal…" so the
  feature is discoverable?
