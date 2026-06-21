"""Diálogo de visibilidad del marcador F (estilo analizador profesional)."""
from __future__ import annotations

from typing import Optional

from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from core.monitor.spectrum_params import SpectrumParams
from i18n.json_translation import tr


def edit_marker_display_dialog(
    params: SpectrumParams,
    *,
    parent: Optional[QWidget] = None,
) -> SpectrumParams | None:
    dlg = QDialog(parent)
    dlg.setWindowTitle(tr("monitor_marker_config_title"))
    layout = QVBoxLayout(dlg)
    layout.addWidget(QLabel(tr("monitor_marker_config_intro")))

    form = QFormLayout()
    cb_line = QCheckBox(tr("monitor_marker_show_line"))
    cb_line.setChecked(params.marker_show_line)
    cb_freq = QCheckBox(tr("monitor_marker_show_freq"))
    cb_freq.setChecked(params.marker_show_freq)
    cb_level = QCheckBox(tr("monitor_marker_show_level"))
    cb_level.setChecked(params.marker_show_level)
    cb_snr = QCheckBox(tr("monitor_marker_show_snr"))
    cb_snr.setChecked(params.marker_show_snr)
    cb_pan = QCheckBox(tr("monitor_marker_auto_pan"))
    cb_pan.setChecked(params.marker_auto_pan)
    form.addRow(cb_line)
    form.addRow(cb_freq)
    form.addRow(cb_level)
    form.addRow(cb_snr)
    form.addRow(cb_pan)
    layout.addLayout(form)

    buttons = QDialogButtonBox(
        QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
    )
    buttons.accepted.connect(dlg.accept)
    buttons.rejected.connect(dlg.reject)
    layout.addWidget(buttons)

    if dlg.exec() != QDialog.DialogCode.Accepted:
        return None

    updated = params.copy()
    updated.marker_show_line = cb_line.isChecked()
    updated.marker_show_freq = cb_freq.isChecked()
    updated.marker_show_level = cb_level.isChecked()
    updated.marker_show_snr = cb_snr.isChecked()
    updated.marker_auto_pan = cb_pan.isChecked()
    return updated
