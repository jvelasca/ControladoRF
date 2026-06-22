"""Botón Ch — activa modo canal (saltos por canal + franja de asignaciones)."""
from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QToolButton, QWidget

from i18n.json_translation import tr


class MonitorChannelModeButton(QToolButton):
    """Conmutador ON/OFF del modo canal en la barra de frecuencia."""

    channel_mode_changed = pyqtSignal(bool)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("MonitorChannelModeBtn")
        self.setText("Ch")
        self.setCheckable(True)
        self.setAutoRaise(False)
        self.setFixedSize(22, 22)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.toggled.connect(self._on_toggled)
        self.set_channel_mode(False)

    def set_channel_mode(self, active: bool) -> None:
        blocked = self.blockSignals(True)
        try:
            self.setChecked(bool(active))
        finally:
            self.blockSignals(blocked)
        self.setProperty("channelActive", "1" if active else "0")
        self.setToolTip(
            tr("monitor_channel_mode_on_tip")
            if active
            else tr("monitor_channel_mode_off_tip")
        )
        self.style().unpolish(self)
        self.style().polish(self)

    def _on_toggled(self, checked: bool) -> None:
        self.set_channel_mode(checked)
        self.channel_mode_changed.emit(checked)
