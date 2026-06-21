"""Utilidades para cabeceras de tabla redimensionables, reordenables y ocultables."""
from __future__ import annotations

from typing import Callable, Optional, Sequence

from PyQt6.QtCore import QByteArray, Qt
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import QHeaderView, QMenu

from i18n.json_translation import tr


def setup_resizable_header(
    header: QHeaderView,
    column_count: int,
    *,
    on_changed: Optional[Callable[[], None]] = None,
) -> None:
    """Activa mover y redimensionar columnas (sin menú contextual)."""
    header.setSectionsMovable(True)
    header.setStretchLastSection(True)
    header.setDefaultSectionSize(110)
    header.setContextMenuPolicy(Qt.ContextMenuPolicy.DefaultContextMenu)

    for index in range(column_count):
        header.setSectionResizeMode(index, QHeaderView.ResizeMode.Interactive)

    if on_changed:
        header.sectionMoved.connect(lambda *_: on_changed())
        header.sectionResized.connect(lambda *_: on_changed())


def setup_configurable_header(
    header: QHeaderView,
    column_keys: Sequence[str],
    *,
    on_changed: Optional[Callable[[], None]] = None,
    get_column_label: Callable[[str], str],
) -> None:
    """Activa mover, redimensionar y menú contextual de visibilidad (legacy)."""
    setup_resizable_header(header, len(column_keys), on_changed=on_changed)
    header.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
    header.customContextMenuRequested.connect(
        lambda pos: _show_column_menu(header, column_keys, get_column_label, on_changed, pos)
    )


def set_column_visible(
    header: QHeaderView,
    column: int,
    visible: bool,
    on_changed: Optional[Callable[[], None]] = None,
) -> bool:
    """Muestra u oculta una columna. Devuelve False si no se permitió ocultar la última."""
    if not visible and visible_column_count(header) <= 1:
        return False
    header.setSectionHidden(column, not visible)
    if on_changed:
        on_changed()
    return True


def reset_table_columns(
    header: QHeaderView,
    column_keys: Sequence[str],
    on_changed: Optional[Callable[[], None]] = None,
) -> None:
    """Restablece visibilidad y orden de columnas."""
    for index in range(len(column_keys)):
        header.setSectionHidden(index, False)
    header.setSectionsMovable(True)
    for index in range(len(column_keys)):
        header.moveSection(header.visualIndex(index), index)
    if on_changed:
        on_changed()


def save_header_state(header: QHeaderView) -> str:
    return header.saveState().toBase64().data().decode("ascii")


def restore_header_state(header: QHeaderView, state_b64: str) -> bool:
    if not state_b64:
        return False
    try:
        data = QByteArray.fromBase64(state_b64.encode("ascii"))
    except Exception:
        return False
    if data.isEmpty():
        return False
    return bool(header.restoreState(data))


def visible_column_count(header: QHeaderView) -> int:
    return sum(1 for index in range(header.count()) if not header.isSectionHidden(index))


def _show_column_menu(
    header: QHeaderView,
    column_keys: Sequence[str],
    get_column_label: Callable[[str], str],
    on_changed: Optional[Callable[[], None]],
    pos,
) -> None:
    logical = header.logicalIndexAt(pos)
    menu = QMenu(header)
    actions: list[tuple[QAction, int]] = []

    for index, key in enumerate(column_keys):
        action = QAction(get_column_label(key), menu)
        action.setCheckable(True)
        action.setChecked(not header.isSectionHidden(index))
        action.triggered.connect(
            lambda checked, col=index: set_column_visible(
                header, col, checked, on_changed
            )
        )
        menu.addAction(action)
        actions.append((action, index))

    if logical >= 0:
        menu.addSeparator()
        reset_action = menu.addAction(tr("table_columns_reset"))
        reset_action.triggered.connect(
            lambda: reset_table_columns(header, column_keys, on_changed)
        )

    menu.exec(header.mapToGlobal(pos))


# Alias internos para el menú legacy
_toggle_column = set_column_visible
_reset_columns = reset_table_columns
