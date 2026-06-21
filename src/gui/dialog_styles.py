"""
dialog_styles.py
----------------
Estilos coherentes para diálogos modales de la aplicación.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from gui.app_chrome_styles import apply_application_chrome
from gui.app_branding import apply_app_window_icon
from gui.icon_utils import ICON_SIZE_DIALOG, get_app_icon
from utils.theme_utils import is_dark_mode


def apply_professional_dialog_style(widget) -> None:
    """Refresca estilos globales y marca el diálogo con cromo de la app."""
    apply_application_chrome()
    widget.setObjectName("AppDialog")
    apply_app_window_icon(widget)
    muted = "#858585" if is_dark_mode() else "#6A6A6A"
    primary = "#F1F1F1" if is_dark_mode() else "#1E1E1E"
    widget.setStyleSheet(
        f"""
        QLabel#DialogHeaderTitle {{
            color: {primary};
            font-size: 15px;
            font-weight: 600;
        }}
        QLabel#DialogHeaderSubtitle {{
            color: {muted};
            font-size: 12px;
        }}
        """
    )


def build_dialog_header(
    title: str,
    subtitle: str = "",
    *,
    icon_name: str = "about",
) -> QWidget:
    """Cabecera estándar con icono, título y subtítulo."""
    header = QWidget()
    header.setObjectName("DialogHeader")

    icon_label = QLabel()
    icon_label.setPixmap(get_app_icon(icon_name, ICON_SIZE_DIALOG).pixmap(ICON_SIZE_DIALOG, ICON_SIZE_DIALOG))
    icon_label.setFixedSize(ICON_SIZE_DIALOG + 4, ICON_SIZE_DIALOG + 4)
    icon_label.setAlignment(Qt.AlignmentFlag.AlignTop)

    title_label = QLabel(title)
    title_label.setObjectName("DialogHeaderTitle")
    title_label.setWordWrap(True)

    text_column = QVBoxLayout()
    text_column.setContentsMargins(0, 0, 0, 0)
    text_column.setSpacing(4)
    text_column.addWidget(title_label)

    subtitle_label = None
    if subtitle:
        subtitle_label = QLabel(subtitle)
        subtitle_label.setObjectName("DialogHeaderSubtitle")
        subtitle_label.setWordWrap(True)
        text_column.addWidget(subtitle_label)

    row = QHBoxLayout(header)
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(12)
    row.addWidget(icon_label, alignment=Qt.AlignmentFlag.AlignTop)
    row.addLayout(text_column, stretch=1)

    header._title_label = title_label  # type: ignore[attr-defined]
    header._subtitle_label = subtitle_label  # type: ignore[attr-defined]
    return header


def add_dialog_separator(parent_layout) -> None:
    line = QFrame()
    line.setFrameShape(QFrame.Shape.HLine)
    line.setFrameShadow(QFrame.Shadow.Plain)
    line.setObjectName("DialogSeparator")
    parent_layout.addWidget(line)
