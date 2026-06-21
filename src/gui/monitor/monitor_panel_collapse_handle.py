"""Pestaña de flecha en el borde de un splitter para colapsar un panel."""
from __future__ import annotations

from typing import Literal

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QSizePolicy, QStyle, QToolButton, QWidget

from i18n.json_translation import tr

_HANDLE_QSS = """
#MonitorPanelCollapseHandle {
    background-color: #1a2430;
    border: none;
    padding: 0;
    margin: 0;
}
#MonitorPanelCollapseHandle:hover {
    background-color: #2a3848;
}
#MonitorPanelCollapseHandle:pressed {
    background-color: #334458;
}
#MonitorPanelCollapseHandle[panelAxis="horizontal"] {
    border-left: 1px solid #3a5060;
    min-width: 14px;
    max-width: 14px;
}
#MonitorPanelCollapseHandle[panelAxis="vertical"] {
    border-top: 1px solid #3a5060;
    min-height: 14px;
    max-height: 14px;
}
"""


class MonitorPanelCollapseHandle(QToolButton):
    """Flecha en el borde del splitter (vertical u horizontal)."""

    collapse_requested = pyqtSignal(bool)

    THICKNESS = 14

    def __init__(
        self,
        *,
        axis: Literal["horizontal", "vertical"] = "horizontal",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._axis = axis
        self._collapsed = False
        self.setObjectName("MonitorPanelCollapseHandle")
        self.setProperty("panelAxis", "vertical" if axis == "vertical" else "horizontal")
        self.setAutoRaise(False)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setStyleSheet(_HANDLE_QSS)
        if axis == "vertical":
            self.setFixedHeight(self.THICKNESS)
            self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        else:
            self.setFixedWidth(self.THICKNESS)
            self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        self.style().polish(self)
        self.clicked.connect(self._on_clicked)
        self._refresh()

    def set_collapsed(self, collapsed: bool) -> None:
        collapsed = bool(collapsed)
        if self._collapsed == collapsed:
            return
        self._collapsed = collapsed
        self._refresh()

    def is_collapsed(self) -> bool:
        return self._collapsed

    def _on_clicked(self) -> None:
        self.collapse_requested.emit(not self._collapsed)

    def _refresh(self) -> None:
        style = self.style()
        if self._axis == "vertical":
            if self._collapsed:
                icon = style.standardIcon(QStyle.StandardPixmap.SP_ArrowUp)
                tip = tr("monitor_waterfall_panel_expand_tip")
            else:
                icon = style.standardIcon(QStyle.StandardPixmap.SP_ArrowDown)
                tip = tr("monitor_waterfall_panel_collapse_tip")
        elif self._collapsed:
            icon = style.standardIcon(QStyle.StandardPixmap.SP_ArrowLeft)
            tip = tr("monitor_cfg_panel_expand_tip")
        else:
            icon = style.standardIcon(QStyle.StandardPixmap.SP_ArrowRight)
            tip = tr("monitor_cfg_panel_collapse_tip")
        self.setIcon(icon)
        self.setToolTip(tip)


# Alias retrocompatible
MonitorSidePanelCollapseHandle = MonitorPanelCollapseHandle
