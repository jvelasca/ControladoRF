"""Tabla M1–M10: modos, colores, delta y visualización en espectro/waterfall."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QColorDialog,
    QMessageBox,
)

from core.monitor.marker_bank import (
    DEFAULT_MARKER_COLORS,
    MARKER_COUNT,
    MARKER_MODES,
    MarkerDefinition,
    default_delta_ref_marker_id,
    find_peak_near,
    marker_bank_params_equal,
    normalize_marker_mode,
    prepare_marker_for_delta_mode,
    resolve_marker_delta,
    resolve_marker_frequency_hz,
    resolve_marker_level_db,
)
from core.monitor.monitor_format import format_freq_short, parse_locale_float
from core.monitor.spectrum_params import SpectrumParams
from gui.monitor.monitor_info_button import MonitorInfoButton
from gui.configurable_table_header import (
    restore_header_state,
    save_header_state,
    setup_resizable_header,
)
from i18n.json_translation import tr


@dataclass
class _RowWidgets:
    enabled: QCheckBox
    mode: QComboBox
    ref: QComboBox
    freq: QTableWidgetItem
    color_btn: QPushButton
    show_line: QCheckBox
    show_freq: QCheckBox
    show_level: QCheckBox
    show_snr: QCheckBox
    delta_f: QTableWidgetItem
    delta_level: QTableWidgetItem
    peak_btn: QPushButton


class MonitorMarkersPanel(QWidget):
    params_changed = pyqtSignal(object)
    active_marker_changed = pyqtSignal(int)

    _COL_ID = 0
    _COL_ON = 1
    _COL_MODE = 2
    _COL_REF = 3
    _COL_FREQ = 4
    _COL_COLOR = 5
    _COL_LINE = 6
    _COL_FREQ_SHOW = 7
    _COL_LEVEL_SHOW = 8
    _COL_SNR_SHOW = 9
    _COL_DELTA_F = 10
    _COL_DELTA_LVL = 11
    _COL_PEAK = 12

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._params = SpectrumParams()
        self._syncing = False
        self._trace_freqs: np.ndarray | None = None
        self._trace_power: np.ndarray | None = None
        self._rows: list[_RowWidgets] = []
        self._on_table_layout_changed = None
        self._pending_table_header = ""
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        header = QHBoxLayout()
        title = QLabel(tr("monitor_cfg_markers"))
        font = title.font()
        font.setBold(True)
        title.setFont(font)
        self._info = MonitorInfoButton(
            title_key="monitor_cfg_markers",
            body_key="monitor_cfg_markers_intro",
        )
        header.addWidget(title)
        header.addWidget(self._info, alignment=Qt.AlignmentFlag.AlignVCenter)
        header.addStretch(1)
        layout.addLayout(header)

        self._auto_pan = QCheckBox(tr("monitor_marker_auto_pan"))
        self._auto_pan.toggled.connect(self._on_auto_pan_toggled)
        layout.addWidget(self._auto_pan)

        self._table = QTableWidget(MARKER_COUNT, 13, self)
        self._table.setHorizontalHeaderLabels(
            [
                tr("monitor_markers_col_id"),
                tr("monitor_markers_col_on"),
                tr("monitor_markers_col_mode"),
                tr("monitor_markers_col_ref"),
                tr("monitor_markers_col_frequency"),
                tr("monitor_markers_col_color"),
                tr("monitor_markers_col_line"),
                tr("monitor_markers_col_freq"),
                tr("monitor_markers_col_level"),
                tr("monitor_markers_col_snr"),
                tr("monitor_markers_col_delta_f"),
                tr("monitor_markers_col_delta_level"),
                tr("monitor_markers_col_peak"),
            ]
        )
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked
            | QAbstractItemView.EditTrigger.EditKeyPressed
            | QAbstractItemView.EditTrigger.AnyKeyPressed
        )
        self._table.verticalHeader().setVisible(False)
        header = self._table.horizontalHeader()
        setup_resizable_header(
            header,
            13,
            on_changed=self._notify_table_layout_changed,
        )
        self._apply_header_tooltips()

        self._syncing = True
        try:
            for row in range(MARKER_COUNT):
                self._build_row(row)
        finally:
            self._syncing = False

        self._table.itemChanged.connect(self._on_item_changed)
        self._table.itemSelectionChanged.connect(self._on_selection_changed)

        layout.addWidget(self._table, stretch=1)

        actions = QHBoxLayout()
        self._all_off_btn = QPushButton(tr("monitor_markers_all_off"))
        self._all_off_btn.clicked.connect(self._all_off)
        actions.addWidget(self._all_off_btn)
        actions.addStretch(1)
        layout.addLayout(actions)

    def _apply_header_tooltips(self) -> None:
        tips = (
            None,
            tr("monitor_markers_on_tip"),
            None,
            tr("monitor_markers_delta_ref_tip"),
            None,
            None,
            tr("monitor_markers_line_tip"),
            tr("monitor_markers_freq_show_tip"),
            tr("monitor_markers_level_show_tip"),
            tr("monitor_markers_snr_show_tip"),
            None,
            None,
            None,
        )
        for col, tip in enumerate(tips):
            if tip:
                item = self._table.horizontalHeaderItem(col)
                if item is not None:
                    item.setToolTip(tip)

    def _center_checkbox(self, checkbox: QCheckBox) -> QWidget:
        host = QWidget(self._table)
        row_layout = QHBoxLayout(host)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.addStretch(1)
        row_layout.addWidget(checkbox)
        row_layout.addStretch(1)
        return host

    def _build_row(self, row: int) -> None:
        marker_id = row + 1
        id_item = QTableWidgetItem(f"M{marker_id}")
        id_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
        id_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self._table.setItem(row, self._COL_ID, id_item)

        enabled = QCheckBox()
        enabled.setToolTip(tr("monitor_markers_on_tip"))
        enabled.toggled.connect(lambda checked, r=row: self._on_enabled_toggled(r, checked))
        self._table.setCellWidget(row, self._COL_ON, self._center_checkbox(enabled))

        mode = QComboBox()
        for key in MARKER_MODES:
            mode.addItem(tr(f"monitor_markers_mode_{key}"), key)
        mode.currentIndexChanged.connect(lambda _idx, r=row: self._on_mode_changed(r))
        self._table.setCellWidget(row, self._COL_MODE, mode)

        ref = QComboBox()
        ref.currentIndexChanged.connect(lambda _idx, r=row: self._on_ref_changed(r))
        self._table.setCellWidget(row, self._COL_REF, ref)

        freq = QTableWidgetItem("100.000000")
        freq.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._table.setItem(row, self._COL_FREQ, freq)

        color_btn = QPushButton()
        color_btn.setFixedSize(28, 18)
        color_btn.setProperty("markerColor", DEFAULT_MARKER_COLORS[row] if row < len(DEFAULT_MARKER_COLORS) else "#FFC850")
        color_btn.clicked.connect(lambda _checked=False, r=row: self._pick_color(r))
        self._table.setCellWidget(row, self._COL_COLOR, color_btn)

        show_line = QCheckBox()
        show_line.setChecked(True)
        show_line.setToolTip(tr("monitor_markers_line_tip"))
        show_line.toggled.connect(lambda _checked, r=row: self._emit_from_row(r))
        self._table.setCellWidget(row, self._COL_LINE, self._center_checkbox(show_line))

        show_freq = QCheckBox()
        show_freq.setChecked(True)
        show_freq.toggled.connect(lambda _checked, r=row: self._emit_from_row(r))
        self._table.setCellWidget(row, self._COL_FREQ_SHOW, self._center_checkbox(show_freq))

        show_level = QCheckBox()
        show_level.setChecked(True)
        show_level.toggled.connect(lambda _checked, r=row: self._emit_from_row(r))
        self._table.setCellWidget(row, self._COL_LEVEL_SHOW, self._center_checkbox(show_level))

        show_snr = QCheckBox()
        show_snr.toggled.connect(lambda _checked, r=row: self._emit_from_row(r))
        self._table.setCellWidget(row, self._COL_SNR_SHOW, self._center_checkbox(show_snr))

        delta_f = QTableWidgetItem("—")
        delta_f.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
        delta_f.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._table.setItem(row, self._COL_DELTA_F, delta_f)

        delta_level = QTableWidgetItem("—")
        delta_level.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
        delta_level.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._table.setItem(row, self._COL_DELTA_LVL, delta_level)

        peak_btn = QPushButton(tr("monitor_markers_peak_btn"))
        peak_btn.clicked.connect(lambda _checked=False, r=row: self._peak_here(r))
        self._table.setCellWidget(row, self._COL_PEAK, peak_btn)

        self._rows.append(
            _RowWidgets(
                enabled=enabled,
                mode=mode,
                ref=ref,
                freq=freq,
                color_btn=color_btn,
                show_line=show_line,
                show_freq=show_freq,
                show_level=show_level,
                show_snr=show_snr,
                delta_f=delta_f,
                delta_level=delta_level,
                peak_btn=peak_btn,
            )
        )
        self._refresh_ref_options(row)

    def _row_widgets(self, row: int) -> _RowWidgets:
        if row < 0 or row >= len(self._rows):
            raise IndexError(f"marker row {row} not ready ({len(self._rows)} rows built)")
        return self._rows[row]

    def _ui_ready(self) -> bool:
        return len(self._rows) >= MARKER_COUNT

    def _freq_cell_text(self, marker: MarkerDefinition) -> str:
        if normalize_marker_mode(marker.mode) == "delta":
            offset_mhz = float(marker.freq_hz) / 1_000_000.0
            return f"{offset_mhz:+.6f}"
        return self._mhz_text(marker.freq_hz)

    def _parse_freq_cell(self, text: str, mode: str) -> float:
        raw = text.strip().replace("−", "-")
        mhz = parse_locale_float(raw)
        if normalize_marker_mode(mode) == "delta":
            return float(mhz) * 1_000_000.0
        return max(0.0, float(mhz) * 1_000_000.0)

    def _choose_delta_ref(self, row: int) -> int | None:
        marker_id = row + 1
        widgets = self._row_widgets(row)
        current_ref = int(widgets.ref.currentData() or 0)
        if current_ref and current_ref != marker_id:
            ref = self._params.markers[current_ref - 1]
            if ref.enabled:
                return current_ref
        return default_delta_ref_marker_id(self._params, marker_id)

    def _apply_delta_ref(self, row: int, ref_id: int) -> None:
        prepare_marker_for_delta_mode(self._params, row + 1, ref_id)
        marker = self._params.markers[row]
        self._row_widgets(row).freq.setText(self._freq_cell_text(marker))
        self._row_widgets(row).enabled.setChecked(True)

    def _refresh_ref_options(self, row: int, *, selected_ref: int | None = None) -> None:
        widgets = self._row_widgets(row)
        marker_id = row + 1
        ref = widgets.ref
        ref.blockSignals(True)
        ref.clear()
        ref.addItem("—", 0)
        active_id = int(self._params.active_marker_id)
        for other in range(1, MARKER_COUNT + 1):
            if other == marker_id:
                continue
            other_marker = self._params.markers[other - 1]
            if not other_marker.enabled:
                continue
            label = f"M{other}"
            if other == active_id:
                label = tr("monitor_markers_ref_active_label", id=other)
            ref.addItem(label, other)
        target = selected_ref
        if target is None:
            target = default_delta_ref_marker_id(self._params, marker_id)
        if target is None:
            target = 0
        idx = ref.findData(target)
        ref.setCurrentIndex(max(0, idx))
        ref.blockSignals(False)
        is_delta = normalize_marker_mode(widgets.mode.currentData() or "normal") == "delta"
        ref.setEnabled(is_delta)
        if is_delta:
            ref.setToolTip(tr("monitor_markers_delta_ref_tip"))
        else:
            ref.setToolTip("")

    def _mhz_text(self, hz: float) -> str:
        return f"{float(hz) / 1_000_000.0:.6f}"

    def _parse_freq_mhz(self, text: str) -> float:
        mhz = parse_locale_float(text)
        return max(0.0, mhz * 1_000_000.0)

    def _apply_color_button(self, button: QPushButton, color: str) -> None:
        qcolor = QColor(str(color))
        if not qcolor.isValid():
            qcolor = QColor("#FFC850")
        button.setStyleSheet(
            f"background-color: {qcolor.name()}; border: 1px solid #556677; min-height: 16px;"
        )

    def _block_row_signals(self, blocked: bool) -> None:
        for row in range(min(len(self._rows), MARKER_COUNT)):
            widgets = self._rows[row]
            for widget in (
                widgets.enabled,
                widgets.mode,
                widgets.ref,
                widgets.show_line,
                widgets.show_freq,
                widgets.show_level,
                widgets.show_snr,
            ):
                widget.blockSignals(blocked)

    def set_params(self, params: SpectrumParams) -> None:
        self._syncing = True
        self._table.blockSignals(True)
        self._block_row_signals(True)
        try:
            self._params = params.copy()
            self._auto_pan.blockSignals(True)
            self._auto_pan.setChecked(bool(self._params.marker_auto_pan))
            self._auto_pan.blockSignals(False)
            if not self._ui_ready():
                return
            for row in range(MARKER_COUNT):
                marker = self._params.markers[row]
                widgets = self._row_widgets(row)
                widgets.enabled.setChecked(marker.enabled)
                mode_index = widgets.mode.findData(normalize_marker_mode(marker.mode))
                widgets.mode.setCurrentIndex(max(0, mode_index))
                self._refresh_ref_options(row, selected_ref=marker.ref_marker_id)
                widgets.freq.setText(self._freq_cell_text(marker))
                widgets.color_btn.setProperty("markerColor", marker.color)
                self._apply_color_button(widgets.color_btn, marker.color)
                widgets.show_line.setChecked(marker.show_line)
                widgets.show_freq.setChecked(marker.show_freq)
                widgets.show_level.setChecked(marker.show_level)
                widgets.show_snr.setChecked(marker.show_snr)
            active_row = max(0, min(MARKER_COUNT - 1, self._params.active_marker_id - 1))
            self._table.selectRow(active_row)
            self._refresh_measurements()
        finally:
            self._block_row_signals(False)
            self._table.blockSignals(False)
            self._syncing = False

    def set_trace_snapshot(
        self,
        freqs: np.ndarray | None,
        power: np.ndarray | None,
    ) -> None:
        self._trace_freqs = freqs
        self._trace_power = power
        self._refresh_measurements()

    def focus_active_marker(self) -> None:
        row = max(0, min(MARKER_COUNT - 1, self._params.active_marker_id - 1))
        self._table.selectRow(row)
        self._table.setFocus(Qt.FocusReason.OtherFocusReason)

    def _refresh_measurements(self) -> None:
        if not self._ui_ready():
            return
        params = self._params
        freqs = self._trace_freqs
        power = self._trace_power
        for row in range(MARKER_COUNT):
            marker_id = row + 1
            widgets = self._row_widgets(row)
            marker = params.markers[row]
            level = resolve_marker_level_db(params, marker_id, freqs=freqs, power=power)
            level_text = f"{level:.1f} dBm" if level is not None else "—"
            if marker.enabled and marker.show_level and level is not None:
                widgets.freq.setToolTip(level_text)
            else:
                widgets.freq.setToolTip("")
            delta_f, delta_level = resolve_marker_delta(params, marker_id, freqs=freqs, power=power)
            if normalize_marker_mode(marker.mode) == "delta" and marker.enabled:
                widgets.delta_f.setText(format_freq_short(delta_f) if delta_f is not None else "—")
                widgets.delta_level.setText(
                    f"{delta_level:+.1f} dB" if delta_level is not None else "—"
                )
            else:
                widgets.delta_f.setText("—")
                widgets.delta_level.setText("—")

    def _marker_from_row(self, row: int) -> MarkerDefinition:
        widgets = self._row_widgets(row)
        ref_id = int(widgets.ref.currentData() or 0)
        mode = str(widgets.mode.currentData() or "normal")
        return MarkerDefinition(
            enabled=widgets.enabled.isChecked(),
            mode=mode,
            freq_hz=self._parse_freq_cell(widgets.freq.text(), mode),
            ref_marker_id=max(1, min(MARKER_COUNT, ref_id if ref_id else 1)),
            color=widgets.color_btn.property("markerColor") or "#FFC850",
            show_line=widgets.show_line.isChecked(),
            show_freq=widgets.show_freq.isChecked(),
            show_level=widgets.show_level.isChecked(),
            show_snr=widgets.show_snr.isChecked(),
        )

    def _build_params(self) -> SpectrumParams:
        if not self._ui_ready():
            return self._params.copy()
        updated = self._params.copy()
        updated.markers = [self._marker_from_row(row) for row in range(MARKER_COUNT)]
        updated.marker_auto_pan = self._auto_pan.isChecked()
        selected = self._table.currentRow()
        if selected >= 0:
            updated.active_marker_id = selected + 1
        return updated

    def _emit_params(self) -> None:
        if self._syncing or not self._ui_ready():
            return
        updated = self._build_params()
        if marker_bank_params_equal(updated, self._params):
            self._params = updated
            self._refresh_measurements()
            return
        self._params = updated
        self._refresh_measurements()
        self.params_changed.emit(updated)

    def _emit_from_row(self, row: int) -> None:
        if self._syncing:
            return
        self._emit_params()

    def _on_item_changed(self, item: QTableWidgetItem) -> None:
        if self._syncing or item.column() != self._COL_FREQ:
            return
        self._emit_params()

    def _on_enabled_toggled(self, row: int, _checked: bool) -> None:
        self._emit_from_row(row)

    def _on_mode_changed(self, row: int) -> None:
        if self._syncing:
            return
        widgets = self._row_widgets(row)
        mode = normalize_marker_mode(str(widgets.mode.currentData() or "normal"))
        if mode == "delta":
            ref_id = self._choose_delta_ref(row)
            if ref_id is None:
                QMessageBox.warning(
                    self,
                    tr("monitor_markers_delta_ref_title"),
                    tr("monitor_markers_delta_ref_missing"),
                )
                widgets.mode.blockSignals(True)
                normal_idx = widgets.mode.findData("normal")
                widgets.mode.setCurrentIndex(max(0, normal_idx))
                widgets.mode.blockSignals(False)
                widgets.ref.setEnabled(False)
                return
            self._apply_delta_ref(row, ref_id)
            self._refresh_ref_options(row, selected_ref=ref_id)
            widgets.ref.showPopup()
        else:
            self._refresh_ref_options(row)
            widgets.ref.setEnabled(False)
        self._emit_params()

    def _on_ref_changed(self, row: int) -> None:
        if self._syncing:
            return
        widgets = self._row_widgets(row)
        mode = normalize_marker_mode(str(widgets.mode.currentData() or "normal"))
        if mode == "delta":
            ref_id = int(widgets.ref.currentData() or 0)
            if ref_id and ref_id != row + 1:
                prepare_marker_for_delta_mode(self._params, row + 1, ref_id)
                marker = self._params.markers[row]
                widgets.freq.setText(self._freq_cell_text(marker))
        self._emit_from_row(row)

    def _on_auto_pan_toggled(self, _checked: bool) -> None:
        self._emit_params()

    def _on_selection_changed(self) -> None:
        if self._syncing or not self._ui_ready():
            return
        row = self._table.currentRow()
        if row < 0:
            return
        marker_id = row + 1
        prev = self._params.copy()
        if marker_id == prev.active_marker_id:
            return
        updated = self._build_params()
        if marker_bank_params_equal(updated, prev):
            return
        self._params = updated
        self.active_marker_changed.emit(marker_id)
        self.params_changed.emit(updated)

    def _pick_color(self, row: int) -> None:
        widgets = self._row_widgets(row)
        current = QColor(str(widgets.color_btn.property("markerColor") or "#FFC850"))
        chosen = QColorDialog.getColor(current, self, tr("monitor_markers_pick_color"))
        if not chosen.isValid():
            return
        widgets.color_btn.setProperty("markerColor", chosen.name())
        self._apply_color_button(widgets.color_btn, chosen.name())
        self._emit_params()

    def _peak_here(self, row: int) -> None:
        if self._trace_freqs is None or self._trace_power is None:
            return
        widgets = self._row_widgets(row)
        center_hz = self._parse_freq_mhz(widgets.freq.text())
        peak_hz = find_peak_near(self._trace_freqs, self._trace_power, center_hz)
        widgets.freq.setText(self._mhz_text(peak_hz))
        widgets.mode.blockSignals(True)
        peak_index = widgets.mode.findData("peak")
        if peak_index >= 0:
            widgets.mode.setCurrentIndex(peak_index)
        widgets.mode.blockSignals(False)
        widgets.enabled.setChecked(True)
        self._table.selectRow(row)
        self._emit_params()

    def _all_off(self) -> None:
        self._syncing = True
        try:
            for row in range(MARKER_COUNT):
                self._row_widgets(row).enabled.setChecked(False)
        finally:
            self._syncing = False
        self._emit_params()

    def recargar_textos(self) -> None:
        headers = [
            tr("monitor_markers_col_id"),
            tr("monitor_markers_col_on"),
            tr("monitor_markers_col_mode"),
            tr("monitor_markers_col_ref"),
            tr("monitor_markers_col_frequency"),
            tr("monitor_markers_col_color"),
            tr("monitor_markers_col_line"),
            tr("monitor_markers_col_freq"),
            tr("monitor_markers_col_level"),
            tr("monitor_markers_col_snr"),
            tr("monitor_markers_col_delta_f"),
            tr("monitor_markers_col_delta_level"),
            tr("monitor_markers_col_peak"),
        ]
        for index, label in enumerate(headers):
            self._table.setHorizontalHeaderItem(index, QTableWidgetItem(label))
        for row in range(MARKER_COUNT):
            widgets = self._row_widgets(row)
            for mode_index, key in enumerate(MARKER_MODES):
                widgets.mode.setItemText(mode_index, tr(f"monitor_markers_mode_{key}"))
            widgets.peak_btn.setText(tr("monitor_markers_peak_btn"))
        self._auto_pan.setText(tr("monitor_marker_auto_pan"))
        self._all_off_btn.setText(tr("monitor_markers_all_off"))
        self._info.recargar_textos()

    def set_table_layout_changed_callback(self, callback) -> None:
        self._on_table_layout_changed = callback

    def save_table_header_state(self) -> str:
        return save_header_state(self._table.horizontalHeader())

    def apply_table_header_state(self, state: str) -> None:
        if not isinstance(state, str) or not state:
            return
        self._pending_table_header = state
        self._apply_pending_table_header()

    def _apply_pending_table_header(self) -> None:
        if not self._pending_table_header:
            return
        restore_header_state(self._table.horizontalHeader(), self._pending_table_header)
        self._pending_table_header = ""

    def _notify_table_layout_changed(self) -> None:
        if self._on_table_layout_changed is not None:
            self._on_table_layout_changed()
