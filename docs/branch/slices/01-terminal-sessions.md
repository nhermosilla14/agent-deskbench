# Terminal sessions and live capability discovery

- Intents: 20261127-terminal-sessions
- ADRs: 20261127-sessions-are-tmux-read-as-text, 20261127-terminal-geometry-is-explicit-cells,
  20261127-capabilities-are-probed-live

## Scope

An agent can open a named session inside a running desktop, read its visible screen as text, type into
it, list and end sessions, and ask which capabilities that desktop currently has.

```
deskbench capabilities NAME [--json]
deskbench term start NAME --cells WxH [--session S]
deskbench term screen NAME [--session S] [--history N]
deskbench term send NAME [--session S] -- TEXT | --key KEY
deskbench term list NAME [--json]
deskbench term stop NAME [--session S]
```

Delivered end to end: tmux in the base image; sessions spawned with `sh -l` as the labelled run user;
the grid required, bounded and pinned with the pin read back; text capture of the visible pane;
scrollback on request; typing including named keys; a clear failure when the shell has exited; the
live capability probe with package managers and privileged writability; and a `term start` failure
that names the flavour, the capability and a distro-appropriate route to install it.

## Layers touched

- Foundation: `tmux` added to `image/Dockerfile`; a terminal module holding the tmux argv builders,
  the `list-sessions` parser and the cell-size validator; a capability probe module reusing the
  existing `_podman` helper, `engine.get` and the run-user label.
- Services: engine functions for start, screen, send, list, stop and capabilities, all going through
  the runtime with `exec`; CLI parsers and handlers for the two verb families; a package-route message
  builder that reads the probe's report instead of assuming a distribution.
- UI: none beyond the CLI, which is the agent's interface.

## End-to-end test

New `tests/test_term.py` through the CLI, plus a `ContainerTest` desktop:

- `term start` then `send` `echo hi`, and `term screen` shows `hi`; `--history` shows a line that
  scrolled off.
- A full-screen program (`top`) renders as readable text with its layout intact and no escapes.
- `term send` answers a `read` prompt; the answer appears on the screen.
- `term screen` returns while a program in the session waits for input, and does not block.
- `send` `exit`, then `screen` and `send` fail saying the session has ended.
- A duplicate session name is refused; an unknown desktop fails before anything runs.
- `term list --json` reports the session's grid and attached count; the pin reads back as `manual`.
- `capabilities --json` has the contracted keys on a built-in image; tmux is present, the package
  managers list `apt-get`, and writability is measured with sudo.
- Grammar tests without a container: cell bounds, `list-sessions` parsing, and the install-route
  message for a Debian-like, an Alpine-like and an immutable report, asserting none of them says apt
  when the report does not.

## Out of scope

- Attaching from the host, the private shell, the tray and settings: slice 02.
- `term resize`, retention of a dead pane, recording, mouse input and colour-preserving capture.
- stdin or TTY flags on `exec`, and any change to `new`'s creation probes.
