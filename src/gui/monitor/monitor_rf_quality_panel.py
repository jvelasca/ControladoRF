"""Panel de métricas RF Fase 1 — calidad de enlace en Configuración/Radio."""
from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPainter, QPen
from PyQt6.QtWidgets import (
    QFrame,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QTableWidget,
    QTableWidgetItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from core.monitor.monitor_format import format_freq_short
from core.monitor.rf_metrics import RfLinkMetrics
from gui.monitor.led_meter_widget import LabeledCompactLedMeter
from gui.monitor.monitor_rf_bandwidth_widget import MonitorRfBandwidthStripWidget
from i18n.json_translation import tr


def _fmt_db(value: Optional[float], *, suffix: str = " dBm") -> str:
    if value is None:
        return "—"
    return f"{value:.1f}{suffix}"


def _fmt_hz(value: Optional[float]) -> str:
    if value is None:
        return "—"
    if value >= 1_000_000:
        return f"{value / 1_000_000:.3f} MHz"
    if value >= 1_000:
        return f"{value / 1_000:.1f} kHz"
    return f"{value:.0f} Hz"


class MonitorLinkScoreBar(QFrame):
    """Semáforo de puntuación de enlace 0–100."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("MonitorLinkScoreBar")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        row = QLabel()
        row.setObjectName("MonitorLinkScoreTitle")
        self._title = row
        layout.addWidget(row)

        self._bar = QProgressBar()
        self._bar.setObjectName("MonitorLinkScoreProgress")
        self._bar.setRange(0, 100)
        self._bar.setValue(0)
        self._bar.setTextVisible(True)
        self._bar.setFormat("%v / 100")
        layout.addWidget(self._bar)

        self._grade = QLabel()
        self._grade.setObjectName("MonitorLinkScoreGrade")
        layout.addWidget(self._grade)

        self._marker = QLabel()
        self._marker.setWordWrap(True)
        self._marker.setObjectName("MonitorLinkScoreMarker")
        layout.addWidget(self._marker)

        self.set_idle()

    def set_idle(self, *, message: str | None = None) -> None:
        self._title.setText(tr("monitor_rf_link_score"))
        self._bar.setValue(0)
        self._bar.setFormat("—")
        self._grade.setText(message or tr("monitor_rf_waiting"))
        self._grade.setStyleSheet("color: #8a95a8;")
        self._marker.setText("")

    def update_metrics(self, metrics: RfLinkMetrics) -> None:
        self._title.setText(tr("monitor_rf_link_score"))
        if not metrics.is_valid():
            self.set_idle(message=tr("monitor_rf_waiting"))
            return
        score = int(metrics.link_score)
        self._bar.setValue(score)
        self._bar.setFormat(f"{score} / 100")
        grade_key = f"monitor_rf_grade_{metrics.link_grade}"
        self._grade.setText(tr(grade_key))
        colors = {
            "good": "#6ecf8a",
            "fair": "#e0c060",
            "poor": "#e07070",
            "unknown": "#8a95a8",
        }
        self._grade.setStyleSheet(f"color: {colors.get(metrics.link_grade, colors['unknown'])};")
        self._marker.setText(
            tr("monitor_rf_marker_freq").format(freq=format_freq_short(metrics.marker_freq_hz))
        )


class MonitorRfAcpMiniMeters(QFrame):
    """ACP adyacente L/R — vúmetros LED compactos (dBc, mayor = mejor)."""

    _ACP_MIN_DB = 0.0
    _ACP_MAX_DB = 50.0

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(3)
        title = QLabel(tr("monitor_rf_acp_title"))
        title.setObjectName("MonitorRfAcpTitle")
        layout.addWidget(title)
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        self._left = LabeledCompactLedMeter(
            "L",
            segments=12,
            bar_height=11,
            min_db=self._ACP_MIN_DB,
            max_db=self._ACP_MAX_DB,
            mode="acp",
            value_suffix=" dBc",
            parent=self,
        )
        self._right = LabeledCompactLedMeter(
            "R",
            segments=12,
            bar_height=11,
            min_db=self._ACP_MIN_DB,
            max_db=self._ACP_MAX_DB,
            mode="acp",
            value_suffix=" dBc",
            parent=self,
        )
        row.addWidget(self._left, stretch=1)
        row.addWidget(self._right, stretch=1)
        layout.addLayout(row)

    def set_values(self, left_db: Optional[float], right_db: Optional[float]) -> None:
        self._left.set_level(left_db, active=left_db is not None)
        self._right.set_level(right_db, active=right_db is not None)


class MonitorRfQualityPanel(QFrame):
    """Métricas RF Fase 1 integradas en pestaña RADIO."""

    bandwidth_changed = pyqtSignal(float)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("MonitorRfQualityPanel")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(8)

        self._heading = QLabel(tr("monitor_rf_quality_title"))
        self._heading.setObjectName("MonitorRfQualityHeading")
        self._heading.setWordWrap(True)
        layout.addWidget(self._heading)

        self._score = MonitorLinkScoreBar(self)
        layout.addWidget(self._score)

        self._bw_strip = MonitorRfBandwidthStripWidget(self)
        self._bw_strip.bandwidth_changed.connect(self.bandwidth_changed.emit)
        layout.addWidget(self._bw_strip)

        self._acp = MonitorRfAcpMiniMeters(self)
        layout.addWidget(self._acp)

        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)

        self._lbl_channel = QLabel(tr("monitor_rf_channel_power"))
        self._val_channel = QLabel("—")
        self._lbl_obw = QLabel(tr("monitor_rf_obw"))
        self._val_obw = QLabel("—")
        self._lbl_snr = QLabel(tr("monitor_rf_snr"))
        self._val_snr = QLabel("—")
        self._lbl_noise = QLabel(tr("monitor_rf_noise_floor"))
        self._val_noise = QLabel("—")
        self._lbl_offset = QLabel(tr("monitor_rf_carrier_offset"))
        self._val_offset = QLabel("—")

        form.addRow(self._lbl_channel, self._val_channel)
        form.addRow(self._lbl_obw, self._val_obw)
        form.addRow(self._lbl_snr, self._val_snr)
        form.addRow(self._lbl_noise, self._val_noise)
        form.addRow(self._lbl_offset, self._val_offset)
        layout.addLayout(form)

        rds_header = QHBoxLayout()
        rds_header.setContentsMargins(0, 0, 0, 0)
        self._rds_title = QLabel(tr("monitor_rds_section"))
        self._rds_toggle = QToolButton()
        self._rds_toggle.setCheckable(True)
        self._rds_toggle.setChecked(False)
        self._rds_toggle.setAutoRaise(True)
        self._rds_toggle.setText("▼")
        self._rds_toggle.setToolTip(tr("monitor_rds_toggle_tip"))
        self._rds_toggle.toggled.connect(self._on_rds_toggled)
        rds_header.addWidget(self._rds_title)
        rds_header.addStretch(1)
        rds_header.addWidget(self._rds_toggle)
        layout.addLayout(rds_header)

        self._rds_table = QTableWidget(6, 2, self)
        self._rds_table.setObjectName("MonitorRdsInfoTable")
        self._rds_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._rds_table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self._rds_table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._rds_table.verticalHeader().setVisible(False)
        self._rds_table.horizontalHeader().setVisible(False)
        self._rds_table.setShowGrid(True)
        self._rds_table.setMaximumHeight(168)
        self._rds_row_keys = (
            "monitor_rds_pi",
            "monitor_rds_country",
            "monitor_rds_coverage",
            "monitor_rds_reference",
            "monitor_rds_pty",
            "monitor_rds_music",
        )
        for row, key in enumerate(self._rds_row_keys):
            label_item = QTableWidgetItem(tr(key))
            label_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self._rds_table.setItem(row, 0, label_item)
            self._rds_table.setItem(row, 1, QTableWidgetItem("—"))
        self._rds_table.setColumnWidth(0, 130)
        self._rds_table.horizontalHeader().setStretchLastSection(True)
        self._rds_table.setVisible(False)
        layout.addWidget(self._rds_table)

        self._hint = QLabel(tr("monitor_rf_quality_hint"))
        self._hint.setWordWrap(True)
        self._hint.setObjectName("MonitorRfQualityHint")
        self._hint.setVisible(False)
        layout.addWidget(self._hint)

    def _on_rds_toggled(self, expanded: bool) -> None:
        self._rds_table.setVisible(expanded)
        self._rds_toggle.setText("▲" if expanded else "▼")

    def configure_demod_bandwidth(
        self,
        *,
        demod_bw_hz: float,
        min_hz: float,
        max_hz: float,
        step_hz: float,
    ) -> None:
        self._bw_strip.set_limits(min_hz=min_hz, max_hz=max_hz, step_hz=step_hz)
        self._bw_strip.set_demod_bandwidth_hz(demod_bw_hz)
        self._bw_strip.setVisible(True)

    def set_idle(self, *, message: str | None = None) -> None:
        self._score.set_idle(message=message)
        self._bw_strip.set_obw_hz(None)
        self._acp.set_values(None, None)
        for val in (
            self._val_channel,
            self._val_obw,
            self._val_snr,
            self._val_noise,
            self._val_offset,
        ):
            val.setText("—")
        self.clear_rds_info()

    def clear_rds_info(self) -> None:
        for row in range(self._rds_table.rowCount()):
            item = self._rds_table.item(row, 1)
            if item is not None:
                item.setText("—")

    def update_rds_info(self, state) -> None:
        ps = (getattr(state, "rds_ps", "") or "").strip()
        pty = (getattr(state, "rds_pty", "") or "").strip()
        if pty and ps:
            program = f"{pty} · {ps}"
        elif ps:
            program = ps
        else:
            program = pty or "—"
        values = (
            getattr(state, "rds_pi", "") or "—",
            getattr(state, "rds_country", "") or "—",
            getattr(state, "rds_coverage", "") or "—",
            getattr(state, "rds_reference", "") or "—",
            program,
            getattr(state, "rds_music", "") or "—",
        )
        for row, text in enumerate(values):
            item = self._rds_table.item(row, 1)
            if item is None:
                item = QTableWidgetItem()
                self._rds_table.setItem(row, 1, item)
            item.setText(str(text))

    def update_metrics(self, metrics: RfLinkMetrics) -> None:
        self._score.update_metrics(metrics)
        self._bw_strip.set_obw_hz(metrics.obw_hz)
        self._acp.set_values(metrics.acp_left_db, metrics.acp_right_db)
        self._val_channel.setText(_fmt_db(metrics.channel_power_dbm))
        self._val_obw.setText(_fmt_hz(metrics.obw_hz))
        self._val_snr.setText(_fmt_db(metrics.snr_db, suffix=" dB"))
        self._val_noise.setText(_fmt_db(metrics.noise_floor_dbm))
        if metrics.carrier_offset_hz is None:
            self._val_offset.setText("—")
        else:
            self._val_offset.setText(f"{metrics.carrier_offset_hz:+.0f} Hz")

    def set_hint_key(self, key: str) -> None:
        pass

    def recargar_textos(self) -> None:
        self._heading.setText(tr("monitor_rf_quality_title"))
        self._hint.setText(tr("monitor_rf_quality_hint"))
        self._lbl_channel.setText(tr("monitor_rf_channel_power"))
        self._lbl_obw.setText(tr("monitor_rf_obw"))
        self._lbl_snr.setText(tr("monitor_rf_snr"))
        self._lbl_noise.setText(tr("monitor_rf_noise_floor"))
        self._lbl_offset.setText(tr("monitor_rf_carrier_offset"))
        self._rds_title.setText(tr("monitor_rds_section"))
        for row, key in enumerate(self._rds_row_keys):
            item = self._rds_table.item(row, 0)
            if item is not None:
                item.setText(tr(key))
