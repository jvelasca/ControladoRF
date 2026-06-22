"""Diálogo Herramientas → Gestión de canalizaciones RF."""
from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QRadioButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.rf.channelization_service import ChannelizationService
from core.rf.channelization_state import ChannelizationState
from gui.dialog_styles import apply_professional_dialog_style
from i18n.json_translation import tr


def _mhz(freq_hz: float) -> str:
    return f"{freq_hz / 1e6:.4f}"


def _configure_resizable_table(table: QTableWidget, default_widths: list[int]) -> None:
    header = table.horizontalHeader()
    header.setStretchLastSection(False)
    header.setSectionsMovable(False)
    header.setMinimumSectionSize(36)
    header.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
    for col in range(table.columnCount()):
        header.setSectionResizeMode(col, QHeaderView.ResizeMode.Interactive)
    table.setWordWrap(False)
    table.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
    for col, width in enumerate(default_widths):
        if col < table.columnCount():
            table.setColumnWidth(col, width)


class ChannelizationDialog(QDialog):
    """Catálogo mundial y preferencias del modo canal (toda la APP)."""

    def __init__(
        self,
        service: ChannelizationService,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._service = service
        self._state = service.get_state()
        self._loading = False
        self.setMinimumSize(720, 560)
        self._setup_ui()
        self._load_values()
        self.recargar_textos()
        apply_professional_dialog_style(self)

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        self._intro = QLabel()
        self._intro.setWordWrap(True)
        layout.addWidget(self._intro)

        prefs_group = QGroupBox()
        self._prefs_group = prefs_group
        prefs_layout = QVBoxLayout(prefs_group)

        region_row = QHBoxLayout()
        self._region_label = QLabel()
        region_row.addWidget(self._region_label)
        self._region_combo = QComboBox()
        self._region_combo.currentIndexChanged.connect(self._on_region_changed)
        region_row.addWidget(self._region_combo, stretch=1)
        prefs_layout.addLayout(region_row)

        mode_row = QHBoxLayout()
        self._mode_freq = QRadioButton()
        self._mode_channel = QRadioButton()
        mode_row.addWidget(self._mode_freq)
        mode_row.addWidget(self._mode_channel)
        mode_row.addStretch(1)
        prefs_layout.addLayout(mode_row)

        self._show_allocations = QCheckBox()
        self._show_restrictions = QCheckBox()
        prefs_layout.addWidget(self._show_allocations)
        prefs_layout.addWidget(self._show_restrictions)
        layout.addWidget(prefs_group)

        standards_group = QGroupBox()
        self._standards_group = standards_group
        standards_layout = QVBoxLayout(standards_group)
        self._standards_table = QTableWidget(0, 3)
        self._standards_table.setHorizontalHeaderLabels(["", "", ""])
        _configure_resizable_table(self._standards_table, [44, 120, 280])
        self._standards_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self._standards_table.itemSelectionChanged.connect(self._on_standard_selected)
        standards_layout.addWidget(self._standards_table)
        layout.addWidget(standards_group)

        channels_group = QGroupBox()
        self._channels_group = channels_group
        channels_layout = QVBoxLayout(channels_group)
        filter_row = QHBoxLayout()
        self._channel_filter_label = QLabel()
        filter_row.addWidget(self._channel_filter_label)
        self._standard_filter = QComboBox()
        self._standard_filter.currentIndexChanged.connect(self._reload_channels)
        filter_row.addWidget(self._standard_filter, stretch=1)
        channels_layout.addLayout(filter_row)

        self._channels_table = QTableWidget(0, 4)
        self._channels_table.setHorizontalHeaderLabels(["", "", "", ""])
        _configure_resizable_table(self._channels_table, [56, 160, 110, 90])
        self._channels_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        channels_layout.addWidget(self._channels_table)
        layout.addWidget(channels_group)

        self._buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        self._buttons.accepted.connect(self._on_save)
        self._buttons.rejected.connect(self.reject)
        layout.addWidget(self._buttons)

    def _load_values(self) -> None:
        self._loading = True
        try:
            self._region_combo.clear()
            for code in self._service.list_region_codes():
                self._region_combo.addItem(code, code)
            idx = self._region_combo.findData(self._state.active_region)
            self._region_combo.setCurrentIndex(idx if idx >= 0 else 0)

            self._mode_freq.setChecked(self._state.input_mode != "channel")
            self._mode_channel.setChecked(self._state.input_mode == "channel")
            self._show_allocations.setChecked(self._state.show_spectrum_allocations)
            self._show_restrictions.setChecked(self._state.show_restrictions)

            self._reload_standards()
            self._reload_standard_filter()
            self._reload_channels()
        finally:
            self._loading = False

    def _reload_standards(self) -> None:
        region = str(self._region_combo.currentData() or "ES")
        standards = self._service.list_standards(region)
        if not standards:
            standards = self._service.list_standards(None)

        self._standards_table.setRowCount(len(standards))
        active = set(self._state.active_standard_ids)
        for row, std in enumerate(standards):
            check_item = QTableWidgetItem()
            check_item.setFlags(
                Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled
            )
            check_item.setCheckState(
                Qt.CheckState.Checked
                if std.id in active
                else Qt.CheckState.Unchecked
            )
            self._standards_table.setItem(row, 0, check_item)

            id_item = QTableWidgetItem(std.id)
            id_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            self._standards_table.setItem(row, 1, id_item)

            name_item = QTableWidgetItem(std.name)
            name_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            name_item.setData(Qt.ItemDataRole.UserRole, std.id)
            self._standards_table.setItem(row, 2, name_item)

        if standards:
            self._standards_table.selectRow(0)

    def _reload_standard_filter(self) -> None:
        self._standard_filter.blockSignals(True)
        self._standard_filter.clear()
        for row in range(self._standards_table.rowCount()):
            name_item = self._standards_table.item(row, 2)
            if name_item is None:
                continue
            std_id = str(name_item.data(Qt.ItemDataRole.UserRole) or "")
            self._standard_filter.addItem(name_item.text(), std_id)
        self._standard_filter.blockSignals(False)

    def _on_region_changed(self) -> None:
        if self._loading:
            return
        region = str(self._region_combo.currentData() or "ES")
        defaults = self._service.default_standards_for_region(region)
        if defaults:
            self._state.active_standard_ids = defaults
        self._reload_standards()
        self._reload_standard_filter()
        self._reload_channels()

    def _on_standard_selected(self) -> None:
        if self._loading:
            return
        row = self._standards_table.currentRow()
        if row < 0:
            return
        name_item = self._standards_table.item(row, 2)
        if name_item is None:
            return
        std_id = str(name_item.data(Qt.ItemDataRole.UserRole) or "")
        idx = self._standard_filter.findData(std_id)
        if idx >= 0:
            self._standard_filter.setCurrentIndex(idx)

    def _reload_channels(self) -> None:
        std_id = str(self._standard_filter.currentData() or "")
        if not std_id:
            self._channels_table.setRowCount(0)
            return
        channels = self._service.list_channels(std_id)
        self._channels_table.setRowCount(len(channels))
        for row, ch in enumerate(channels):
            num = "" if ch.channel_number is None else str(ch.channel_number)
            values = (
                num,
                ch.channel_label,
                _mhz(ch.center_freq_hz),
                _mhz(ch.bandwidth_hz),
            )
            for col, text in enumerate(values):
                item = QTableWidgetItem(text)
                item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                self._channels_table.setItem(row, col, item)

    def _collect_state(self) -> ChannelizationState:
        active_ids: list[str] = []
        for row in range(self._standards_table.rowCount()):
            check = self._standards_table.item(row, 0)
            name_item = self._standards_table.item(row, 2)
            if check is None or name_item is None:
                continue
            if check.checkState() == Qt.CheckState.Checked:
                active_ids.append(str(name_item.data(Qt.ItemDataRole.UserRole) or ""))

        return ChannelizationState(
            input_mode="channel" if self._mode_channel.isChecked() else "frequency",
            active_region=str(self._region_combo.currentData() or "ES"),
            active_standard_ids=active_ids,
            show_spectrum_allocations=self._show_allocations.isChecked(),
            show_restrictions=self._show_restrictions.isChecked(),
        )

    def _on_save(self) -> None:
        state = self._collect_state()
        if not state.active_standard_ids:
            return
        self._service.save_state(state)
        self.accept()

    def recargar_textos(self) -> None:
        self.setWindowTitle(tr("channelization_dialog_title"))
        self._intro.setText(tr("channelization_dialog_intro"))
        self._prefs_group.setTitle(tr("channelization_prefs_group"))
        self._region_label.setText(tr("channelization_region"))
        self._mode_freq.setText(tr("channelization_mode_frequency"))
        self._mode_channel.setText(tr("channelization_mode_channel"))
        self._show_allocations.setText(tr("channelization_show_allocations"))
        self._show_restrictions.setText(tr("channelization_show_restrictions"))

        self._standards_group.setTitle(tr("channelization_standards_group"))
        self._standards_table.setHorizontalHeaderLabels(
            [
                tr("channelization_col_active"),
                tr("channelization_col_id"),
                tr("channelization_col_name"),
            ]
        )

        self._channels_group.setTitle(tr("channelization_channels_group"))
        self._channel_filter_label.setText(tr("channelization_standard_filter"))
        self._channels_table.setHorizontalHeaderLabels(
            [
                tr("channelization_col_number"),
                tr("channelization_col_label"),
                tr("channelization_col_center_mhz"),
                tr("channelization_col_bw_mhz"),
            ]
        )
