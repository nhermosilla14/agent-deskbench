# Join a session from the developer's own terminal, and list sessions in the tray

- Status: Accepted
- Date: 2026-11-27
- Owner: Nicolás Hermosilla Polanco
- Approved by: Nicolás Hermosilla Polanco
- Depends on: 20261127-terminal-sessions

## Goal

A developer can see the live terminal sessions of every desktop from the tray icon and join one in
their own terminal emulator, with one command or one click, sharing that session with the agent. A
private shell stays available for anything the agent must not read, and a small settings window holds
the defaults that concern the human rather than the agent.

## Acceptance criteria

- `deskbench term attach NAME [--session S]` opens the session in a terminal emulator on the host,
  running `exec -it … tmux attach` against the container, and returns without waiting for the
  emulator to exit. The desktop and session are validated before anything is spawned, so a wrong name
  fails in the terminal that asked instead of becoming a window that flashes and dies.
- The attach runs as the user recorded on the container, because the tmux server lives in that user's
  socket directory; attaching as anyone else finds no session or is refused on permissions.
- When a host terminal is attached and measurable, `term attach` warns when it is smaller than the
  pinned grid, since the human would see a cropped session.
- The emulator is resolved in a documented order (`$TERMINAL`, `xdg-terminal-exec`,
  `x-terminal-emulator`, then the common emulators); with none available, `term attach` exits 1
  naming what it looked for.
- `term attach --print` writes the argv it would spawn and spawns nothing, so the wiring is provable
  without a GUI; `DESKBENCH_TERMINAL` overrides the emulator and the tests use it. The printed argv is
  a debugging surface, not a supported way to reach a desktop.
- The human's terminal attaches to the same session the agent reads: what they type appears in
  `term screen`, and what the agent causes appears in their terminal.
- `deskbench shell NAME` opens a private interactive shell (a login shell via `exec -it`) that no
  multiplexer manages; it appears in neither `term list` nor the tray.
- The tray shows, per desktop, a Terminals submenu with each live session and its attached count;
  selecting one attaches locally. It also offers "New terminal…", which starts the default session
  when absent and attaches, and "Open private shell". A failure from either action reaches the human
  as a desktop notification, not only on a stderr nobody is watching.
- The tray offers a Settings item that opens a **separate window**, not a menu widget, so the window
  can stay open while the menu is dismissed.
- The settings window shows one setting, "Default size for new terminals", in cells, defaulting to
  `120x40` when nothing is stored. It accepts `WxH`, refuses an invalid value with a message in the
  window, and never overwrites a stored value it could not parse.
- The size is persisted under the user's XDG config root, beside the flavour manifests but resolved
  independently of `DESKBENCH_FLAVOURS_DIR`, read at startup, and takes effect on the next
  "New terminal…" without restarting the tray. Saving is atomic, so a crash mid-write cannot lose the
  stored value, and a hand-edited or unreadable file falls back to `120x40` rather than failing.
- The value is validated on save with the same bounds `--cells` uses, so the window cannot store a
  grid the CLI would refuse.
- Closing the settings window hides it and leaves the tray running; the next open shows the current
  value.
- "New terminal…" starts the session at the configured size. `term start` on the CLI still requires
  `--cells`, so an agent always states the grid it needs.
- The private shell takes its size from the human's own terminal, so the setting does not apply to it.
- Sessions that start or end appear or disappear without restarting the tray.
- The tray calls the same attach code as the CLI; there is no second implementation.
- The tray rebuilds its menu only when what it displays changed, so items no longer flicker when the
  two-second poll finds nothing new.
- The skill and the README state that a listed session is readable by the agent, so secrets belong
  in a private shell.

## Spec changes

- Adds: `terminal.md` / Attaching from the host
- Adds: `terminal.md` / The private shell
- Adds: `settings.md` / The settings window
- Changes: `lifecycle.md` / the tray's menu (it now lists sessions, attaches, and opens settings)
- Changes: `cli.md` / the verb index

## Out of scope

- A terminal window inside the desktop (xterm over VNC).
- Asking which emulator to use when several exist; the documented order decides.
- Attaching several sessions in one call or in tabs.
- Any setting other than the default terminal size, and per-desktop overrides of it.
- Editing settings from the CLI: the window is the only editor.

## Open questions

- With no sessions, should the Terminals submenu be hidden, or shown with only "New terminal…" so the
  feature is discoverable?
- Does the size apply as soon as it is valid, or on an explicit Save? One field makes "apply on
  change" tempting, but a half-typed `12` must not be stored.
