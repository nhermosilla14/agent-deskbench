# A desktop image must satisfy a checkable contract

- Status: Accepted
- Date: 2026-11-26
- Deciders: Nicolás Hermosilla Polanco
- Approved by: Nicolás Hermosilla Polanco
- Spec area: images.md

## Context

Once a flavour can point at any OCI image, the CLI can no longer assume the layout of the base image.
`url` assumes a viewer on one port and one path, `shot` assumes `/usr/local/bin/deskbench-capture`,
`exec` assumes a shell, and bind mounts assume a process uid that maps to the host user. A random
third-party desktop image gets some of these wrong.

Without validation, `new` reports success and the failure surfaces later, when an agent tries to
take a screenshot or run the application. That wastes the run and the human's attention. Third-party
images also differ in port, path, user, environment and screenshot tool, so hardcoding the base
layout would exclude exactly the images this feature is for.

Whatever `new` decides has to remain available to later calls. A host state file would break the
rule that the container runtime is the only state store; container labels are the existing
mechanism.

## Decision

A desktop image is viable only if it satisfies the **desktop contract**:

1. an HTTP or HTTPS viewer on a configured container port and path;
2. a screenshot command that writes a non-empty file to a path deskbench chooses;
3. a shell (`sh`) for `exec`;
4. a process user whose uid can be mapped to the invoking host user, so bind mounts keep their
   ownership in both directions.

A flavour manifest may describe those points; defaults reproduce the built-in image.

- `[viewer]`: `port` (default `6080`), `path` (default `/vnc.html?autoconnect=1&resize=scale`),
  `scheme` (`http` or `https`, default `http`) and `timeout` in seconds (default `30`). Readiness
  accepts 2xx, 3xx, 401 and 403, because a viewer may ask for credentials before it renders.
- `[run]`: `user` (default `1000:1000`), optional `entrypoint` and `command` argv, and an `env`
  string map. `{width}` and `{height}` are substituted in environment values, so images with their
  own geometry variables can honour `--size`. The runtime maps the host user to the configured uid,
  starts the container as that user, and uses the same user for `exec`.
- `[screenshot]`: `command` argv with `{output}` and `{settle}` placeholders, plus a `settle`
  boolean. Built-ins use `/usr/local/bin/deskbench-capture {output} {settle}` with `settle = false`;
  custom commands default to `settle = true`.
- The manifest rejects unknown keys, so a typo cannot silently fall back to a default.
- `new` resolves the flavour once, runs the container, waits for the viewer, then probes the
  contract inside the container:
  - run the screenshot command to a temporary path and require a non-empty file;
  - run `sh -lc true`.
  If either probe fails, `new` stops the container and exits 1 naming the flavour and the missing
  capability. A bare `--image` uses the same defaults and the same probe.
- `new` writes the effective viewer and screenshot settings as container labels
  (`deskbench.viewer.port`, `deskbench.viewer.path`, `deskbench.viewer.scheme`,
  `deskbench.screenshot` and the user). `ls`, `url`, `shot` and `ask` read those labels. Containers
  without them fall back to the built-in defaults, so desktops created before this change keep
  working. Editing a manifest never mutates a running desktop.
- With `settle = true`, `shot` captures until two consecutive frames match, bounded in time. With
  `settle = false` it captures once and trusts the command's own waiting.
- The contract is a viability check, not a sandbox.

## Alternatives considered

- **Trust the image and fail on the first `shot`** — the desktop exists, the agent runs, and the
  failure arrives at the worst moment with no clean-up.
- **Only allow deskbench-built images** — safe, but rejects the third-party images the feature
  exists for.
- **Build an adapter layer that installs Xvnc and noVNC into any image** — only works for apt-based
  images, needs a build, and reverses the decision that the CLI never builds.
- **Speak RFB from the host to capture the screen** — a VNC client implementation inside deskbench
  and a second way to take screenshots; an in-image command is simpler and works with any tool the
  image already ships.
- **Detect the viewer port and screenshot tool from image metadata** — image metadata does not say
  where the viewer is or which tool exists, and guessing is worse than an explicit manifest.
- **Store the resolved configuration in a file under the user config directory** — breaks the
  "container runtime is the only state store" rule and can go stale.
- **Validate only at `shot` time and remember success in a label** — labels are immutable, and the
  first failure still arrives after `new` reported success.

## Consequences

- `new` is slower by one screenshot and one shell probe. That cost is deliberate and bounded by the
  viewer timeout.
- An image with a viewer but no screenshot tool is refused. That is the point: without `shot` the
  desktop is not usable by the agent.
- Images that run as root need `[run] user = "0:0"` to keep bind ownership. Under rootful Docker
  that means the process runs as host root; the documentation must say so and recommend rootless
  Podman.
- Desktops created before this change have no labels and keep the old default viewer path; that
  compatibility path can be removed in a later change.
- The manifest schema becomes a supported interface. Adding a field is a design decision, not a
  drive-by edit.
- The fixture test has to build an image that proves a non-default port, path, environment and
  screenshot command through the CLI.
