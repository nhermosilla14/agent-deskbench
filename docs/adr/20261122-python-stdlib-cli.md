# Python standard library only, unittest for tests

- Status: Accepted
- Date: 2026-11-22
- Deciders: Nicolás Hermosilla Polanco
- Approved by: Nicolás Hermosilla Polanco

## Context

The tool is a thin orchestration layer: it shells out to Podman, parses its JSON, opens a browser and
drives GTK. The host may have no reachable package index, no virtualenv tooling, and an agent that
must not spend its budget on environment repair. GTK and AppIndicator must come from system packages
(`python3-gi`, `gir1.2-ayatanaappindicator3-0.1`) either way, because they are not pip-installable in
practice.

## Decision

Python 3.11 or newer, standard library only, no runtime dependencies. Tests use `unittest` and run
with `python3 -m unittest discover -s tests`. Task automation uses a Taskfile. GTK is imported
lazily so that every CLI verb works on a machine without `python3-gi`.

## Alternatives considered

- **Click or Typer for the CLI** — nicer ergonomics, but a dependency for `argparse`-sized work.
- **pytest** — better assertions and fixtures, but it is not installed here and buys little for an
  end-to-end suite that mostly shells out.
- **Go single binary** — fastest start and no interpreter, but much slower to iterate on GTK tray
  work, and the developer's default for glue is Python.

## Consequences

No install step beyond the system packages, and the tool runs from a checkout. Verbose test
boilerplate and no fixture ecosystem; `subprocess` plumbing is written by hand. If the CLI surface
grows past roughly a dozen verbs with shared state, revisit the parser decision.
