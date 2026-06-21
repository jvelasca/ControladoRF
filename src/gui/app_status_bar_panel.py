"""Panel permanente derecho de la barra de estado — proyecto, supervisión y workspace.

Layout (izquierda → derecha): ruta del proyecto · | · bloque supervisión · | · workspace.
"""
from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSizePolicy, QWidget

from gui.supervision_status_bar_widget import SupervisionStatusBarWidget


def make_status_bar_separator(parent: Optional[QWidget] = None) -> QFrame:
    sep = QFrame(parent)
    sep.setObjectName("StatusBarSeparator")
    sep.setFrameShape(QFrame.Shape.VLine)
    sep.setFrameShadow(QFrame.Shadow.Plain)
    sep.setFixedWidth(1)
    sep.setMinimumHeight(14)
    sep.setMaximumHeight(18)
    return sep


class AppStatusBarPanel(QWidget):
    """Zona permanente: [proyecto] | [supervisión] | [workspace]."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("AppStatusBarPanel")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)

        self.project_label = QLabel()
        self.project_label.setObjectName("ProjectDocumentPathLabel")
        self.project_label.setAlignment(
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft
        )

        self.supervision = SupervisionStatusBarWidget(self)

        self.workspace_label = QLabel()
        self.workspace_label.setObjectName("StatusBarWorkspaceLabel")
        self.workspace_label.setAlignment(
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight
        )

        row.addWidget(self.project_label, 0, Qt.AlignmentFlag.AlignVCenter)
        row.addWidget(make_status_bar_separator(self), 0, Qt.AlignmentFlag.AlignVCenter)
        row.addWidget(self.supervision, 0, Qt.AlignmentFlag.AlignVCenter)
        row.addWidget(make_status_bar_separator(self), 0, Qt.AlignmentFlag.AlignVCenter)
        row.addWidget(self.workspace_label, 0, Qt.AlignmentFlag.AlignVCenter)
