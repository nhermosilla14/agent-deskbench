# Keep Chromium's renderer sandbox

- Status: Accepted
- Date: 2026-11-22
- Deciders: Nicolás Hermosilla Polanco
- Approved by: Nicolás Hermosilla Polanco
- Spec area: cli.md

## Context

The `chromium-desk` wrapper was written while everything inside the container ran as root, where
Chromium refuses to start without `--no-sandbox`. After the switch to an unprivileged user the flag
was never revisited, so every session shipped with the renderer sandbox disabled and a permanent
yellow warning bar.

Measured on the current image: Chromium launches as uid 1000 with no sandbox flag, renders normally,
and prints no sandbox error. There is no `chrome-sandbox` helper in the package, and
`kernel.unprivileged_userns_clone` is 1, so Chromium uses the namespace sandbox.

## Decision

Drop `--no-sandbox`. The wrapper keeps only `--disable-dev-shm-usage`, because `/dev/shm` is 64 MB in
a container and Chromium degrades on heavy pages without it.

Documented fallback: on a host that blocks unprivileged user namespaces (or under a seccomp profile
that denies `CLONE_NEWUSER`), Chromium will refuse to start; the caller then passes `--no-sandbox`
explicitly and accepts the weakened boundary.

A test asserts the shipped wrapper does not disable the sandbox, so it cannot regress silently.

## Alternatives considered

- **Keep `--no-sandbox`** — simpler, and the container bounds the damage, but the pages under test are
  exactly the untrusted input, and the warning bar is noise an agent learns to ignore.
- **`--cap-add=SYS_ADMIN` or `seccomp=unconfined`** — trades a much larger privilege for the same
  result as the namespace sandbox already gives us.
- **Ship the SUID `chrome-sandbox` helper** — setuid binaries in a container are a worse default than
  relying on user namespaces.

## Consequences

The sandbox now depends on the host kernel allowing unprivileged user namespaces; on hardened hosts a
browser session fails to start until the caller opts out. That failure is visible and actionable
(Chromium prints it), unlike the previous silent downgrade.
