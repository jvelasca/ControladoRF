"""Panel DISPLAY — escala, unidades y parámetros básicos de imagen."""
from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from core.monitor.amplitude_units import AMPLITUDE_UNITS, amplitude_axis_label
from core.monitor.display_colors import (
    DEFAULT_SPAN_VIEWPORT_COLOR,
    apply_display_color_defaults,
    apply_display_sdr_color_defaults,
)
from core.monitor.display_scale import REF_RANGE_STEPS_DB
from core.monitor.spectrum_params import SpectrumParams
from gui.color_picker_utils import pick_color
from i18n.json_translation import tr


class MonitorDisplayPanel(QFrame):
    params_changed = pyqtSignal(object)

    _MATRIX_ROWS = (
        ("ref_scale_auto", "monitor_display_ref_auto"),
        ("ampt_mode", "monitor_display_ampt_mode"),
        ("ref_level_dbm", "monitor_display_ref_level"),
        ("ref_range_db", "monitor_display_ref_range"),
        ("ref_offset_db", "monitor_display_ref_offset"),
        ("vertical_divisions", "monitor_display_v_div"),
        ("detector", "monitor_display_detector"),
        ("trace_mode", "monitor_display_trace_mode"),
        ("fft_size", "monitor_display_fft_size"),
        ("waterfall_colormap", "monitor_display_colormap"),
        ("waterfall_auto_levels", "monitor_display_wf_auto"),
        ("waterfall_contrast_auto", "monitor_display_wf_contrast"),
        ("display_span_viewport_color", "monitor_display_span_viewport"),
        ("display_span_handle_color", "monitor_display_span_handle"),
        ("display_trace_color", "monitor_display_trace"),
        ("display_sdr_trace_color", "monitor_display_sdr_trace"),
    )

    _COLOR_FIELDS = (
        ("display_span_viewport_color", "monitor_display_span_viewport"),
        ("display_span_viewport_hi_color", "monitor_display_span_viewport_hi"),
        ("display_span_track_color", "monitor_display_span_track"),
        ("display_span_handle_color", "monitor_display_span_handle"),
        ("display_trace_color", "monitor_display_trace"),
    )

    _SDR_COLOR_FIELDS = (
        ("display_sdr_span_viewport_color", "monitor_display_sdr_span_viewport"),
        ("display_sdr_span_viewport_hi_color", "monitor_display_sdr_span_viewport_hi"),
        ("display_sdr_span_track_color", "monitor_display_sdr_span_track"),
        ("display_sdr_span_handle_color", "monitor_display_sdr_span_handle"),
        ("display_sdr_trace_color", "monitor_display_sdr_trace"),
    )

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("MonitorDisplayPanel")
        self._params = SpectrumParams()
        self._loading = False
        self._color_buttons: dict[str, QPushButton] = {}
        self._sdr_color_buttons: dict[str, QPushButton] = {}
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(8)

        self._heading = QLabel(tr("monitor_display_title"))
        self._heading.setObjectName("MonitorDisplayHeading")
        self._heading.setWordWrap(True)
        layout.addWidget(self._heading)

        unit_group = QGroupBox(tr("monitor_display_unit_group"))
        unit_layout = QHBoxLayout(unit_group)
        self._unit_combo = QComboBox()
        for unit in AMPLITUDE_UNITS:
            self._unit_combo.addItem(amplitude_axis_label(unit), unit)
        self._unit_combo.currentIndexChanged.connect(self._on_unit_changed)
        unit_layout.addWidget(QLabel(tr("monitor_tb_ampt_unit")))
        unit_layout.addWidget(self._unit_combo, stretch=1)
        layout.addWidget(unit_group)

        colors_group = QGroupBox(tr("monitor_display_colors_group"))
        colors_form = QFormLayout(colors_group)
        self._color_labels: dict[str, QLabel] = {}
        for field, label_key in self._COLOR_FIELDS:
            label = QLabel(tr(label_key))
            btn = QPushButton()
            btn.setFixedSize(56, 22)
            btn.clicked.connect(lambda _c=False, f=field: self._pick_color(f))
            self._color_buttons[field] = btn
            self._color_labels[field] = label
            colors_form.addRow(label, btn)
        reset_row = QHBoxLayout()
        reset_row.addStretch(1)
        self._colors_reset = QPushButton(tr("monitor_display_colors_reset"))
        self._colors_reset.clicked.connect(self._reset_display_colors)
        reset_row.addWidget(self._colors_reset)
        colors_form.addRow(reset_row)
        layout.addWidget(colors_group)

        sdr_colors_group = QGroupBox(tr("monitor_display_sdr_colors_group"))
        sdr_form = QFormLayout(sdr_colors_group)
        self._sdr_color_labels: dict[str, QLabel] = {}
        for field, label_key in self._SDR_COLOR_FIELDS:
            label = QLabel(tr(label_key))
            btn = QPushButton()
            btn.setFixedSize(56, 22)
            btn.clicked.connect(lambda _c=False, f=field: self._pick_color(f))
            self._sdr_color_buttons[field] = btn
            self._sdr_color_labels[field] = label
            sdr_form.addRow(label, btn)
        sdr_reset_row = QHBoxLayout()
        sdr_reset_row.addStretch(1)
        self._sdr_colors_reset = QPushButton(tr("monitor_display_sdr_colors_reset"))
        self._sdr_colors_reset.clicked.connect(self._reset_sdr_display_colors)
        sdr_reset_row.addWidget(self._sdr_colors_reset)
        sdr_form.addRow(sdr_reset_row)
        layout.addWidget(sdr_colors_group)

        self._matrix = QTableWidget(len(self._MATRIX_ROWS), 2, self)
        self._matrix.setObjectName("MonitorDisplayMatrix")
        self._matrix.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._matrix.verticalHeader().setVisible(False)
        self._matrix.horizontalHeader().setVisible(False)
        for row, (_key, label_key) in enumerate(self._MATRIX_ROWS):
            self._matrix.setItem(row, 0, QTableWidgetItem(tr(label_key)))
            self._matrix.setItem(row, 1, QTableWidgetItem("—"))
            item0 = self._matrix.item(row, 0)
            if item0 is not None:
                item0.setFlags(Qt.ItemFlag.ItemIsEnabled)
        self._matrix.setColumnWidth(0, 140)
        self._matrix.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self._matrix)

        edit_group = QGroupBox(tr("monitor_display_edit_group"))
        form = QFormLayout(edit_group)
        self._ref_auto = QCheckBox(tr("monitor_ampt_auto"))
        self._ref_auto.toggled.connect(self._emit_patch)
        self._ref_level = QDoubleSpinBox()
        self._ref_level.setRange(-140.0, 30.0)
        self._ref_level.setDecimals(1)
        self._ref_level.valueChanged.connect(self._emit_patch)
        self._ref_range = QComboBox()
        for db in REF_RANGE_STEPS_DB:
            self._ref_range.addItem(f"{db:.0f} dB", db)
        self._ref_range.currentIndexChanged.connect(self._emit_patch)
        self._ref_offset = QDoubleSpinBox()
        self._ref_offset.setRange(-120.0, 120.0)
        self._ref_offset.setDecimals(1)
        self._ref_offset.valueChanged.connect(self._emit_patch)
        self._wf_auto = QCheckBox(tr("monitor_display_wf_auto"))
        self._wf_auto.toggled.connect(self._emit_patch)
        form.addRow(self._ref_auto)
        form.addRow(tr("monitor_display_ref_level"), self._ref_level)
        form.addRow(tr("monitor_display_ref_range"), self._ref_range)
        form.addRow(tr("monitor_display_ref_offset"), self._ref_offset)
        form.addRow(self._wf_auto)
        layout.addWidget(edit_group)
        layout.addStretch(1)

    def set_params(self, params: SpectrumParams) -> None:
        self._loading = True
        self._params = params.copy()
        idx = self._unit_combo.findData(self._params.amplitude_unit)
        if idx >= 0:
            self._unit_combo.setCurrentIndex(idx)
        self._ref_auto.setChecked(bool(self._params.ref_scale_auto))
        self._ref_level.setValue(float(self._params.ref_level_dbm))
        ridx = self._ref_range.findData(self._params.ref_range_db)
        if ridx >= 0:
            self._ref_range.setCurrentIndex(ridx)
        self._ref_offset.setValue(float(self._params.ref_offset_db))
        self._wf_auto.setChecked(bool(self._params.waterfall_auto_levels))
        self._refresh_color_buttons()
        self._refresh_matrix()
        self._loading = False

    def _apply_color_button(self, button: QPushButton, color_hex: str) -> None:
        qcolor = QColor(str(color_hex))
        if not qcolor.isValid():
            qcolor = QColor(DEFAULT_SPAN_VIEWPORT_COLOR)
        button.setStyleSheet(
            f"background-color: {qcolor.name()}; border: 1px solid #556677; border-radius: 2px;"
        )
        button.setToolTip(qcolor.name().upper())

    def _refresh_color_buttons(self) -> None:
        for field, button in self._color_buttons.items():
            self._apply_color_button(button, str(getattr(self._params, field, DEFAULT_SPAN_VIEWPORT_COLOR)))
        for field, button in self._sdr_color_buttons.items():
            self._apply_color_button(button, str(getattr(self._params, field, DEFAULT_SPAN_VIEWPORT_COLOR)))

    def _refresh_matrix(self) -> None:
        p = self._params
        values = {
            "ref_scale_auto": tr("yes") if p.ref_scale_auto else tr("no"),
            "ampt_mode": p.ampt_mode,
            "ref_level_dbm": f"{p.ref_level_dbm:.1f} dBm",
            "ref_range_db": f"{p.ref_range_db:.0f} dB",
            "ref_offset_db": f"{p.ref_offset_db:.1f} dB",
            "vertical_divisions": str(p.vertical_divisions),
            "detector": p.detector,
            "trace_mode": p.trace_mode,
            "fft_size": str(p.fft_size),
            "waterfall_colormap": p.waterfall_colormap,
            "waterfall_auto_levels": tr("yes") if p.waterfall_auto_levels else tr("no"),
            "waterfall_contrast_auto": tr("yes") if p.waterfall_contrast_auto else tr("no"),
            "display_span_viewport_color": p.display_span_viewport_color.upper(),
            "display_span_handle_color": p.display_span_handle_color.upper(),
            "display_trace_color": p.display_trace_color.upper(),
            "display_sdr_trace_color": p.display_sdr_trace_color.upper(),
        }
        for row, (key, label_key) in enumerate(self._MATRIX_ROWS):
            item = self._matrix.item(row, 0)
            if item is not None:
                item.setText(tr(label_key))
            val_item = self._matrix.item(row, 1)
            if val_item is not None:
                val_item.setText(values.get(key, "—"))

    def _pick_color(self, field: str) -> None:
        if self._loading:
            return
        current = str(getattr(self._params, field, DEFAULT_SPAN_VIEWPORT_COLOR))
        chosen = pick_color(self, current)
        if chosen is None:
            return
        updated = self._params.copy()
        setattr(updated, field, chosen)
        self._emit(updated)

    def _reset_display_colors(self) -> None:
        if self._loading:
            return
        self._emit(apply_display_color_defaults(self._params))

    def _reset_sdr_display_colors(self) -> None:
        if self._loading:
            return
        self._emit(apply_display_sdr_color_defaults(self._params))

    def _on_unit_changed(self, _index: int) -> None:
        if self._loading:
            return
        unit = self._unit_combo.currentData()
        if not unit:
            return
        updated = self._params.copy()
        updated.amplitude_unit = str(unit)
        self._emit(updated)

    def _emit_patch(self) -> None:
        if self._loading:
            return
        updated = self._params.copy()
        updated.ref_scale_auto = self._ref_auto.isChecked()
        updated.ref_level_dbm = float(self._ref_level.value())
        updated.ref_range_db = float(self._ref_range.currentData() or updated.ref_range_db)
        updated.ref_offset_db = float(self._ref_offset.value())
        updated.waterfall_auto_levels = self._wf_auto.isChecked()
        if updated.ref_scale_auto:
            updated.ampt_mode = "ref_level"
        self._emit(updated)

    def _emit(self, updated: SpectrumParams) -> None:
        self._params = updated
        self._refresh_color_buttons()
        self._refresh_matrix()
        self.params_changed.emit(updated)

    def recargar_textos(self) -> None:
        self._heading.setText(tr("monitor_display_title"))
        self._colors_reset.setText(tr("monitor_display_colors_reset"))
        self._sdr_colors_reset.setText(tr("monitor_display_sdr_colors_reset"))
        field_labels = dict(self._COLOR_FIELDS) | dict(self._SDR_COLOR_FIELDS)
        for field, label in self._color_labels.items():
            label_key = field_labels.get(field, "")
            if label_key:
                label.setText(tr(label_key))
        for field, label in self._sdr_color_labels.items():
            label_key = field_labels.get(field, "")
            if label_key:
                label.setText(tr(label_key))
        self._refresh_matrix()
