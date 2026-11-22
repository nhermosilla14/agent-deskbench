# Discover through a skill, install through the existing console script, defer MCP

- Status: Accepted
- Date: 2026-11-22
- Deciders: Nicolás Hermosilla Polanco
- Approved by: Nicolás Hermosilla Polanco

## Context

The CLI works, but an agent in a fresh session has no way to learn it exists. Three mechanisms were
on the table: documentation in the repository, a skill (Markdown loaded into the agent's context),
and an MCP server (a typed tool surface). They solve different problems: discovery, invocation and
result plumbing.

The tool also lives in a checkout and runs as `python3 -m deskbench`, which forces every caller to
know the path — friction that shows up on every call. The package already declares a console script
(`deskbench = deskbench.cli:main`) in `pyproject.toml`, so the only missing piece is *installing* it.

## Decision

Ship **a skill** as the discovery mechanism, and install the **existing console script** into
`~/.local/bin` with `uv tool install`, which already exists on the target machine and copes with
Ubuntu's externally-managed Python. Defer MCP.

The skill is authored at `skill/SKILL.md` and installed by copying to `~/.agents/skills/agent-deskbench`;
`task install-skill` does it. `task install-cli` runs `uv tool install --editable .`, so edits in the
checkout take effect without reinstalling.

A test asserts that every verb the skill documents exists in the parser, so documentation cannot
drift from the CLI.

## Alternatives considered

- **README only** — invisible to an agent that was not told to read it.
- **A hand-written launcher script** — redundant: the console script already exists, and a shell
  wrapper would have to fake `PYTHONPATH` where a real install links the package.
- **`pip install --user .`** — refused on this machine: Ubuntu ships an externally-managed Python.
- **MCP over stdio** — better ergonomics for one capability (returning screenshots as image blocks),
  but ~200 lines, a protocol dependency, and an awkward fit for the blocking `ask`. Not justified
  until the skill proves insufficient.

## Consequences

Two copies of the skill exist once installed (the repo source and the installed copy), reconciled by
`task install-skill`. `uv tool install` needs network access once, to fetch the build backend. If MCP
is built later it must wrap `deskbench.engine`, not reimplement it.
