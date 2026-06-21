"""Lecturas estilo LCD de analizador profesional (R&S)."""

from __future__ import annotations



from typing import Callable, List, Optional, Tuple



from PyQt6.QtCore import Qt, pyqtSignal

from PyQt6.QtGui import QFont, QWheelEvent

from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QMenu, QPushButton, QVBoxLayout, QWidget



from gui.monitor.monitor_lcd_styles import apply_lcd_readout_style





class MonitorLcdReadout(QFrame):

    """Indicador LCD: etiqueta + valor, rueda, botones ▲▼ y menú."""



    value_changed = pyqtSignal(str)

    numeric_changed = pyqtSignal(float)

    step_up_requested = pyqtSignal()

    step_down_requested = pyqtSignal()



    def __init__(

        self,

        label: str,

        *,

        value: str = "---",

        readout_id: str = "",

        parent: Optional[QWidget] = None,

    ) -> None:

        super().__init__(parent)

        self.readout_id = readout_id

        self._numeric_value = 0.0

        self._wheel_step = 1.0

        self._wheel_enabled = False

        self._choice_items: List[Tuple[str, str]] = []

        self._current_choice_id = ""



        self.setObjectName("MonitorLcdReadout")

        self.setCursor(Qt.CursorShape.PointingHandCursor)

        apply_lcd_readout_style(self)



        layout = QVBoxLayout(self)

        layout.setContentsMargins(4, 2, 4, 2)

        layout.setSpacing(0)



        self._label = QLabel(label.upper(), self)

        self._label.setObjectName("MonitorLcdLabel")



        row = QHBoxLayout()

        row.setContentsMargins(0, 0, 0, 0)

        row.setSpacing(2)



        self._down_btn = QPushButton("−", self)

        self._down_btn.setObjectName("MonitorLcdStepDown")

        self._down_btn.setFixedWidth(18)

        self._down_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        self._down_btn.clicked.connect(self._on_step_down)

        self._down_btn.hide()



        self._value = QLabel(value, self)

        self._value.setObjectName("MonitorLcdValue")

        self._value.setAlignment(Qt.AlignmentFlag.AlignCenter)

        font = QFont("Consolas", 10)

        font.setStyleHint(QFont.StyleHint.Monospace)

        self._value.setFont(font)



        self._up_btn = QPushButton("+", self)

        self._up_btn.setObjectName("MonitorLcdStepUp")

        self._up_btn.setFixedWidth(18)

        self._up_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        self._up_btn.clicked.connect(self._on_step_up)

        self._up_btn.hide()



        row.addWidget(self._down_btn)

        row.addWidget(self._value, stretch=1)

        row.addWidget(self._up_btn)



        layout.addWidget(self._label)

        layout.addLayout(row)



    def set_label(self, text: str) -> None:

        self._label.setText(text.upper())



    def set_value(self, text: str) -> None:

        self._value.setText(text)



    def set_numeric(

        self,

        value: float,

        *,

        text: str,

        step: float = 1.0,

        show_step_buttons: bool = True,

    ) -> None:

        self._numeric_value = value

        self._wheel_step = step

        self._wheel_enabled = True

        self._choice_items = []

        self._down_btn.setVisible(show_step_buttons)

        self._up_btn.setVisible(show_step_buttons)

        self.set_value(text)



    def set_choice(

        self,

        items: List[Tuple[str, str]],

        current_id: str,

        *,

        label_for_id: Callable[[str], str],

        show_step_buttons: bool = True,

    ) -> None:

        self._wheel_enabled = False

        self._choice_items = list(items)

        self._current_choice_id = current_id

        show = show_step_buttons and len(items) > 1

        self._down_btn.setVisible(show)

        self._up_btn.setVisible(show)

        self.set_value(label_for_id(current_id))



    def bump_numeric(self, direction: int) -> None:

        if not self._wheel_enabled:

            return

        self._numeric_value += direction * self._wheel_step

        self.numeric_changed.emit(self._numeric_value)



    def bump_choice(self, direction: int) -> None:

        if not self._choice_items:

            return

        ids = [item_id for item_id, _ in self._choice_items]

        try:

            idx = ids.index(self._current_choice_id)

        except ValueError:

            idx = 0

        idx = max(0, min(len(ids) - 1, idx + direction))

        self._pick_choice(ids[idx])



    def mousePressEvent(self, event) -> None:

        if event.button() == Qt.MouseButton.LeftButton:

            pos = event.position()

            h = max(1, self.height())

            if pos.y() < h * 0.35:

                self._on_step_up()

            elif pos.y() > h * 0.65:

                self._on_step_down()

            else:

                self._show_adjustment_menu(event.globalPosition().toPoint())

        super().mousePressEvent(event)



    def wheelEvent(self, event: QWheelEvent) -> None:

        delta = event.angleDelta().y()

        if delta == 0:

            return

        direction = 1 if delta > 0 else -1

        if self._wheel_enabled:

            self.bump_numeric(direction)

        elif self._choice_items:

            self.bump_choice(direction)

        event.accept()



    def _on_step_up(self) -> None:

        if self._wheel_enabled:

            self.bump_numeric(1)

        elif self._choice_items:

            self.bump_choice(1)

        else:

            self.step_up_requested.emit()



    def _on_step_down(self) -> None:

        if self._wheel_enabled:

            self.bump_numeric(-1)

        elif self._choice_items:

            self.bump_choice(-1)

        else:

            self.step_down_requested.emit()



    def _show_adjustment_menu(self, global_pos) -> None:

        menu = QMenu(self)

        if self._choice_items:

            for item_id, item_label in self._choice_items:

                action = menu.addAction(item_label)

                action.triggered.connect(lambda _checked=False, i=item_id: self._pick_choice(i))

        elif self._wheel_enabled:

            action_up = menu.addAction("+")

            action_up.triggered.connect(lambda: self.bump_numeric(1))

            action_down = menu.addAction("−")

            action_down.triggered.connect(lambda: self.bump_numeric(-1))

        else:

            return

        menu.exec(global_pos)



    def _pick_choice(self, item_id: str) -> None:

        self._current_choice_id = item_id

        self.value_changed.emit(item_id)


