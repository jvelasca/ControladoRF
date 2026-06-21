"""Atajos de teclado F1–F10 del módulo Monitor."""
from __future__ import annotations

from typing import Callable

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import QWidget

# Etiquetas estándar para tooltips (coinciden con F1–F10).
MONITOR_SHORTCUTS = {
    "help": "F1",
    "transport": "F2",
    "supervision_tree": "F3",
    "ack_all": "F4",
    "thresholds": "F5",
    "history": "F6",
    "export_report": "F7",
    "locate": "F8",
    "ack_one": "F9",
    "trigger": "F10",
}


def setup_monitor_shortcuts(
    host: QWidget,
    *,
    get_controller: Callable[[], object | None],
    is_monitor_active: Callable[[], bool],
) -> None:
    """Registra F1–F10; solo actúan con el módulo Monitor activo."""

    def _guard(slot):
        def wrapped() -> None:
            if not is_monitor_active():
                return
            controller = get_controller()
            if controller is None:
                return
            slot(controller)

        return wrapped

    # F2 (Play/Stop) se registra en MainWindow junto al atajo de Inventario.
    bindings = (
        ("F1", lambda c: c.show_supervision_help()),
        ("F3", lambda c: c.show_supervision_tree_panel()),
        ("F4", lambda c: c._on_supervision_ack_all()),
        ("F5", lambda c: c.show_supervision_thresholds_dialog()),
        ("F6", lambda c: c.show_supervision_events_dialog()),
        ("F7", lambda c: c.export_supervision_events()),
        ("F8", lambda c: c.locate_selected_supervision_channel()),
        ("F9", lambda c: c.ack_selected_supervision_channel()),
        ("F10", lambda c: c.arm_trigger()),
    )
    refs: list[QShortcut] = []
    for key, handler in bindings:
        shortcut = QShortcut(QKeySequence(key), host)
        shortcut.setContext(Qt.ShortcutContext.WindowShortcut)
        shortcut.activated.connect(_guard(handler))
        refs.append(shortcut)
    setattr(host, "_monitor_shortcut_refs", refs)
