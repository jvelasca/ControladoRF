"""Control numérico profesional para toolbar Monitor (spin + menú …)."""
from __future__ import annotations

from typing import Callable, Optional

from PyQt6.QtCore import QEvent, Qt, QLocale, QTimer, pyqtSignal
from PyQt6.QtGui import QFont, QValidator
from PyQt6.QtWidgets import (
    QDoubleSpinBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from core.monitor.monitor_format import parse_locale_float
from gui.monitor.monitor_lcd_styles import apply_lcd_readout_style


class MonitorDecimalSpinBox(QDoubleSpinBox):
    """Acepta coma o punto decimal; confirma al pulsar Enter o perder foco."""

    valueCommitted = pyqtSignal(float)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        self._programmatic = False
        self._manual_edit = False
        super().__init__(parent)
        self.setLocale(QLocale.c())
        self.setKeyboardTracking(False)
        self.setAccelerated(True)
        self.setCorrectionMode(QDoubleSpinBox.CorrectionMode.CorrectToNearestValue)
        le = self.lineEdit()
        if le is not None:
            le.setAlignment(Qt.AlignmentFlag.AlignRight)
            le.installEventFilter(self)
            le.editingFinished.connect(self._commit_line_text)
        self.valueChanged.connect(self._emit_if_user_action)

    def selectAll(self) -> None:
        editor = self.lineEdit()
        if editor is not None:
            editor.selectAll()

    def is_editing(self) -> bool:
        editor = self.lineEdit()
        if editor is not None and editor.hasFocus():
            return True
        return self._manual_edit

    def commit_editing(self) -> None:
        if self.is_editing():
            self._commit_line_text()

    def cancel_editing(self) -> None:
        self._manual_edit = False
        editor = self.lineEdit()
        if editor is not None and editor.hasFocus():
            editor.clearFocus()

    def eventFilter(self, obj, event) -> bool:
        if obj is self.lineEdit():
            if event.type() == QEvent.Type.FocusIn:
                self._manual_edit = True
                QTimer.singleShot(0, self._select_all_text)
            elif event.type() == QEvent.Type.MouseButtonPress:
                self._manual_edit = True
                QTimer.singleShot(0, self._select_all_text)
            elif event.type() == QEvent.Type.KeyPress:
                key = event.key()
                if key in (
                    Qt.Key.Key_Period,
                    Qt.Key.Key_Comma,
                    Qt.Key.KeypadPeriod,
                    Qt.Key.KeypadComma,
                ):
                    editor = self.lineEdit()
                    if editor is not None:
                        editor.insert(".")
                        return True
                if key in range(int(Qt.Key.Key_A), int(Qt.Key.Key_Z) + 1):
                    return True
        return super().eventFilter(obj, event)

    def _select_all_text(self) -> None:
        editor = self.lineEdit()
        if editor is not None and editor.hasFocus():
            editor.selectAll()

    def validate(self, text: str, pos: int):
        if "," in text and "." not in text:
            text = text.replace(",", ".")
        if self.is_editing():
            stripped = text.strip()
            if not stripped:
                return (QValidator.State.Intermediate, text, pos)
            try:
                parse_locale_float(stripped)
                return (QValidator.State.Acceptable, text, pos)
            except ValueError:
                if stripped[-1] in ".,0123456789":
                    return (QValidator.State.Intermediate, text, pos)
        return super().validate(text, pos)

    def valueFromText(self, text: str) -> float:
        try:
            return parse_locale_float(text)
        except ValueError:
            return self.value()

    def setValue(self, value: float) -> None:
        if self.is_editing() and not self._programmatic:
            return
        self._programmatic = True
        try:
            super().setValue(value)
        finally:
            self._programmatic = False

    def setMaximum(self, value: float) -> None:
        if self.is_editing():
            return
        self._programmatic = True
        try:
            super().setMaximum(value)
        finally:
            self._programmatic = False

    def setMinimum(self, value: float) -> None:
        if self.is_editing():
            return
        super().setMinimum(value)

    def setSingleStep(self, step: float) -> None:
        if self.is_editing():
            return
        super().setSingleStep(step)

    def setReadOnly(self, read_only: bool) -> None:
        if self.is_editing():
            return
        super().setReadOnly(read_only)

    def _emit_if_user_action(self, value: float) -> None:
        if self._programmatic:
            return
        self.valueCommitted.emit(float(value))

    def _parse_editor_text(self, text: str) -> Optional[float]:
        text = text.strip()
        suffix = self.suffix()
        if suffix and text.endswith(suffix):
            text = text[: -len(suffix)].strip()
        prefix = self.prefix()
        if prefix and text.startswith(prefix):
            text = text[len(prefix) :].strip()
        if not text:
            return None
        return parse_locale_float(text)

    def _commit_line_text(self) -> None:
        editor = self.lineEdit()
        if editor is None:
            return
        try:
            value = self._parse_editor_text(editor.text())
        except ValueError:
            value = None
        if value is None:
            clamped = float(self.value())
        else:
            clamped = max(self.minimum(), min(self.maximum(), value))
        self._programmatic = True
        try:
            super().setValue(clamped)
        finally:
            self._programmatic = False
        self._manual_edit = False
        self.valueCommitted.emit(clamped)


class MonitorNumericControl(QFrame):
    """Etiqueta + spin con flechas integradas + botón … opcional."""

    value_changed = pyqtSignal(float)

    def __init__(
        self,
        title: str,
        *,
        suffix: str = "",
        decimals: int = 3,
        minimum: float = 0.0,
        maximum: float = 9999.0,
        step: float = 1.0,
        menu_builder: Optional[Callable[[QMenu], None]] = None,
        compact: bool = False,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._menu_builder = menu_builder
        self._block_emit = False
        self.setObjectName("MonitorNumericControlCompact" if compact else "MonitorNumericControl")
        apply_lcd_readout_style(self)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(2 if compact else 4, 1 if compact else 2, 2 if compact else 4, 1 if compact else 2)
        layout.setSpacing(0)

        self._label = QLabel(title.upper(), self)
        self._label.setObjectName("MonitorLcdLabel")

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(2)
        self._value_row = row

        self._spin = MonitorDecimalSpinBox(self)
        self._spin.setObjectName("MonitorNumericSpin")
        self._spin.setDecimals(decimals)
        self._spin.setRange(minimum, maximum)
        self._spin.setSingleStep(step)
        if suffix:
            self._spin.setSuffix(suffix)
        font = QFont("Consolas", 9 if compact else 10)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self._spin.setFont(font)
        self._spin.valueCommitted.connect(self._on_spin_committed)

        row.addWidget(self._spin, stretch=1)

        self._menu_btn: Optional[QToolButton] = None
        if menu_builder is not None:
            self._menu_btn = QToolButton(self)
            self._menu_btn.setObjectName("MonitorNumericMenuBtn")
            self._menu_btn.setText("…")
            self._menu_btn.setFixedWidth(20 if compact else 22)
            self._menu_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            self._menu_btn.clicked.connect(self._show_menu)
            row.addWidget(self._menu_btn)

        layout.addWidget(self._label)
        layout.addLayout(row)

    def insert_value_row_widget(self, widget: QWidget, *, before_menu: bool = True) -> None:
        """Inserta un botón inline (p. ej. FC/F) antes del menú …."""
        if before_menu and self._menu_btn is not None:
            idx = self._value_row.indexOf(self._menu_btn)
            self._value_row.insertWidget(idx, widget, alignment=Qt.AlignmentFlag.AlignVCenter)
        else:
            self._value_row.addWidget(widget, alignment=Qt.AlignmentFlag.AlignVCenter)

    def set_title(self, title: str) -> None:
        self._label.setText(title.upper())

    def set_readout_mode(self, mode: str) -> None:
        self._label.setProperty("readoutMode", mode)
        self._label.style().unpolish(self._label)
        self._label.style().polish(self._label)

    def set_tooltips(self, spin_tip: str = "", menu_tip: str = "") -> None:
        self._spin.setToolTip(spin_tip)
        if self._menu_btn is not None and menu_tip:
            self._menu_btn.setToolTip(menu_tip)

    def set_value(self, value: float, *, force: bool = False) -> None:
        if self.is_user_editing() and not force:
            return
        self._block_emit = True
        if force and self.is_user_editing():
            self._spin._manual_edit = False
            self._spin._programmatic = True
        try:
            self._spin.setValue(value)
        finally:
            self._spin._programmatic = False
            self._block_emit = False

    def is_user_editing(self) -> bool:
        return self._spin.is_editing()

    def commit_editing(self) -> None:
        self._spin.commit_editing()

    def get_value(self) -> float:
        return float(self._spin.value())

    def set_step(self, step: float) -> None:
        if self.is_user_editing():
            return
        self._spin.setSingleStep(step)

    def set_maximum(self, value: float, *, force: bool = False) -> None:
        if self.is_user_editing() and not force:
            return
        self._block_emit = True
        try:
            self._spin.setMaximum(value)
        finally:
            self._block_emit = False

    def set_minimum(self, value: float, *, force: bool = False) -> None:
        if self.is_user_editing() and not force:
            return
        self._spin.setMinimum(value)

    def set_read_only(self, read_only: bool, *, force: bool = False) -> None:
        if self.is_user_editing() and not force:
            return
        self._spin.setReadOnly(read_only)
        self._spin.setButtonSymbols(
            QDoubleSpinBox.ButtonSymbols.NoButtons
            if read_only
            else QDoubleSpinBox.ButtonSymbols.UpDownArrows
        )

    def set_value_mode(self, mode: str) -> None:
        """Indica visualmente AUTO (auto) vs valor manual (manual | normal)."""
        self._spin.setProperty("valueMode", mode)
        self._spin.style().unpolish(self._spin)
        self._spin.style().polish(self._spin)

    def _on_spin_committed(self, value: float) -> None:
        if self._block_emit:
            return
        self.value_changed.emit(value)

    def _show_menu(self) -> None:
        if self._menu_builder is None or self._menu_btn is None:
            return
        self.show_popup_menu(
            self._menu_btn.mapToGlobal(self._menu_btn.rect().bottomLeft())
        )

    def show_popup_menu(self, global_pos) -> None:
        if self._menu_builder is None:
            return
        menu = QMenu(self)
        self._menu_builder(menu)
        menu.exec(global_pos)
