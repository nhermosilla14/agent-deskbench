# Settings are host preferences edited by the tray

- Status: Accepted
- Date: 2026-11-27
- Deciders: Nicolás Hermosilla Polanco
- Approved by: Nicolás Hermosilla Polanco
- Spec area: settings.md, lifecycle.md

## Context

A human choosing `New terminal…` from the tray cannot type a grid, while the CLI requires one. The
value has to persist somewhere, and it is not derivable from the runtime the way a desktop's name or
URL is.

Two existing rules look like obstacles and are not, provided the scope is stated. The state-store
decision says "persist nothing", in a context that is explicitly about which desktops exist and what
serves them: it governs desktop state, which stays in Podman. The tray "only observes", in a
sentence about creating desktops: editing a per-user preference is neither a desktop nor a creation.

The user config directory already holds the flavour manifests, so preferences belong beside them.

## Decision

Settings live in `$XDG_CONFIG_HOME/agent-deskbench/settings.toml` (`~/.config/...` when the variable
is unset), resolved from the XDG config root only: `DESKBENCH_FLAVOURS_DIR` is a flavours-specific
override and must not redirect settings. Tests set `XDG_CONFIG_HOME`.

- TOML, like the manifests next to it, with one key: `[term] default_size = "120x40"`. It is read with
  `tomllib`, which is read-only, so writing uses a small writer for that fixed schema. Writes go to a
  temporary file and are moved into place with `os.replace`, so a crash mid-write cannot leave a
  half-file that resets the human's preference.
- An absent or unreadable file falls back to `120x40` instead of failing; an invalid value is refused
  where it is edited.
- The tray offers a Settings item that opens a separate `Gtk.Dialog` in the tray's own process: the
  toolkit and the GLib loop are already there, and a window can outlive the menu being dismissed,
  which a menu widget cannot. It has one field, `Default size for new terminals`, and Save and Cancel.
- The value is validated on Save with the same bounds as `--cells`. An invalid value is refused in the
  dialog and leaves the stored one untouched, so a half-typed `12` is never written.
- Closing the window hides it and the tray keeps running: `delete-event` hides and returns `True`.
  Returning `False` would end the GLib loop and take the tray down with the dialog.
- The setting applies to `New terminal…` only. `term start` still requires `--cells`, so an agent
  always states the grid it needs; the private shell follows the human's terminal.

## Alternatives considered

- **No setting, a fixed size for tray-created sessions** — contradicts the explicit-grid decision and
  leaves the human unable to tune a value they will notice.
- **Prompt for the size from inside the indicator menu** — nested dialogs from a StatusNotifierItem
  menu are unreliable across panels; a separate window can stay open and is testable.
- **Store the size in container labels** — immutable and per-container, for a preference that is
  per-user and predates any container.
- **GSettings or dconf** — a schema to install and a dependency for one key.
- **JSON instead of TOML** — stdlib writes and reads it, but a second format in a directory of TOML
  manifests is worse than five lines of writer for a schema that will not grow by itself.
- **A CLI verb to edit settings** — the window is the human's path; the CLI stays the agent's
  interface, which is already carrying enough verbs.

## Consequences

The tray writes a host file. That is a deliberate, documented exception, limited to preferences and
never to desktops: the state-store rule is untouched and this decision is deliberately scoped around
it rather than replacing it.

The file is per-user, inherited by every desktop, and survives `stop`. The tray is its only writer, so
no locking is needed. A corrupt file degrades to the default instead of blocking the tray, and the
atomic write narrows the window for corruption to almost nothing.

`tomllib` being read-only means the project gains one small serialiser, which must refuse to emit
anything it has not validated. The file's name and location become permanent the moment a user has
one, so they are chosen now and are not to be renamed.
