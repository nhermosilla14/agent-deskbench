# Humans attach from their own terminal, and a private shell exists

- Status: Accepted
- Date: 2026-11-27
- Deciders: Nicolás Hermosilla Polanco
- Approved by: Nicolás Hermosilla Polanco
- Spec area: terminal.md, lifecycle.md

## Context

The vision requires that a human can attach to any running desktop at any time without disturbing the
agent, and take over in one click. For a terminal session there are three routes: an emulator inside
the desktop rendered through the VNC viewer, a web terminal served from the container, or the
developer's own emulator attached to the same tmux session the agent reads.

Two constraints shape the choice. The human's terminal should be their own: their font, their
scrollback, their copy and paste. And a shared session is by construction readable by the agent, which
matters at the moment a human is asked to type a password or a token for it.

The tray is the discovery surface, and it has no stderr: a click that fails silently is a click that
did nothing.

## Decision

`deskbench term attach NAME [--session S]` opens the session in a terminal emulator on the host.

- The desktop and session are validated before anything is spawned: a wrong name fails with a message
  in the terminal that asked, not with a window that flashes and dies.
- The emulator is resolved in a documented order: `$TERMINAL`, `xdg-terminal-exec`,
  `x-terminal-emulator`, then the common emulators by name. With none available it exits 1 naming what
  it looked for.
- It is spawned detached, with no inherited stdio and in its own session, running
  `podman exec -it --user <labelled run user> <container> tmux attach`. The run user is explicit
  because the tmux server lives in that user's socket directory: attaching as anyone else sees
  nothing, or fails on permissions, which would work on the built-in images and break on exactly the
  third-party flavours the rest of the design tolerates.
- `--print` writes the argv it would spawn and spawns nothing. It is a debugging and testing surface,
  not a supported interface: the raw `podman` command it shows is deliberately not a documented way to
  reach a desktop.
- When a host terminal is attached and measurable, `term attach` warns on stderr if it is smaller than
  the pinned grid, because the human would otherwise see a cropped session.

The tray lists, per desktop, a Terminals submenu with each live session and its attached count;
selecting one attaches through the same function the CLI uses, so there is no second implementation.
It offers `New terminal…`, which starts the default session at the configured size when absent and
attaches, and `Open private shell`. A failure surfacing from either is shown as a desktop
notification, not only on a stderr nobody is watching. The menu is rebuilt only when what it displays
has changed, so the two-second poll no longer makes items flicker under the pointer.

`deskbench shell NAME` is a private interactive login shell: `exec -it` as the labelled user, with no
multiplexer. It appears in neither `term list` nor the tray, and it is the documented place for
anything the agent must not read.

The image keeps the xterm it already ships, but nothing in the CLI opens a terminal window on the
desktop: the human's terminal is the host's. No web terminal is added.

## Alternatives considered

- **An xterm on the desktop, watched through the VNC viewer** — the human gets a remote desktop
  instead of their own terminal, every image needs an emulator installed, and the window competes for
  space with the application under test.
- **A web terminal such as ttyd or gotty** — a second listener, a second way to reach a shell,
  browser-only, and a duplicate of the viewer the desktop already has.
- **VTE text over AT-SPI** — the vision's non-goal for automation, and it works only with one family
  of emulators.
- **Making every attach private** — defeats the shared view, which is the point of listing sessions at
  all. The need for privacy is real, and is served by `shell` instead.
- **Spawn first and hope** — cheaper, and produces the silent-failure path the tray cannot show.

## Consequences

The human works in their own terminal and closing it detaches without disturbing the session. A host
terminal that already runs tmux traps the prefix key, so the inner one needs it twice; that is
documented rather than solved. Emulator argument conventions differ, so the lookup carries a small
table that must be tested with a fake emulator. Attaching needs a TTY and fails clearly without one.

The tray now spawns processes, which `Open viewer` already did, but only through the CLI's own module.
A shared pane is readable by the agent, so secrets belong in the private shell and the documentation
says so next to both actions.
