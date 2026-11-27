# Terminal geometry is an explicit cell grid

- Status: Accepted
- Date: 2026-11-27
- Deciders: Nicolás Hermosilla Polanco
- Approved by: Nicolás Hermosilla Polanco
- Spec area: terminal.md

## Context

A terminal session needs a size, and that size is a grid of character cells, not pixels: the human
view is the developer's own terminal emulator, so no window exists inside the desktop to measure.
Something must choose the grid, and the choice is not cosmetic. Programs lay themselves out from the
size they are given, and a grid that changes between two `term screen` calls reflows the text the
agent is trying to reason about.

Two ways to get it wrong. A default freezes a size that the caller never chose and the program may not
have been designed for. Letting the attached client drive the size means a human who resizes their
window silently rewrites the agent's screen, mid-investigation, without either party noticing.

## Decision

`deskbench term start` requires the grid: `--cells WxH`, with no default. The value is validated the
way desktop sizes are, with plausible bounds (20–500 columns, 5–200 rows), so `--cells 1x1` and
`--cells 100000x100000` are refused before anything starts.

- The session is created at that size and pinned with tmux `window-size manual`, so an attached client
  can resize its own view without changing what the agent reads.
- The pin is verified after creation by reading the option back. If the tmux in the image cannot pin,
  `term start` fails naming the limitation rather than starting a session whose size will drift. This
  is a functional probe, not a version comparison, because the boundary between tmux releases is not
  something the record should guess at.
- Sessions created from the tray use the configured default size (see the settings decision, `120x40`).
- The private `shell` is a plain interactive shell with no multiplexer, so it follows the human's own
  terminal and needs no setting.
- There is no `term resize` in this change. The grid is immutable for the life of a session, which is
  what makes two reads comparable. A human whose terminal is smaller than the pinned grid sees a
  cropped view; `term attach` warns on stderr when it can measure a smaller host terminal, and the
  limitation is documented.

## Alternatives considered

- **Default `80x24`**, the VT100, xterm and tmux default — sensible for programs, but it makes the
  caller's choice invisible and produces grids nobody decided on.
- **Default `100x35`**, derived from an 800x600 window — matches no standard and predates the decision
  that the human views sessions in their own terminal, so the pixel size it came from no longer
  exists.
- **Let the client drive the size** — a human resize rewrites the agent's screen, which is the exact
  failure the pin exists to prevent.
- **A default plus an override** — the same invisibility, with two ways to state the same thing.
- **Ship `term resize` now** — it would let a human change the agent's grid underneath it. If it is
  ever added it must be an explicit, agent-visible act; that is a later decision, not a default.

## Consequences

Callers state a grid, so an agent decides deliberately: `80x24` as a baseline, wider for diffs and
logs. The tray needs its own setting because a human clicking a menu cannot type a grid. The pinned
grid does not reflow under an attached human, which is what makes `term screen` reproducible.

The crop is a real limitation, not a cosmetic one: a human on a narrow terminal joining a wide session
cannot see the line they are typing, and their only remedy is a wider terminal. That is why attach
warns when it can measure the difference, and why resize is deliberately absent rather than forgotten.

Every session reports its grid in `term list`, so the caller can see what the program was given.
