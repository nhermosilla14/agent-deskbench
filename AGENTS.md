# AGENTS.md

## Project overview

See `README.md` for overview, structure, usage and all commands, and `docs/vision.md` for goals.

## Rules (mandatory, for humans and agents)

The skill vendored at `.agents/skills/general-software-development/` holds the full rules. This
list is the entry point, not a second copy.

1. **Use the `general-software-development` skill.** All work on this project (features, fixes,
   refactors, docs, config) MUST load and follow it first, from the vendored copy: that is the
   version this project follows. Do not edit that copy by hand; it changes only through the skill's
   vendoring step. A subagent working from an orchestrator's brief follows the brief and does not
   start the workflow itself.
2. **Size the change first.** Propose the tier (trivial or full loop, as the skill defines them)
   with the reason, and wait for confirmation. Trivial changes need no records.
3. **Follow the loop.** Requirements (intents) → design (ADRs) → vertical slices → code and test one
   slice at a time, each stage approved by the user before the next. Working records live in
   `docs/branch/`, which must be empty to merge. Any decision affecting architecture, dependencies,
   interfaces, data formats, security, deployment or scope needs an ADR first.
4. **Keep docs current.** `docs/spec/` describes what the system does today, with the tests that
   prove it; `docs/architecture.md` how it is built; `docs/adr/` why. Update them, `docs/vision.md`,
   `docs/README.md` and `README.md` whenever what they describe changes, and check them before
   finishing. Documented commands must work.
5. **Ask, don't invent.** If goals are unclear, ask the user and record the answer in `docs/`, using
   specialized discovery or interview skills when available. Ask also before resolving a conflict
   between decisions.
6. **Orchestrate full-loop work.** The agent talking to the user plans, delegates, reviews and
   reports; the work goes to subagents, specialized over general, as the skill describes.
7. **Tooling and workflow live in Conventions**, not ADRs. Edit them in place.
8. **Update this file** when rules or conventions change.

## Conventions

- Tooling: Python 3.11+ standard library only (no third-party runtime packages), `unittest` for
  tests, Taskfile for task automation, Podman for containers, ShellCheck-clean POSIX shell for the
  image entrypoint. `python3 -m compileall` is the syntax gate.
- Git workflow: trunk-based. Integration branch: `main`. Short-lived `feat/<slug>` or `fix/<slug>`
  branches created from an up-to-date `main`; merge back to `main` when finalized. Remote: `origin`
  on GitHub (`nhermosilla14/agent-deskbench`); push `main` when a branch is finalized.
- Workflow: branch names as above; commits `type: imperative summary` (feat, fix, docs, test,
  chore); each slice lands as its own commit once its end-to-end test passes.
- Style: PEP 8, 4-space indents, `from __future__ import annotations`, type hints on public
  functions, docstrings that state the contract rather than the mechanics. Keep modules small.
- Never commit secrets; keep them out of git via `.gitignore` and provide `.env.example`.
