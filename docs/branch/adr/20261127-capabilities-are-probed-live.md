# Capability is probed live, not frozen in labels

- Status: Proposed
- Date: 2026-11-27
- Deciders: Nicolás Hermosilla Polanco
- Spec area: terminal.md, cli.md

## Context

`new` proves the desktop contract (a viewer, a screenshot command, a shell) and records the resolved
viewer, screenshot command and run user as container labels. Labels are immutable by design, so an
edited manifest cannot mutate a running desktop: the label is the record of how that container was
started, and later calls read it instead of guessing.

A terminal needs tmux, which an arbitrary `--image` may not have, and which the agent can install
inside the container at any time with the passwordless `sudo` the contract promises. A capability
recorded at creation would therefore be wrong for the rest of the container's life, and would be wrong
in the direction that matters: it would say "no" after the agent has fixed it.

Agents also need to install things the way the image expects. Assuming Debian and apt is wrong for a
Fedora, Alpine or Arch image, and some images cannot install packages at all because their root
filesystem is immutable, where Homebrew is the workable route.

## Decision

Split the two kinds of fact. Frozen facts stay labels: viewer port, path and scheme, the screenshot
command, and the run user. Acquirable capabilities are probed live.

`deskbench capabilities NAME [--json]` runs one `podman exec` and reports, with resolved paths where
they exist: the shell; the screenshot tool; tmux; sudo; the package managers present (`apt-get`,
`dnf`, `zypper`, `apk`, `pacman`, `brew`); and whether the root filesystem can be written to.

- The writability check runs with privileges when it can: `sudo -n test -w /usr` when sudo is present
  and passwordless, otherwise `test -w /usr`. A plain unprivileged check would answer "no" on every
  ordinary image, including the Debian base, because `/usr` belongs to root — it would route every
  agent to Homebrew on systems where the native manager works. The report says that the answer is only
  as good as the privilege it was measured with.
- A terminal emulator is deliberately absent from the report. Nothing in the CLI consumes one inside
  the image, and a field with no consumer invites an agent to depend on it.
- `new` neither probes, records nor refuses anything about terminals. The creation contract still
  covers exactly the viewer, the screenshot and the shell, and the promise that a successful `new`
  means the desktop is usable stays true without a fourth requirement.
- `term start` probes tmux at first use. When it is missing it exits 1 naming the flavour and the
  capability, with the route that fits the image: its native package manager when one is present and a
  privileged write is possible; Homebrew when that fails and `brew` exists; otherwise it names what it
  found and says the image cannot install packages the usual way. No message in the code or the
  documentation assumes apt.
- The skill tells the agent to read the image before installing, prefer its native manager, and fall
  back to Homebrew only when the image cannot install packages normally.

## Alternatives considered

- **Record tmux in a label at creation** — lies from the moment the agent installs it, because labels
  cannot change.
- **Refuse an image without tmux in `new`** — breaks the documented `--image` escape hatch and every
  third-party flavour, and vision goal 7 enumerates exactly three mandatory capabilities.
- **Let `term` fail with a generic message** — leaves the agent to guess a package manager, and
  `apt-get` on an immutable image fails with an error that hides the real problem.
- **Report capabilities from `new`'s JSON** — a snapshot that rots within the same minute, and it
  mixes informing with refusing in the one call that must stay binary.
- **Assume apt** — true of the base image and false of `--image`, which is the feature's whole point.
- **Probe writability unprivileged** — the tempting one, and wrong: it answers "no" everywhere and
  misroutes the agent to Homebrew on a normal Debian desktop. Rejected on review.

## Consequences

One extra exec per planning call, tens of milliseconds, and nothing at creation. An agent may see a
capability appear after installing it, which is the intended behaviour. No new labels, and the
creation contract is unchanged. `capabilities` reuses the probes `new` already performs.

The writability answer stays advisory even with sudo: an immutable image can have a writable `/usr`
for other reasons, and a writable one can still refuse a specific install. The report informs the
agent's choice; it does not promise an install will work.

The `capabilities --json` keys become part of the CLI contract when they ship, so they are named as if
permanent.
