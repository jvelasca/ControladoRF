"""
config_dialog.py
----------------
Diálogo de configuración: idioma (por workspace) y base de datos (global).
La apariencia sigue automáticamente el modo claro/oscuro del sistema operativo.
"""
from typing import Optional

from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from core.developer_mode import read_developer_mode
from gui.config_db_tab import DatabaseConfigTab
from gui.developer_lock_button import DeveloperLockButton
from gui.dialog_styles import apply_professional_dialog_style
from gui.icon_utils import ICON_SIZE_DIALOG, get_app_icon
from i18n.json_translation import tr
from i18n.translation_utils import apply_language
from utils.theme_utils import is_dark_mode
from workspace.controller import WorkspaceController

AVAILABLE_LANGUAGES = {
    "es": "Español",
    "en": "English",
}


class ConfigDialog(QDialog):
    """Preferencias: idioma del workspace activo y parámetros globales de SQLite."""

    def __init__(
        self,
        controller: WorkspaceController,
        database_service: Optional[DatabaseService] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.setMinimumSize(560, 560)
        self.controller = controller
        self._database_service = database_service
        self._loading = False
        self._store = controller.store
        self._developer_mode = read_developer_mode(self._store.get_config)
        self._setup_ui()
        self._load_values()
        self.recargar_textos()
        apply_professional_dialog_style(self)

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        self._tabs = QTabWidget()
        self._general_tab = QWidget()
        general_layout = QVBoxLayout(self._general_tab)

        self._intro_label = QLabel()
        self._intro_label.setWordWrap(True)
        general_layout.addWidget(self._intro_label)

        self._language_group = QGroupBox()
        language_layout = QVBoxLayout(self._language_group)

        language_header = QHBoxLayout()
        self._language_icon = QLabel()
        self._language_icon.setPixmap(
            get_app_icon("language", ICON_SIZE_DIALOG).pixmap(ICON_SIZE_DIALOG, ICON_SIZE_DIALOG)
        )
        language_header.addWidget(self._language_icon)
        self._label_idioma = QLabel()
        language_header.addWidget(self._label_idioma, stretch=1)
        language_layout.addLayout(language_header)

        self.combo_idioma = QComboBox()
        for code in AVAILABLE_LANGUAGES:
            self.combo_idioma.addItem("", code)
        self.combo_idioma.currentIndexChanged.connect(self._on_language_changed)
        language_layout.addWidget(self.combo_idioma)

        self._language_hint = QLabel()
        self._language_hint.setWordWrap(True)
        language_layout.addWidget(self._language_hint)

        self._appearance_note = QLabel()
        self._appearance_note.setWordWrap(True)
        language_layout.addWidget(self._appearance_note)
        general_layout.addWidget(self._language_group)

        self._developer_group = QGroupBox()
        developer_layout = QVBoxLayout(self._developer_group)
        dev_row = QHBoxLayout()
        self._developer_lock = DeveloperLockButton(
            get_config=self._store.get_config,
            set_config=self._store.set_config,
            parent=self,
        )
        self._developer_lock.unlocked_changed.connect(self._on_developer_lock_changed)
        self._developer_label = QLabel()
        dev_row.addWidget(self._developer_label)
        dev_row.addStretch(1)
        dev_row.addWidget(self._developer_lock, alignment=Qt.AlignmentFlag.AlignVCenter)
        self._developer_hint = QLabel()
        self._developer_hint.setWordWrap(True)
        developer_layout.addLayout(dev_row)
        developer_layout.addWidget(self._developer_hint)
        general_layout.addWidget(self._developer_group)

        general_layout.addStretch()

        self._db_tab = DatabaseConfigTab(
            self._database_service,
            developer_mode=self._developer_mode,
            get_config=self._store.get_config,
            set_config=self._store.set_config,
            parent=self,
        )
        self._tabs.addTab(self._general_tab, "")
        self._tabs.addTab(self._db_tab, "")
        layout.addWidget(self._tabs)

        self._status_label = QLabel()
        layout.addWidget(self._status_label)

        self._button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        self._button_box.rejected.connect(self.reject)
        layout.addWidget(self._button_box)

    def _load_values(self) -> None:
        self._loading = True
        self.combo_idioma.blockSignals(True)
        lang = self.controller.get_language()
        idx_lang = self.combo_idioma.findData(lang)
        if idx_lang >= 0:
            self.combo_idioma.setCurrentIndex(idx_lang)
        self.combo_idioma.blockSignals(False)

        self._developer_lock.sync_from_config()
        self._developer_mode = self._developer_lock.is_unlocked()
        self._loading = False

    def _on_developer_lock_changed(self, unlocked: bool) -> None:
        if self._loading:
            return
        self._developer_mode = bool(unlocked)
        self._db_tab.set_developer_mode(self._developer_mode)
        self.recargar_textos()

    def _on_language_changed(self) -> None:
        if self._loading:
            return
        code: str = self.combo_idioma.currentData()
        if not code:
            return
        self.controller.set_language(code)
        apply_language(code)
        parent = self.parent()
        if parent is not None and hasattr(parent, "recargar_textos"):
            parent.recargar_textos()
        self.recargar_textos()

    def recargar_textos(self) -> None:
        self.setWindowTitle(tr("config_title"))
        self._tabs.setTabText(0, tr("config_tab_general"))
        self._tabs.setTabText(1, tr("config_tab_database"))
        self._intro_label.setText(tr("config_workspace_hint"))
        self._language_group.setTitle(tr("config_section_language"))
        self._language_hint.setText(tr("config_language_hint"))
        self._appearance_note.setText(tr("config_appearance_system_note"))
        self._developer_group.setTitle(tr("config_dev_group"))
        self._developer_label.setText(tr("config_dev_mode"))
        self._developer_lock.recargar_textos()
        self._developer_hint.setText(
            tr("config_dev_mode_active_hint")
            if self._developer_mode
            else tr("config_dev_mode_hint")
        )

        lang: str = self.controller.get_language()
        lang_label = tr(AVAILABLE_LANGUAGES.get(lang, lang))
        self._label_idioma.setText(tr("language_active", lang=lang_label))

        for i in range(self.combo_idioma.count()):
            code: str = self.combo_idioma.itemData(i)
            self.combo_idioma.setItemText(i, tr(AVAILABLE_LANGUAGES.get(code, code)))

        close_btn = self._button_box.button(QDialogButtonBox.StandardButton.Close)
        if close_btn:
            close_btn.setText(tr("close"))

        ws = self.controller.active_workspace
        ws_name = ws.name if ws else "---"
        mode_label = tr("appearance_dark") if is_dark_mode() else tr("appearance_light")
        dev_label = tr("config_dev_mode_on") if self._developer_mode else tr("config_dev_mode_off")
        self._status_label.setText(
            tr(
                "config_status_summary_dev",
                workspace=ws_name,
                lang=lang_label,
                mode=mode_label,
                dev=dev_label,
            )
        )
        self._db_tab.recargar_textos()
        self._apply_hint_style()

    def _apply_hint_style(self) -> None:
        hint_color = "#858585" if is_dark_mode() else "#6A6A6A"
        hint_style = f"color: {hint_color}; font-size: 11px;"
        self._language_hint.setStyleSheet(hint_style)
        self._appearance_note.setStyleSheet(hint_style)
        self._developer_hint.setStyleSheet(hint_style)
        self._intro_label.setStyleSheet(hint_style.replace("11px", "12px"))
