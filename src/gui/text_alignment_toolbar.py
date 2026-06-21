"""Barra de alineación de texto estilo Office (grupo de 3 botones con iconos)."""
from __future__ import annotations

from typing import Callable, Optional

from PyQt6.QtCore import Qt, QSize, pyqtSignal
from PyQt6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap
from PyQt6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from gui.inventory_table_alignment import (
    DEFAULT_TABLE_ALIGNMENT,
    TABLE_ALIGN_CENTER,
    TABLE_ALIGN_LEFT,
    TABLE_ALIGN_RIGHT,
    normalize_table_alignment,
)
from i18n.json_translation import tr
from utils.theme_utils import is_dark_mode


def _line_color() -> QColor:
    return QColor("#F1F1F1" if is_dark_mode() else "#1E1E1E")


def alignment_icon(mode: str, size: int = 16) -> QIcon:
    """Icono monocromático de alineación (tres líneas, estilo Word)."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    pen = QPen(_line_color())
    pen.setWidthF(1.4)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    painter.setPen(pen)

    margin = size * 0.2
    width = size - 2 * margin
    y1 = size * 0.28
    y2 = size * 0.5
    y3 = size * 0.72
    lengths = (width * 0.95, width * 0.72, width * 0.55)

    for y, line_len in zip((y1, y2, y3), lengths):
        if mode == TABLE_ALIGN_LEFT:
            x1, x2 = margin, margin + line_len
        elif mode == TABLE_ALIGN_RIGHT:
            x1, x2 = size - margin - line_len, size - margin
        else:
            half = line_len / 2
            center = size / 2
            x1, x2 = center - half, center + half
        painter.drawLine(int(x1), int(y), int(x2), int(y))

    painter.end()
    return QIcon(pixmap)


class TextAlignmentToolbar(QWidget):
    """Grupo compacto izquierda / centro / derecha con botones unidos (estilo Windows)."""

    alignment_changed = pyqtSignal(str)

    _MODES = (TABLE_ALIGN_LEFT, TABLE_ALIGN_CENTER, TABLE_ALIGN_RIGHT)
    _I18N_KEYS = {
        TABLE_ALIGN_LEFT: "inventory_table_align_left",
        TABLE_ALIGN_CENTER: "inventory_table_align_center",
        TABLE_ALIGN_RIGHT: "inventory_table_align_right",
    }

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        *,
        on_changed: Optional[Callable[[str], None]] = None,
    ) -> None:
        super().__init__(parent)
        self._on_changed = on_changed
        self._loading = False
        self._buttons: dict[str, QToolButton] = {}

        self._button_group = QButtonGroup(self)
        self._button_group.setExclusive(True)

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)

        for index, mode in enumerate(self._MODES):
            button = QToolButton()
            button.setObjectName(f"TextAlign{mode.title()}Button")
            button.setCheckable(True)
            button.setAutoRaise(False)
            button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
            button.setFixedSize(32, 28)
            button.setIconSize(QSize(16, 16))
            button.setProperty("alignMode", mode)
            button.setProperty("segmentIndex", index)
            button.setProperty("segmentCount", len(self._MODES))
            self._button_group.addButton(button)
            self._buttons[mode] = button
            button.clicked.connect(lambda _checked, m=mode: self._on_button_clicked(m))
            row.addWidget(button)

        frame = QFrame()
        frame.setObjectName("TextAlignmentButtonFrame")
        frame.setLayout(row)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.addWidget(frame)

        self.set_alignment(DEFAULT_TABLE_ALIGNMENT, notify=False)
        self.recargar_textos()
        self.apply_visual_theme()

    def recargar_textos(self) -> None:
        for mode, button in self._buttons.items():
            button.setToolTip(tr(self._I18N_KEYS[mode]))

    def apply_visual_theme(self) -> None:
        for mode, button in self._buttons.items():
            button.setIcon(alignment_icon(mode))
        dark = is_dark_mode()
        border = "#3F3F46" if dark else "#CCCEDB"
        hover = "#3E3E42" if dark else "#E5F3FF"
        checked = "#094771" if dark else "#CCE8FF"
        accent = "#0078D4"
        self.setStyleSheet(
            f"""
            QFrame#TextAlignmentButtonFrame {{
                border: 1px solid {border};
                border-radius: 4px;
                background: transparent;
            }}
            QToolButton {{
                background: transparent;
                border: none;
                border-right: 1px solid {border};
                border-radius: 0;
                padding: 4px;
            }}
            QToolButton[segmentIndex="0"] {{
                border-top-left-radius: 3px;
                border-bottom-left-radius: 3px;
            }}
            QToolButton[segmentIndex="2"] {{
                border-right: none;
                border-top-right-radius: 3px;
                border-bottom-right-radius: 3px;
            }}
            QToolButton:hover {{
                background-color: {hover};
            }}
            QToolButton:checked {{
                background-color: {checked};
                border-color: {accent};
            }}
            """
        )

    def get_alignment(self) -> str:
        button = self._button_group.checkedButton()
        if button is None:
            return DEFAULT_TABLE_ALIGNMENT
        mode = button.property("alignMode")
        return normalize_table_alignment(str(mode) if mode else None)

    def set_alignment(self, mode: str, *, notify: bool = False) -> None:
        normalized = normalize_table_alignment(mode)
        button = self._buttons.get(normalized)
        if button is None:
            return
        self._loading = True
        button.setChecked(True)
        self._loading = False
        if notify:
            self._emit_changed(normalized)

    def _on_button_clicked(self, mode: str) -> None:
        if self._loading:
            return
        self._emit_changed(mode)

    def _emit_changed(self, mode: str) -> None:
        normalized = normalize_table_alignment(mode)
        self.alignment_changed.emit(normalized)
        if self._on_changed:
            self._on_changed(normalized)
