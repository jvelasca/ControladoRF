"""Diálogos modales para editar valores de la franja de estado del espectro."""
from __future__ import annotations

from typing import Optional

from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from core.monitor.amplitude_units import (
    amplitude_axis_label,
    dbm_to_display,
    display_to_dbm,
)
from core.monitor.display_scale import REF_SCALE_PRESETS
from core.monitor.monitor_freq_span_logic import (
    clamp_center_hz,
    patch_center_freq,
    patch_freq_start,
    patch_freq_step,
    patch_freq_stop,
    patch_manual_span,
    patch_ref_auto,
    patch_ref_level,
    patch_ref_range,
    patch_rf_input,
    patch_hackrf_lna,
    patch_hackrf_vga,
    ui_span_min_hz,
)
from core.monitor.hackrf_rx_gains import VGA_GAIN_MAX_DB
from core.monitor.monitor_mode_profile import source_freq_limits_hz
from core.monitor.spectrum_params import SpectrumParams
from gui.monitor.monitor_numeric_control import MonitorDecimalSpinBox
from i18n.json_translation import tr


class _MonitorValueDialog(QDialog):
    def __init__(
        self,
        *,
        title: str,
        parent: Optional[QWidget] = None,
        hint: str = "",
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        layout = QVBoxLayout(self)
        if hint:
            hint_label = QLabel(hint, self)
            hint_label.setWordWrap(True)
            layout.addWidget(hint_label)
        self._form = QFormLayout()
        layout.addLayout(self._form)
        self._buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self._buttons.accepted.connect(self.accept)
        self._buttons.rejected.connect(self.reject)
        layout.addWidget(self._buttons)
        self._auto_selected = False

    def add_auto_button(self, text: str) -> QPushButton:
        btn = self._buttons.addButton(text, QDialogButtonBox.ButtonRole.ActionRole)
        btn.clicked.connect(self._select_auto)
        return btn

    def _select_auto(self) -> None:
        self._auto_selected = True
        self.accept()

    def auto_selected(self) -> bool:
        return self._auto_selected


def _read_spin_mhz(spin: MonitorDecimalSpinBox) -> float:
    spin.commit_editing()
    return float(spin.value())


def edit_center_freq_dialog(
    params: SpectrumParams,
    *,
    parent: Optional[QWidget] = None,
) -> Optional[SpectrumParams]:
    fmin, fmax = source_freq_limits_hz(params.source_id)
    dialog = _MonitorValueDialog(
        title=tr("monitor_status_dialog_center_title"),
        parent=parent,
    )
    spin = MonitorDecimalSpinBox(dialog)
    spin.setDecimals(6)
    spin.setSuffix(" MHz")
    spin.setRange(fmin / 1_000_000.0, fmax / 1_000_000.0)
    spin.setValue(params.center_freq_hz / 1_000_000.0)
    spin.selectAll()
    dialog._form.addRow(tr("monitor_status_dialog_center_label"), spin)
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return None
    hz = clamp_center_hz(params, _read_spin_mhz(spin) * 1_000_000.0)
    return patch_center_freq(params, hz)


def edit_freq_start_dialog(
    params: SpectrumParams,
    *,
    parent: Optional[QWidget] = None,
) -> Optional[SpectrumParams]:
    fmin, fmax = source_freq_limits_hz(params.source_id)
    dialog = _MonitorValueDialog(
        title=tr("monitor_status_dialog_start_title"),
        parent=parent,
        hint=tr("monitor_status_dialog_start_hint"),
    )
    spin = MonitorDecimalSpinBox(dialog)
    spin.setDecimals(6)
    spin.setSuffix(" MHz")
    spin.setRange(fmin / 1_000_000.0, fmax / 1_000_000.0)
    spin.setValue(params.freq_start_hz() / 1_000_000.0)
    spin.selectAll()
    dialog._form.addRow(tr("monitor_status_dialog_start_label"), spin)
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return None
    return patch_freq_start(params, _read_spin_mhz(spin) * 1_000_000.0)


def edit_freq_stop_dialog(
    params: SpectrumParams,
    *,
    parent: Optional[QWidget] = None,
) -> Optional[SpectrumParams]:
    fmin, fmax = source_freq_limits_hz(params.source_id)
    dialog = _MonitorValueDialog(
        title=tr("monitor_status_dialog_stop_title"),
        parent=parent,
        hint=tr("monitor_status_dialog_stop_hint"),
    )
    spin = MonitorDecimalSpinBox(dialog)
    spin.setDecimals(6)
    spin.setSuffix(" MHz")
    spin.setRange(fmin / 1_000_000.0, fmax / 1_000_000.0)
    spin.setValue(params.freq_stop_hz() / 1_000_000.0)
    spin.selectAll()
    dialog._form.addRow(tr("monitor_status_dialog_stop_label"), spin)
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return None
    return patch_freq_stop(params, _read_spin_mhz(spin) * 1_000_000.0)


def edit_freq_step_dialog(
    params: SpectrumParams,
    *,
    parent: Optional[QWidget] = None,
) -> Optional[SpectrumParams]:
    dialog = _MonitorValueDialog(
        title=tr("monitor_status_dialog_step_title"),
        parent=parent,
    )
    spin = MonitorDecimalSpinBox(dialog)
    spin.setDecimals(3)
    spin.setSuffix(" kHz")
    spin.setRange(0.001, 1_000_000.0)
    spin.setValue(max(params.freq_step_hz, 1000.0) / 1000.0)
    spin.selectAll()
    dialog._form.addRow(tr("monitor_status_dialog_step_label"), spin)
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return None
    return patch_freq_step(params, _read_spin_mhz(spin) * 1000.0)


def edit_span_dialog(
    params: SpectrumParams,
    *,
    parent: Optional[QWidget] = None,
) -> Optional[SpectrumParams]:
    minimum = ui_span_min_hz(params)
    iq = params.capture_mode == "iq"
    dialog = _MonitorValueDialog(
        title=tr("monitor_status_dialog_bandwidth_title")
        if iq
        else tr("monitor_status_dialog_span_title"),
        parent=parent,
        hint=tr("monitor_status_dialog_bandwidth_hint")
        if iq
        else tr("monitor_status_dialog_span_hint_sweep"),
    )
    spin = MonitorDecimalSpinBox(dialog)
    spin.setDecimals(3)
    spin.setSuffix(" MHz")
    spin.setRange(minimum / 1_000_000.0, params.max_span_hz / 1_000_000.0)
    if params.span_mode == "manual":
        value_mhz = params.manual_span_hz / 1_000_000.0
    else:
        value_mhz = params.display_span_hz() / 1_000_000.0
    spin.setValue(max(minimum / 1_000_000.0, value_mhz))
    spin.selectAll()
    dialog._form.addRow(
        tr("monitor_status_dialog_bandwidth_label")
        if iq
        else tr("monitor_status_dialog_span_label"),
        spin,
    )
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return None
    requested_hz = _read_spin_mhz(spin) * 1_000_000.0
    from core.monitor.monitor_mode_guard import span_requires_analyzer_mode
    from gui.monitor.monitor_mode_notify import format_mode_restriction

    notice = span_requires_analyzer_mode(params, requested_hz)
    if notice is not None:
        from PyQt6.QtWidgets import QMessageBox

        QMessageBox.warning(
            parent,
            tr("monitor_mode_warn_title"),
            format_mode_restriction(notice),
        )
    return patch_manual_span(params, requested_hz)


def edit_ref_level_dialog(
    params: SpectrumParams,
    *,
    parent: Optional[QWidget] = None,
) -> Optional[SpectrumParams]:
    unit = params.amplitude_unit
    dialog = _MonitorValueDialog(
        title=tr("monitor_status_dialog_ref_title"),
        parent=parent,
        hint=tr("monitor_status_dialog_ref_hint"),
    )
    dialog.add_auto_button(tr("monitor_ampt_auto"))
    spin = MonitorDecimalSpinBox(dialog)
    spin.setDecimals(1)
    spin.setSuffix(f" {amplitude_axis_label(unit)}")
    spin.setRange(-200.0, 50.0)
    display = dbm_to_display(params.ref_level_dbm, unit, ref_offset_db=params.ref_offset_db)
    spin.setValue(display)
    spin.selectAll()
    dialog._form.addRow(tr("monitor_status_dialog_ref_label"), spin)
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return None
    if dialog.auto_selected():
        return patch_ref_auto(params, enabled=True)
    ref_dbm = display_to_dbm(_read_spin_mhz(spin), unit, ref_offset_db=params.ref_offset_db)
    return patch_ref_level(params, ref_dbm)


def edit_ref_range_dialog(
    params: SpectrumParams,
    *,
    parent: Optional[QWidget] = None,
) -> Optional[SpectrumParams]:
    dialog = _MonitorValueDialog(
        title=tr("monitor_status_dialog_range_title"),
        parent=parent,
    )
    dialog.add_auto_button(tr("monitor_ampt_auto"))
    spin = MonitorDecimalSpinBox(dialog)
    spin.setDecimals(0)
    spin.setSuffix(" dB")
    spin.setRange(10.0, 120.0)
    spin.setSingleStep(10.0)
    spin.setValue(params.ref_range_db)
    spin.selectAll()
    dialog._form.addRow(tr("monitor_status_dialog_range_label"), spin)
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return None
    if dialog.auto_selected():
        return patch_ref_auto(params, enabled=True)
    range_db = _read_spin_mhz(spin)
    preset = min(REF_SCALE_PRESETS, key=lambda p: abs(p[0] - range_db))
    return patch_ref_range(params, range_db, db_div=preset[1])


def edit_rf_input_dialog(
    params: SpectrumParams,
    *,
    parent: Optional[QWidget] = None,
) -> Optional[SpectrumParams]:
    dialog = _MonitorValueDialog(
        title=tr("monitor_status_dialog_rf_title"),
        parent=parent,
        hint=tr("monitor_status_dialog_rf_hint"),
    )
    from PyQt6.QtWidgets import QCheckBox

    lna = MonitorDecimalSpinBox(dialog)
    lna.setDecimals(0)
    lna.setRange(0, 40)
    lna.setSingleStep(8)
    lna.setSuffix(" dB")
    lna.setValue(float(params.lna_gain_db))

    vga = MonitorDecimalSpinBox(dialog)
    vga.setDecimals(0)
    vga.setRange(0, 62)
    vga.setSingleStep(2)
    vga.setSuffix(" dB")
    vga.setValue(float(params.vga_gain_db))

    preamp = QCheckBox(tr("monitor_status_dialog_rf_preamp"), dialog)
    preamp.setChecked(params.rf_amp_enable)

    dialog._form.addRow(tr("monitor_status_dialog_rf_lna"), lna)
    dialog._form.addRow(tr("monitor_status_dialog_rf_vga"), vga)
    dialog._form.addRow("", preamp)
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return None
    return patch_rf_input(
        params,
        lna_gain_db=int(lna.value()),
        vga_gain_db=int(vga.value()),
        rf_amp_enable=preamp.isChecked(),
    )


def edit_lna_dialog(
    params: SpectrumParams,
    *,
    parent: Optional[QWidget] = None,
) -> Optional[SpectrumParams]:
    dialog = _MonitorValueDialog(
        title=tr("monitor_status_dialog_lna_title"),
        parent=parent,
    )
    spin = MonitorDecimalSpinBox(dialog)
    spin.setDecimals(0)
    spin.setRange(0, 40)
    spin.setSingleStep(8)
    spin.setSuffix(" dB")
    spin.setValue(float(params.lna_gain_db))
    spin.selectAll()
    dialog._form.addRow(tr("monitor_status_dialog_rf_lna"), spin)
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return None
    return patch_hackrf_lna(params, int(spin.value()))


def edit_vga_dialog(
    params: SpectrumParams,
    *,
    parent: Optional[QWidget] = None,
) -> Optional[SpectrumParams]:
    dialog = _MonitorValueDialog(
        title=tr("monitor_status_dialog_vga_title"),
        parent=parent,
    )
    spin = MonitorDecimalSpinBox(dialog)
    spin.setDecimals(0)
    spin.setRange(0, VGA_GAIN_MAX_DB)
    spin.setSingleStep(2)
    spin.setSuffix(" dB")
    spin.setValue(float(params.vga_gain_db))
    spin.selectAll()
    dialog._form.addRow(tr("monitor_status_dialog_rf_vga"), spin)
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return None
    return patch_hackrf_vga(params, int(spin.value()))
