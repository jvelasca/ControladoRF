"""
about_dialog.py
---------------
Ventana modal «Acerca de…» — diseño compacto con icono centrado.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QVBoxLayout

from gui.app_branding import get_about_hero_pixmap, get_app_version
from gui.dialog_styles import add_dialog_separator, apply_professional_dialog_style
from gui.message_box_utils import localize_dialog_button_box
from i18n.json_translation import tr


class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(400)
        self.setMaximumWidth(480)
        self.setModal(True)
        self._hero_icon: QLabel | None = None
        self._title_label: QLabel | None = None
        self._tagline_label: QLabel | None = None
        self._version_label: QLabel | None = None
        self._modules_label: QLabel | None = None
        self._footer_label: QLabel | None = None
        self._init_ui()
        self.recargar_textos()

    def _init_ui(self) -> None:
        apply_professional_dialog_style(self)
        self.setStyleSheet(
            (self.styleSheet() or "")
            + """
            QLabel#AboutHeroIcon {
                margin-top: 4px;
                margin-bottom: 8px;
            }
            QLabel#AboutTitle {
                font-size: 18px;
                font-weight: 600;
            }
            QLabel#AboutTagline {
                font-size: 12px;
            }
            QLabel#AboutMeta {
                font-size: 12px;
            }
            """
        )

        self._hero_icon = QLabel()
        self._hero_icon.setObjectName("AboutHeroIcon")
        self._hero_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._hero_icon.setPixmap(get_about_hero_pixmap())

        self._title_label = QLabel()
        self._title_label.setObjectName("AboutTitle")
        self._title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._tagline_label = QLabel()
        self._tagline_label.setObjectName("AboutTagline")
        self._tagline_label.setWordWrap(True)
        self._tagline_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._version_label = QLabel()
        self._version_label.setObjectName("AboutMeta")
        self._version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._modules_label = QLabel()
        self._modules_label.setWordWrap(True)
        self._modules_label.setObjectName("AboutMeta")
        self._modules_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._footer_label = QLabel()
        self._footer_label.setObjectName("AboutMeta")
        self._footer_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        self._buttons.rejected.connect(self.accept)
        close_btn = self._buttons.button(QDialogButtonBox.StandardButton.Close)
        if close_btn:
            close_btn.clicked.connect(self.accept)
        localize_dialog_button_box(self._buttons)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 16)
        layout.setSpacing(8)
        layout.addWidget(self._hero_icon)
        layout.addWidget(self._title_label)
        layout.addWidget(self._tagline_label)
        layout.addSpacing(4)
        layout.addWidget(self._version_label)
        layout.addWidget(self._modules_label)
        add_dialog_separator(layout)
        layout.addWidget(self._footer_label)
        layout.addSpacing(4)
        layout.addWidget(self._buttons, alignment=Qt.AlignmentFlag.AlignCenter)

    def recargar_textos(self) -> None:
        self.setWindowTitle(tr("about"))
        version = get_app_version(tr("version_unknown"))
        if self._hero_icon is not None:
            self._hero_icon.setPixmap(get_about_hero_pixmap())
        if self._title_label is not None:
            self._title_label.setText(tr("app_title"))
        if self._tagline_label is not None:
            self._tagline_label.setText(tr("about_tagline"))
        if self._version_label is not None:
            self._version_label.setText(tr("about_version_line").format(version=version))
        if self._modules_label is not None:
            self._modules_label.setText(tr("about_modules_line"))
        if self._footer_label is not None:
            self._footer_label.setText(tr("about_footer"))
        localize_dialog_button_box(self._buttons)
