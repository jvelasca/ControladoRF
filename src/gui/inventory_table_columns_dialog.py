"""Diálogo de columnas visibles de la tabla de inventario RF."""

from __future__ import annotations



from typing import Callable, Optional, Sequence



from PyQt6.QtCore import Qt

from PyQt6.QtWidgets import (

    QCheckBox,

    QDialog,

    QDialogButtonBox,

    QGroupBox,

    QHBoxLayout,

    QLabel,

    QPushButton,

    QScrollArea,

    QVBoxLayout,

    QWidget,

)



from gui.configurable_table_header import (

    reset_table_columns,

    set_column_visible,

)

from gui.inventory_table_alignment import DEFAULT_TABLE_ALIGNMENT

from gui.message_box_utils import localize_dialog_button_box

from gui.icon_utils import ICON_SIZE_DIALOG, get_app_icon

from gui.text_alignment_toolbar import TextAlignmentToolbar

from i18n.json_translation import tr





class InventoryTableColumnsDialog(QDialog):

    """Ventana emergente con checks para mostrar u ocultar columnas."""



    def __init__(

        self,

        parent: Optional[QWidget],

        header,

        column_keys: Sequence[str],

        *,

        on_changed: Optional[Callable[[], None]] = None,

        on_fit_contents: Optional[Callable[[], None]] = None,

        get_column_label: Callable[[str], str],

        get_text_alignment: Callable[[], str],

        set_text_alignment: Callable[[str], None],

        reset_text_alignment: Callable[[], None],

    ) -> None:

        super().__init__(parent)

        self._header = header

        self._column_keys = list(column_keys)

        self._on_changed = on_changed

        self._on_fit_contents = on_fit_contents

        self._get_column_label = get_column_label

        self._get_text_alignment = get_text_alignment

        self._set_text_alignment = set_text_alignment

        self._reset_text_alignment = reset_text_alignment

        self._checkboxes: list[tuple[int, QCheckBox]] = []

        self._loading = False



        self.setWindowTitle(tr("inventory_table_columns_title"))

        self.setWindowModality(Qt.WindowModality.WindowModal)

        self.setMinimumWidth(300)



        scroll_content = QWidget()

        form = QVBoxLayout(scroll_content)

        form.setContentsMargins(0, 0, 0, 0)

        form.setSpacing(4)



        for index, key in enumerate(self._column_keys):

            checkbox = QCheckBox(get_column_label(key))

            checkbox.setChecked(not header.isSectionHidden(index))

            checkbox.toggled.connect(

                lambda checked, col=index: self._on_column_toggled(col, checked)

            )

            form.addWidget(checkbox)

            self._checkboxes.append((index, checkbox))



        scroll = QScrollArea()

        scroll.setWidgetResizable(True)

        scroll.setFrameShape(QScrollArea.Shape.NoFrame)

        scroll.setWidget(scroll_content)



        self._layout_group = QGroupBox()

        layout_inner = QVBoxLayout(self._layout_group)

        layout_inner.setContentsMargins(8, 8, 8, 8)

        layout_inner.setSpacing(6)



        self._align_label = QLabel()

        self._align_label.setObjectName("TableAlignLabel")

        self._align_toolbar = TextAlignmentToolbar(on_changed=self._on_alignment_changed)



        align_row = QHBoxLayout()

        align_row.setContentsMargins(0, 0, 0, 0)

        align_row.addWidget(self._align_label)

        align_row.addStretch(1)

        align_row.addWidget(self._align_toolbar)

        layout_inner.addLayout(align_row)



        self._fit_btn = QPushButton()

        self._fit_btn.clicked.connect(self._fit_column_widths)



        self._reset_btn = QPushButton()

        self._reset_btn.setIcon(get_app_icon("reset_panels", ICON_SIZE_DIALOG))

        self._reset_btn.clicked.connect(self._reset_columns)



        self._buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)

        self._buttons.rejected.connect(self.reject)

        self._buttons.addButton(self._fit_btn, QDialogButtonBox.ButtonRole.ActionRole)

        self._buttons.addButton(self._reset_btn, QDialogButtonBox.ButtonRole.ResetRole)

        localize_dialog_button_box(self._buttons)



        layout = QVBoxLayout(self)

        layout.setContentsMargins(12, 12, 12, 12)

        layout.setSpacing(8)

        layout.addWidget(self._layout_group)

        layout.addWidget(scroll)

        layout.addWidget(self._buttons)



        self.recargar_textos()



    def recargar_textos(self) -> None:

        self.setWindowTitle(tr("inventory_table_columns_title"))

        self._layout_group.setTitle(tr("inventory_table_layout_group"))

        self._align_label.setText(tr("inventory_table_align_label"))

        self._fit_btn.setText(tr("table_columns_fit_contents"))

        self._reset_btn.setText(tr("table_columns_reset"))

        localize_dialog_button_box(self._buttons)

        self._loading = True

        self._align_toolbar.recargar_textos()

        self._align_toolbar.set_alignment(self._get_text_alignment(), notify=False)

        self._align_toolbar.apply_visual_theme()

        for index, checkbox in self._checkboxes:

            key = self._column_keys[index]

            checkbox.setText(self._get_column_label(key))

            checkbox.setChecked(not self._header.isSectionHidden(index))

        self._loading = False



    def _on_column_toggled(self, column: int, visible: bool) -> None:

        if self._loading:

            return

        if not set_column_visible(self._header, column, visible, self._on_changed):

            self._loading = True

            self._checkboxes[column][1].setChecked(not visible)

            self._loading = False



    def _on_alignment_changed(self, mode: str) -> None:

        if self._loading:

            return

        self._set_text_alignment(mode)



    def _fit_column_widths(self) -> None:

        if self._on_fit_contents:

            self._on_fit_contents()



    def _reset_columns(self) -> None:

        reset_table_columns(self._header, self._column_keys, self._on_changed)

        self._reset_text_alignment()

        self._loading = True

        self._align_toolbar.set_alignment(DEFAULT_TABLE_ALIGNMENT, notify=False)

        for index, checkbox in self._checkboxes:

            checkbox.setChecked(not self._header.isSectionHidden(index))

        self._loading = False


