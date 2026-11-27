# Sessions are tmux panes read as text

- Status: Proposed
- Date: 2026-11-27
- Deciders: Nicolás Hermosilla Polanco
- Spec area: terminal.md

## Context

`deskbench exec` runs one command per invocation through `sh -lc`, without a persistent working
directory, environment or stdin. An agent can start a program and read its stdout, but it cannot
answer a prompt, drive a REPL, look at a full-screen program, or carry state from one call to the
next. Wrapping several steps in one `sh -c` is the only workaround, and it cannot answer anything
that decides to ask a question mid-run.

The need splits into three parts: state that survives between calls, answers to prompts, and a view
of what a full-screen program is drawing. "Interactivity" on its own is not a requirement, because an
agent's tool call has no way to type a character while the call is open.

Three constraints bound the answer. `docs/vision.md` rules out an in-container control daemon for
semantic automation, keeps Podman as the only state store, and forbids third-party Python packages.
The agent's current view of a desktop is `shot`, a PNG of several hundred kilobytes that can only be
interpreted visually.

## Decision

A session is a tmux session inside the desktop container, and its visible pane is the source of
truth.

- `deskbench term start NAME --cells WxH [--session S]` creates the session detached and returns only
  once it answers. The session runs `sh -l` explicitly rather than tmux's `default-shell`: the desktop
  contract guarantees `sh`, while a third-party image's passwd entry may name a shell that is missing
  or `nologin`.
- `deskbench term screen NAME [--session S] [--history N]` is `tmux capture-pane -p`: the visible pane
  as plain text, wrapped lines joined, no escape sequences. `--history N` prepends up to N lines of
  scrollback; the default is the visible area only, matching what a human sees.
- `deskbench term send NAME [--session S] -- TEXT` types literal text with `send-keys -l` and then
  Enter; `--key` sends one named key such as `C-c` or `Tab`.
- `deskbench term list NAME [--json]` reports each session's name, grid and attached-client count;
  `deskbench term stop NAME [--session S]` ends one session and leaves the desktop running.
- Several named sessions may exist per desktop, with `main` as the default name. A duplicate name is
  refused.
- A session ends when its shell exits. `remain-on-exit` stays off, so the pane is not kept as a
  corpse; `term screen` and `term send` on a session that has ended fail with a message saying so,
  instead of relaxing into a silent no-op on a dead pane.
- There is no host daemon and no new in-container daemon. The tmux server lives and dies with the
  `--rm` container, so Podman remains the only state store and sessions do not survive `stop`. That
  is a boundary, not a gap to extend later.
- tmux ships in the base image as a Debian distribution package.

## Alternatives considered

- **stdin and TTY flags on `exec`** — answers prompts, which is one of the three needs, but gives no
  persistence and no view of a full-screen program. Worth doing on its own merits; it does not
  replace a session.
- **A persisted working directory and environment file for `exec`** — covers state alone, cannot
  answer a prompt or render a TUI, and invents a state convention that the session makes redundant.
- **asciinema or `script` casts** — a byte stream with timings. It is a recording format: turning it
  into a screen still needs a terminal emulator, which is the thing being chosen.
- **A PTY plus a VT parser of our own** — the same emulator idea, hand-written or pulled from a
  third-party package, for something tmux already ships and maintains.
- **Reading a GUI terminal's text over AT-SPI** — only VTE-based terminals expose their text, which
  couples capture to one emulator and walks into the vision's non-goal on in-container automation.
- **`screen`'s `hardcopy`** — equivalent for capture, but tmux additionally provides multi-client
  attach and explicit geometry control, which the next decisions rely on.
- **`remain-on-exit on`** — keeps the last frame after a crash, but turns `term send` into a silent
  no-op and makes "is this session usable" a question the agent has to ask. An explicit "the session
  has ended" is the better signal for the common case, which is a deliberate exit.

## Consequences

The agent reads a few kilobytes of exact text instead of a megabyte of pixels, with no OCR, no font
guessing and no ambiguity over box drawing or glyphs. Only the visible pane is captured, so scrollback
costs an explicit `--history`. Processes started in a session die with it, which is the same
guarantee `exec` already gives. A flavour without tmux lacks the feature entirely; capability
handling is a separate decision. tmux becomes a per-desktop process wherever sessions are used, and a
new dependency that flavour authors must satisfy.

`term list --json` keys and the `capabilities --json` keys become part of the CLI contract as soon as
they ship, so they are named as if permanent.
