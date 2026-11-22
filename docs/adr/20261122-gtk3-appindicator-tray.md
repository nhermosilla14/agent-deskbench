# Tray built on GTK 3 and AyatanaAppIndicator

- Status: Accepted
- Date: 2026-11-22
- Deciders: Nicolás Hermosilla Polanco
- Approved by: Nicolás Hermosilla Polanco

## Context

The tray must expose a dynamic menu of running desktops on a Wayland session. On Linux, a panel icon
is a StatusNotifierItem published on the session bus; GTK's own `Gtk.StatusIcon` is gone from GTK 4
and unreliable on Wayland. The candidates are PyQt6's `QSystemTrayIcon` (which speaks SNI) and
PyGObject with `AyatanaAppIndicator3`.

The tray is long-lived only while desktops exist, but it still competes for memory with the
developer's editor; PyQt6 pulls in the whole Qt stack.

## Decision

Use PyGObject (`python3-gi`) with GTK 3 and `AyatanaAppIndicator3`. The indicator status is
`ACTIVE` while the process lives; process death removes the item, so no explicit hide path is
needed. The same `gi` session-bus access delivers notifications for `ask`.

## Alternatives considered

- **PyQt6** — fewer lines of menu code, but roughly 60–80 MB resident against 15–25 MB, and a large
  dependency for a menu.
- **A compiled tray (Rust `ksni`)** — under 10 MB and instant start, but a second language and
  toolchain for one small window.
- **Rendering the icon ourselves over raw D-Bus** — no benefit over libayatana, which is already
  installed.

## Consequences

The tray requires `python3-gi` plus the AppIndicator introspection data on the host; the CLI does
not. GTK 3 menu construction is verbose. GNOME users need the AppIndicator shell extension, which is
documented in `README.md`.
