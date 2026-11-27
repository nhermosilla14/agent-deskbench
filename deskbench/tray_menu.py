"""The tray's menu content as plain data, so it can be asserted without GTK.

The tray renders this model and rebuilds its menu only when :func:`signature` changes, so a
tick that finds nothing new leaves the menu alone.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from . import engine, settings as settings_store, term


@dataclass(frozen=True)
class TerminalItem:
    session: str
    attached: int

    @property
    def label(self) -> str:
        return f"{self.session}  ·  {self.attached} attached"


@dataclass(frozen=True)
class DesktopMenu:
    name: str
    state: str
    url: str
    terminals: tuple[TerminalItem, ...]


@dataclass(frozen=True)
class MenuModel:
    desktops: tuple[DesktopMenu, ...]
    new_terminal_size: str


def build(
    desktops: Sequence[engine.Desktop],
    sessions: Mapping[str, Sequence[term.TermSession]],
    settings: settings_store.Settings,
) -> MenuModel:
    """Describe the menu. Only tmux sessions appear as terminals: a private shell is never one."""
    entries = tuple(
        DesktopMenu(
            name=desktop.name,
            state=desktop.state,
            url=desktop.url,
            terminals=tuple(
                TerminalItem(session=entry.name, attached=entry.attached)
                for entry in sessions.get(desktop.name, ())
            ),
        )
        for desktop in desktops
    )
    return MenuModel(desktops=entries, new_terminal_size=settings.default_size)


def signature(model: MenuModel) -> tuple:
    """Hashable summary of what the menu shows; equal signatures mean no rebuild is needed."""
    return (
        model.new_terminal_size,
        tuple(
            (
                desktop.name,
                desktop.state,
                desktop.url,
                tuple((item.session, item.attached) for item in desktop.terminals),
            )
            for desktop in model.desktops
        ),
    )
