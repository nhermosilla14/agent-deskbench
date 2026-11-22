# GUI verbs re-exec under the system interpreter

- Status: Accepted
- Date: 2026-11-22
- Deciders: Nicolás Hermosilla Polanco
- Approved by: Nicolás Hermosilla Polanco
- Spec area: lifecycle.md

## Context

PyGObject is a system package: it is built against the distribution's glib and is not casually
installable into a virtualenv. The console script is installed with `uv tool`, which creates an
isolated environment, so `import gi` fails there even though `/usr/bin/python3` has it.

The symptom was invisible for a specific reason: `new` spawned the tray with its stderr going to
`/dev/null`, so a tray that died on import looked exactly like a tray that worked — until the user
noticed there was no icon.

## Decision

Before dispatching `tray` or `ask`, if `gi` cannot be imported, re-exec the same arguments under the
first system interpreter that exists (`/usr/bin/python3`, `/usr/local/bin/python3`) with
`PYTHONPATH` pointing at the package. If neither exists, behaviour is unchanged and the verb fails
with its existing message.

The tray is spawned with stdout and stderr appended to `$XDG_RUNTIME_DIR/deskbench/tray.log`, so a
start-up failure is always diagnosable.

## Alternatives considered

- **Install PyGObject into the tool environment** — needs compilers and matching glib headers, and
  would drift from the distribution build.
- **Require running from a checkout** — the whole point of installing was to avoid that.
- **A shell wrapper that execs the system python** — equivalent, but it moves the knowledge into
  packaging where it cannot be tested; the re-exec is in the code and covered by a test.

## Consequences

The process identity changes once at start-up for two verbs, so `pgrep` shows the system interpreter
running `-m deskbench tray`. That is also what `lock.tray_pid` matches, and it keeps PID checks
honest. A machine without `/usr/bin/python3` (a container image, for instance) keeps the old
behaviour.
