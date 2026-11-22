# Adopt intents, ADRs, spec and vertical slices

- Status: Accepted
- Date: 2026-11-22
- Deciders: Nicolás Hermosilla Polanco
- Approved by: Nicolás Hermosilla Polanco

## Context

The project will be extended by agents working with limited context, over many sessions, on a
codebase whose behaviour (process lifetime, container lifecycle, human handoff) is easy to break
silently. Decisions taken in conversation are lost unless written down, and "what the system does"
must be readable without running it.

## Decision

Follow the vendored `general-software-development` skill: work is sized, then driven by intents
(what must become true), ADRs (why), and vertical slices (what is built next). `docs/spec/` records
delivered behaviour with the tests that prove it. `docs/branch/` holds working records and is empty
between branches.

## Alternatives considered

- **Issues in a tracker** — not available: the repository is local-only for now, and the records must
  live with the code.
- **A single design document** — rots quickly; it cannot distinguish decided from delivered, and it
  gives no test names.

## Consequences

Every change carries a small documentation cost, and a full-loop change needs three approvals. In
exchange, a new agent can learn the contracts from `docs/spec/` and the trade-offs from `docs/adr/`
without replaying this conversation.
