"""Vista FFT del analizador Monitor."""
from __future__ import annotations

from typing import Optional

import numpy as np
import time
from PyQt6.QtCore import Qt, QPoint, QRect, QTimer, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QColor, QFont, QPainter, QPen, QPolygon, QShowEvent, QWheelEvent
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QSizePolicy, QWidget

from core.monitor.amplitude_units import (
    amplitude_axis_label,
    dbm_to_display,
    format_amplitude_value,
)
from core.monitor.display_scale import level_to_normalized_y
from core.monitor.display_colors import spectrum_trace_color, spectrum_trace_fill_color
from core.monitor.marker_analysis import estimate_snr_db, interpolate_power_db
from core.monitor.monitor_freq_span_logic import display_span_hz
from core.monitor.spectrum_params import SpectrumFrame, SpectrumParams
from core.monitor.spectrum_plot_mapping import plot_freq_bounds, resample_power_to_grid
from gui.monitor.monitor_marker_draw import draw_f_tune_indicator, draw_fc_center_indicator, draw_markers_on_plot
from gui.monitor.monitor_supervision_draw import (
    draw_supervision_offscreen_indicators,
    draw_supervision_targets_on_plot,
)
from gui.monitor.monitor_plot_layout import (
    DOCK_COLLAPSED_WIDTH,
    FREQ_PLOT_LEFT_MARGIN,
    freq_plot_rect,
    unified_freq_plot_right_gutter,
)
from gui.monitor.monitor_spectrum_dock_panel import MonitorSpectrumDockPanel
from gui.monitor.monitor_spectrum_overlays import MonitorSpectrumSliders, _SLIDER_QSS
from gui.monitor.monitor_spectrum_status_strip import MonitorSpectrumStatusStrip
from i18n.json_translation import tr

_SLIDER_BAR_HEIGHT = 36
_STATUS_STRIP_HEIGHT = 18
_FREQ_AXIS_HEIGHT = 20
_DOCK_COLLAPSED_WIDTH = DOCK_COLLAPSED_WIDTH


def _format_freq_hz(freq_hz: float) -> str:
    if abs(freq_hz) >= 1_000_000_000:
        return f"{freq_hz / 1_000_000_000:.3f} GHz"
    if abs(freq_hz) >= 1_000_000:
        return f"{freq_hz / 1_000_000:.3f} MHz"
    if abs(freq_hz) >= 1_000:
        return f"{freq_hz / 1_000:.1f} kHz"
    return f"{freq_hz:.0f} Hz"


class MonitorSpectrumWidget(QWidget):
    """Traza de potencia vs frecuencia con rejilla estilo analizador."""

    frequency_clicked = pyqtSignal(float)
    span_zoom_requested = pyqtSignal(float, float)
    marker_settings_requested = pyqtSignal()
    marker_activate_requested = pyqtSignal(int)
    marker_drag_active = pyqtSignal(bool)
    dock_settings_changed = pyqtSignal(str, float)
    freq_plot_gutter_changed = pyqtSignal(int)

    def __init__(self, module_id: str, panel_id: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.module_id = module_id
        self.panel_id = panel_id
        self._freqs: Optional[np.ndarray] = None
        self._power: Optional[np.ndarray] = None
        self._center_hz = 100e6
        self._span_hz = 20e6
        self._ref_dbm = 0.0
        self._ref_range_db = 100.0
        self._params = SpectrumParams()
        self._marker_label_rect: QRect | None = None
        self._marker_label_hits: list[tuple[int, QRect, QRect]] = []
        self._pending_drag_freq_hz: float | None = None
        self._label_measure_power: np.ndarray | None = None
        self._label_measure_at: float = 0.0
        self._alert_message = ""
        self._alert_tone = ""
        self._recording_message = ""
        self._recording_blink_on = False
        self._recording_timer = QTimer(self)
        self._recording_timer.setInterval(500)
        self._recording_timer.timeout.connect(self._on_recording_blink)
        self._dock_width = _DOCK_COLLAPSED_WIDTH
        self._plot_drag: str | None = None
        self._drag_from_marker_label = False
        self._marker_drag_active = False
        self._supervision_targets = []
        self._supervision_visible = False
        self._supervision_alarm_states: dict[str, str] = {}
        self._supervision_highlight_keys: set[str] = set()
        self._supervision_pulse_targets = []
        self._supervision_blink_on = False
        self._supervision_blink_ticks = 0
        self._supervision_blink_timer = QTimer(self)
        self._supervision_blink_timer.setInterval(400)
        self._supervision_blink_timer.timeout.connect(self._on_supervision_blink)
        self._drag_start_y = 0.0
        self._drag_start_span = 0.0
        self._drag_start_center_hz = 0.0
        self._drag_plot_start_hz = 0.0
        self._drag_plot_stop_hz = 0.0
        self.setMinimumHeight(160)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self.sliders = MonitorSpectrumSliders(self)
        self._dock = MonitorSpectrumDockPanel(self)
        self._dock.width_changed.connect(self._on_dock_width_changed)
        self._dock.dock_settings_changed.connect(self.dock_settings_changed.emit)
        self.rf_preamp = self._dock.rf_preamp
        self.rf_lna = self._dock.rf_lna
        self.rf_vga = self._dock.rf_vga
        self.ampt = self._dock.ampt
        self.vrange = self._dock.vrange
        self.status = MonitorSpectrumStatusStrip(self)
        self.sliders.show()
        self._dock.show()
        self.status.show()
        self._reposition_overlays()
        self._emit_freq_plot_gutter()

    def freq_plot_right_gutter(self) -> int:
        return unified_freq_plot_right_gutter(dock_width=self._dock_width)

    def _emit_freq_plot_gutter(self) -> None:
        self.freq_plot_gutter_changed.emit(self.freq_plot_right_gutter())

    def _on_dock_width_changed(self, width: int) -> None:
        self._dock_width = max(_DOCK_COLLAPSED_WIDTH, int(width))
        self._reposition_overlays()
        self._emit_freq_plot_gutter()

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        self._reposition_overlays()

    def set_analyzer_params(self, params: SpectrumParams) -> None:
        if self._marker_drag_active:
            preserved_markers = [marker.copy() for marker in self._params.markers]
            preserved_selected = float(self._params.selected_freq_hz)
            preserved_vfo = float(self._params.vfo_freq_hz)
            preserved_active = int(self._params.active_marker_id)
            self._params = params.copy()
            self._params.markers = preserved_markers
            self._params.selected_freq_hz = preserved_selected
            self._params.vfo_freq_hz = preserved_vfo
            self._params.active_marker_id = preserved_active
        else:
            self._params = params.copy()
        self._center_hz = self._params.center_freq_hz
        self._span_hz = display_span_hz(self._params)
        self.sliders.set_params(self._params)
        self._dock.set_params(self._params)
        self.status.set_params(self._params)
        if not self._marker_drag_active:
            self.update()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._reposition_overlays()
        self._emit_freq_plot_gutter()

    def _reposition_overlays(self) -> None:
        margin = self._margins()
        plot = freq_plot_rect(
            self.rect(),
            right_gutter=self.freq_plot_right_gutter(),
            top=margin.top,
            bottom=margin.bottom,
        )
        plot_h = max(60, plot.height())
        self._dock.setFixedSize(self._dock_width, plot_h)
        self._dock.move(self.width() - self._dock_width, plot.top())
        self._dock.raise_()

        slider_w = max(420, plot.width() - 8)
        self.sliders.setFixedSize(slider_w, _SLIDER_BAR_HEIGHT)
        self.sliders.move(plot.left(), 2)
        self.sliders.raise_()

        self.status.setFixedSize(max(1, plot.width()), _STATUS_STRIP_HEIGHT)
        self.status.move(plot.left(), self.height() - _STATUS_STRIP_HEIGHT)
        self.status.raise_()

    def _overlay_hit(self, point) -> bool:
        return (
            self.sliders.geometry().contains(point)
            or self._dock.geometry().contains(point)
            or self.status.geometry().contains(point)
        )

    @pyqtSlot(object)
    def update_frame(self, frame: SpectrumFrame) -> None:
        freqs = np.asarray(frame.freqs_hz, dtype=float).reshape(-1)
        power = np.asarray(frame.power_db, dtype=float).reshape(-1)
        n = min(freqs.size, power.size)
        self._freqs = freqs[:n]
        self._power = power[:n]
        now = time.monotonic()
        if self._marker_drag_active:
            pass
        elif now - self._label_measure_at >= 0.25 or self._label_measure_power is None:
            self._label_measure_power = power[:n].copy()
            self._label_measure_at = now
        self._center_hz = frame.center_freq_hz
        self._span_hz = frame.span_hz
        if self._params.ref_scale_auto:
            self._ref_dbm = frame.ref_level_dbm
            self._ref_range_db = frame.ref_range_db
        else:
            self._ref_dbm = self._params.ref_level_dbm
            self._ref_range_db = self._params.ref_range_db
        self.update()

    def _trace_arrays(self) -> tuple[float, float, np.ndarray, np.ndarray]:
        """Eje frecuencia + potencia alineados para pintar (nunca por índice de bin)."""
        if self._freqs is None or self._power is None:
            return 0.0, 0.0, np.array([]), np.array([])
        freqs = np.asarray(self._freqs, dtype=float).reshape(-1)
        power = np.asarray(self._power, dtype=float).reshape(-1)
        n = min(freqs.size, power.size)
        if n < 2:
            return 0.0, 0.0, freqs[:n], power[:n]
        freqs = freqs[:n]
        power = power[:n]
        start, stop = self._plot_freq_bounds()
        if stop <= start:
            stop = start + 1.0
        return start, stop, freqs, power

    def set_display_params(self, ref_level_dbm: float, ref_range_db: float) -> None:
        self._ref_dbm = ref_level_dbm
        self._ref_range_db = ref_range_db
        self.update()

    def set_alert_message(self, message: str, *, tone: str = "warn") -> None:
        self._alert_message = str(message or "").strip()
        self._alert_tone = tone if self._alert_message else ""
        self.update()

    def clear_alert_message(self) -> None:
        self._alert_message = ""
        self._alert_tone = ""
        self.update()

    def set_recording_banner(self, message: str) -> None:
        text = str(message or "").strip()
        self._recording_message = text
        if text:
            if not self._recording_timer.isActive():
                self._recording_blink_on = True
                self._recording_timer.start()
        else:
            self._recording_timer.stop()
            self._recording_blink_on = False
        self.update()

    def _on_recording_blink(self) -> None:
        if not self._recording_message:
            self._recording_timer.stop()
            self._recording_blink_on = False
            return
        self._recording_blink_on = not self._recording_blink_on
        self.update()

    def alert_tone(self) -> str:
        return self._alert_tone

    def recargar_textos(self) -> None:
        self.sliders.recargar_textos()
        self._dock.recargar_textos()
        self.status.recargar_textos()
        self.update()

    def apply_visual_theme(self, _style_key: str) -> None:
        self.update()

    def _plot_freq_bounds(self) -> tuple[float, float]:
        return plot_freq_bounds(self._params, self._freqs)

    def _freq_to_plot_x(self, freq_hz: float, plot) -> int:
        start, stop = self._plot_freq_bounds()
        span = stop - start
        if span <= 0:
            return plot.left() + plot.width() // 2
        ratio = (float(freq_hz) - start) / span
        ratio = max(0.0, min(1.0, ratio))
        return plot.left() + int(ratio * plot.width())

    def _plot_width(self) -> int:
        return max(1, self._plot_rect().width())

    def _plot_rect(self):
        margin = self._margins()
        return freq_plot_rect(
            self.rect(),
            right_gutter=self.freq_plot_right_gutter(),
            top=margin.top,
            bottom=margin.bottom,
        )

    def _freq_at_plot_x(self, x: float) -> float | None:
        plot = self._plot_rect()
        if plot.width() <= 0:
            return None
        rel = x - plot.left()
        if rel < 0 or rel > plot.width():
            return None
        start, stop = self._plot_freq_bounds()
        ratio = rel / max(plot.width(), 1)
        return float(start + ratio * (stop - start))

    def _is_fc_readout(self) -> bool:
        return self._params.freq_readout == "fc"

    def _marker_plot_x(self, freq_hz: float, plot) -> int:
        if self._is_fc_readout():
            return plot.left() + plot.width() // 2
        return self._freq_to_plot_x(freq_hz, plot)

    def _markers_draggable(self) -> bool:
        return self._params.freq_readout == "f"

    def _marker_label_hit(self, point: QPoint) -> tuple[int, QRect, QRect] | None:
        for marker_id, full_rect, handle_rect in reversed(self._marker_label_hits):
            if full_rect.contains(point):
                return marker_id, full_rect, handle_rect
        return None

    def _begin_marker_plot_drag(self, x: float, y: float) -> None:
        if not self._markers_draggable():
            return
        plot = self._plot_rect()
        if plot.width() <= 0:
            return
        self._drag_from_marker_label = True
        self._plot_drag = "marker"
        self._set_marker_drag_active(True)
        self._drag_start_x = x
        self._drag_start_y = y
        self._drag_start_span = display_span_hz(self._params)
        self._drag_start_center_hz = float(self._params.center_freq_hz)
        pstart, pstop = self._plot_freq_bounds()
        self._drag_plot_start_hz = float(pstart)
        self._drag_plot_stop_hz = float(pstop)
        self.setCursor(Qt.CursorShape.ClosedHandCursor)
        self._emit_freq_at(x)

    def _set_marker_drag_active(self, active: bool) -> None:
        if self._marker_drag_active == active:
            return
        self._marker_drag_active = active
        self.marker_drag_active.emit(active)

    def _preview_marker_drag(self, freq_hz: float) -> None:
        """Actualización local inmediata al arrastrar F (evita parpadeo sombra SDR / marcas)."""
        if self._params.freq_readout != "f":
            return
        from core.monitor.marker_bank import patch_active_marker_frequency
        from core.monitor.monitor_freq_span_logic import clamp_freq_to_visible_hz

        local = self._params.copy()
        clamped = clamp_freq_to_visible_hz(local, freq_hz)
        patch_active_marker_frequency(local, clamped)
        if local.operating_mode_enum().demod_enabled():
            local.vfo_freq_hz = local.selected_freq_hz
        self._params = local
        self.update()

    def _emit_freq_at(self, x: float) -> None:
        if not self._markers_draggable():
            return
        freq = self._freq_at_plot_x(x)
        if freq is None:
            return
        self._preview_marker_drag(freq)
        if self._marker_drag_active:
            self._pending_drag_freq_hz = float(freq)
            return
        self.frequency_clicked.emit(freq)

    def _emit_fc_pan(self, x: float) -> None:
        plot = self._plot_rect()
        if plot.width() <= 0:
            return
        span = self._drag_plot_stop_hz - self._drag_plot_start_hz
        if span <= 0:
            return
        delta_hz = (x - self._drag_start_x) / max(plot.width(), 1) * span
        self.frequency_clicked.emit(float(self._drag_start_center_hz + delta_hz))

    def _marker_color(self) -> QColor:
        if self._params.freq_readout == "f":
            return QColor(255, 200, 80)
        return QColor(100, 190, 255)

    def _marker_label_bg(self) -> QColor:
        if self._params.freq_readout == "f":
            return QColor(80, 56, 24, 230)
        return QColor(30, 64, 96, 230)

    def _marker_label_border(self) -> QColor:
        if self._params.freq_readout == "f":
            return QColor(128, 96, 48)
        return QColor(58, 112, 144)

    def _begin_fc_pan(self, x: float, y: float) -> None:
        plot = self._plot_rect()
        if plot.width() <= 0:
            return
        self._drag_from_marker_label = False
        self._plot_drag = "pan_fc"
        self._drag_start_x = x
        self._drag_start_y = y
        self._drag_start_span = display_span_hz(self._params)
        self._drag_start_center_hz = float(self._params.center_freq_hz)
        pstart, pstop = self._plot_freq_bounds()
        self._drag_plot_start_hz = float(pstart)
        self._drag_plot_stop_hz = float(pstop)

    def _resolve_plot_drag(self, x: float, y: float) -> None:
        dx = abs(x - self._drag_start_x)
        dy = abs(y - self._drag_start_y)
        if dx < 6 and dy < 6:
            return
        if dx >= dy:
            if self._is_fc_readout():
                self._plot_drag = "pan_fc"
            elif self._markers_draggable():
                self._plot_drag = "marker"
                self._set_marker_drag_active(True)
                self._emit_freq_at(x)
            else:
                return
        else:
            self._plot_drag = "span"

    def mouseMoveEvent(self, event) -> None:
        point = event.position().toPoint()
        x = event.position().x()
        y = event.position().y()
        label_hit = self._marker_label_hit(point) if self._markers_draggable() else None
        if label_hit is not None and self._plot_drag is None:
            self.setCursor(Qt.CursorShape.OpenHandCursor)
        elif self._plot_drag == "pending":
            self._resolve_plot_drag(x, y)
            if self._plot_drag == "pan_fc":
                self.setCursor(Qt.CursorShape.ClosedHandCursor)
                self._emit_fc_pan(x)
            elif self._plot_drag == "marker":
                self.setCursor(Qt.CursorShape.ClosedHandCursor)
                self._emit_freq_at(x)
            elif self._plot_drag == "span":
                self.setCursor(Qt.CursorShape.SizeVerCursor)
        elif self._plot_drag == "pan_fc":
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            self._emit_fc_pan(x)
        elif self._plot_drag == "marker":
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            self._emit_freq_at(x)
        elif self._plot_drag == "span":
            self.setCursor(Qt.CursorShape.SizeVerCursor)
            dy = self._drag_start_y - event.position().y()
            factor = 1.0 + dy / 120.0
            if factor > 0.05:
                anchor = self._freq_at_plot_x(event.position().x()) or self._params.center_freq_hz
                self.span_zoom_requested.emit(float(factor), float(anchor))
        elif self._plot_rect().contains(point):
            if self._is_fc_readout():
                self.setCursor(
                    Qt.CursorShape.ClosedHandCursor
                    if self._plot_drag == "pan_fc"
                    else Qt.CursorShape.OpenHandCursor
                )
            elif self._markers_draggable():
                self.setCursor(Qt.CursorShape.OpenHandCursor)
            elif label_hit is not None:
                self.setCursor(Qt.CursorShape.OpenHandCursor)
            else:
                self.setCursor(Qt.CursorShape.ArrowCursor)
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if self._plot_drag == "pending" and self._markers_draggable():
            dx = abs(event.position().x() - self._drag_start_x)
            dy = abs(event.position().y() - self._drag_start_y)
            if dx < 6 and dy < 6:
                freq = self._freq_at_plot_x(event.position().x())
                if freq is not None:
                    self._preview_marker_drag(freq)
                    self.frequency_clicked.emit(float(freq))
        if self._marker_drag_active:
            pending = self._pending_drag_freq_hz
            self._pending_drag_freq_hz = None
            self._set_marker_drag_active(False)
            if pending is not None:
                self.frequency_clicked.emit(pending)
        self._plot_drag = None
        self._drag_from_marker_label = False
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._markers_draggable():
            label_hit = self._marker_label_hit(event.position().toPoint())
            if label_hit is not None:
                marker_id, _full, _handle = label_hit
                if marker_id != int(self._params.active_marker_id):
                    self.marker_activate_requested.emit(marker_id)
                self.marker_settings_requested.emit()
                return
        super().mouseDoubleClickEvent(event)

    def wheelEvent(self, event: QWheelEvent) -> None:
        if self._overlay_hit(event.position().toPoint()):
            super().wheelEvent(event)
            return
        delta = event.angleDelta().y()
        if delta == 0:
            return
        factor = 1.12 if delta > 0 else 1.0 / 1.12
        anchor = self._freq_at_plot_x(event.position().x()) or self._params.center_freq_hz
        self.span_zoom_requested.emit(factor, float(anchor))
        event.accept()

    def mousePressEvent(self, event) -> None:
        if (
            event.button() == Qt.MouseButton.LeftButton
            and self._markers_draggable()
        ):
            label_hit = self._marker_label_hit(event.position().toPoint())
            if label_hit is not None:
                marker_id, _full, _handle = label_hit
                if marker_id != int(self._params.active_marker_id):
                    self.marker_activate_requested.emit(marker_id)
                self._begin_marker_plot_drag(event.position().x(), event.position().y())
                return
        if self._overlay_hit(event.position().toPoint()):
            super().mousePressEvent(event)
            return
        if (
            event.button() == Qt.MouseButton.LeftButton
            and self._freqs is not None
            and len(self._freqs) > 0
        ):
            plot = self._plot_rect()
            if plot.contains(event.position().toPoint()):
                x = event.position().x()
                y = event.position().y()
                self.setFocus(Qt.FocusReason.MouseFocusReason)
                if self._is_fc_readout():
                    self._begin_fc_pan(x, y)
                else:
                    self._drag_from_marker_label = False
                    self._plot_drag = "pending"
                    self._drag_start_x = x
                    self._drag_start_y = y
                    self._drag_start_span = display_span_hz(self._params)
                    self._drag_start_center_hz = float(self._params.center_freq_hz)
                    pstart, pstop = self._plot_freq_bounds()
                    self._drag_plot_start_hz = float(pstart)
                    self._drag_plot_stop_hz = float(pstop)
        super().mousePressEvent(event)

    def keyPressEvent(self, event) -> None:
        if self._params.freq_readout == "f":
            from core.monitor.monitor_freq_span_logic import nudge_selected_freq_hz, nudge_step_hz

            step = nudge_step_hz(self._params)
            if event.key() == Qt.Key.Key_Left:
                freq = nudge_selected_freq_hz(self._params, -step)
                self._preview_marker_drag(freq)
                self.frequency_clicked.emit(freq)
                event.accept()
                return
            if event.key() == Qt.Key.Key_Right:
                freq = nudge_selected_freq_hz(self._params, step)
                self._preview_marker_drag(freq)
                self.frequency_clicked.emit(freq)
                event.accept()
                return
        super().keyPressEvent(event)

    def _margins(self):
        from dataclasses import dataclass

        @dataclass
        class M:
            left: int = FREQ_PLOT_LEFT_MARGIN
            right: int = 0
            top: int = _SLIDER_BAR_HEIGHT + 6
            bottom: int = _FREQ_AXIS_HEIGHT + _STATUS_STRIP_HEIGHT + 4

        return M()

    def _display_top_bottom(self) -> tuple[float, float]:
        unit = self._params.amplitude_unit
        offset = self._params.ref_offset_db
        top = dbm_to_display(self._ref_dbm, unit, ref_offset_db=offset)
        bottom = top - self._ref_range_db
        return top, bottom

    def _visible_freq_window(self) -> tuple[float, float]:
        return self._plot_freq_bounds()

    def _build_marker_label(self, freq_hz: float) -> str:
        unit = self._params.amplitude_unit
        parts: list[str] = []
        prefix = "FC" if self._params.freq_readout == "fc" else "F"
        level_db: float | None = None
        if self._freqs is not None and self._power is not None:
            level_db = interpolate_power_db(self._freqs, self._power, freq_hz)
        parts.append(prefix)
        if self._params.marker_show_freq:
            parts.append(_format_freq_hz(freq_hz))
        if self._params.marker_show_level and level_db is not None:
            level_disp = dbm_to_display(
                level_db, unit, ref_offset_db=self._params.ref_offset_db
            )
            parts.append(format_amplitude_value(level_disp, unit))
        if (
            self._params.marker_show_snr
            and level_db is not None
            and self._power is not None
        ):
            snr = estimate_snr_db(self._power, level_db)
            if snr is not None:
                parts.append(f"S/R {snr:.1f} dB")
        return " · ".join(parts)

    def _draw_offscreen_marker(
        self,
        painter: QPainter,
        plot,
        *,
        left: bool,
        freq_hz: float,
        color: QColor | None = None,
    ) -> None:
        marker_color = color or self._marker_color()
        painter.setPen(QPen(marker_color, 2))
        painter.setBrush(marker_color)
        mid_y = (plot.top() + plot.bottom()) // 2
        tip_x = plot.left() + 6 if left else plot.right() - 6
        base_x = plot.left() + 18 if left else plot.right() - 18
        if left:
            tri = QPolygon(
                [
                    QPoint(tip_x, mid_y),
                    QPoint(base_x, mid_y - 10),
                    QPoint(base_x, mid_y + 10),
                ]
            )
        else:
            tri = QPolygon(
                [
                    QPoint(tip_x, mid_y),
                    QPoint(base_x, mid_y - 10),
                    QPoint(base_x, mid_y + 10),
                ]
            )
        painter.drawPolygon(tri)
        painter.setPen(marker_color.lighter(115))
        painter.setFont(QFont("Consolas", 8, QFont.Weight.Bold))
        label_x = plot.left() + 4 if left else plot.right() - 14
        label = "F" if self._params.freq_readout == "f" else "FC"
        painter.drawText(label_x, plot.top() + 12, label)
        painter.setPen(marker_color.lighter(130))
        painter.setFont(QFont("Consolas", 7))
        painter.drawText(
            plot.left() + 4 if left else plot.right() - 72,
            plot.bottom() - 4,
            _format_freq_hz(freq_hz),
        )
        label = self._build_marker_label(freq_hz)
        if label:
            painter.setPen(QColor(255, 210, 120))
            painter.setFont(QFont("Consolas", 7))
            painter.drawText(
                plot.left() + 4 if left else plot.right() - 120,
                plot.top() + 24,
                label,
            )

    def set_supervision_targets(self, targets, *, visible: bool = True) -> None:
        self._supervision_targets = list(targets or [])
        self._supervision_visible = bool(visible)
        self.update()

    def set_supervision_alarm_states(self, states: dict[str, str]) -> None:
        self._supervision_alarm_states = dict(states or {})
        self.update()

    def pulse_supervision_highlight(
        self,
        channel_keys: list[str],
        *,
        pulse_targets=None,
    ) -> None:
        self._supervision_highlight_keys = {str(key) for key in channel_keys if key}
        self._supervision_pulse_targets = list(pulse_targets or [])
        self._supervision_blink_on = True
        self._supervision_blink_ticks = 12
        self._supervision_blink_timer.start()
        self.update()

    def _on_supervision_blink(self) -> None:
        if self._supervision_blink_ticks <= 0:
            self._supervision_blink_timer.stop()
            self._supervision_highlight_keys.clear()
            self._supervision_pulse_targets = []
            self._supervision_blink_on = False
            self.update()
            return
        self._supervision_blink_ticks -= 1
        self._supervision_blink_on = not self._supervision_blink_on
        self.update()

    def _draw_supervision_targets(self, painter: QPainter, plot) -> None:
        has_pulse = bool(self._supervision_highlight_keys and self._supervision_blink_on)
        if not self._supervision_visible and not (has_pulse and self._supervision_pulse_targets):
            return
        if not self._supervision_targets and not (has_pulse and self._supervision_pulse_targets):
            return
        draw_supervision_targets_on_plot(
            painter,
            plot,
            self._supervision_targets if self._supervision_visible else [],
            freq_to_x=self._freq_to_plot_x,
            alarm_states=self._supervision_alarm_states,
            highlight_keys=self._supervision_highlight_keys,
            highlight_pulse=self._supervision_blink_on,
            pulse_targets=self._supervision_pulse_targets if has_pulse else None,
        )
        if has_pulse and self._supervision_pulse_targets:
            plot_start, plot_stop = self._plot_freq_bounds()
            from i18n.json_translation import tr

            draw_supervision_offscreen_indicators(
                painter,
                plot,
                self._supervision_pulse_targets,
                plot_start_hz=plot_start,
                plot_stop_hz=plot_stop,
                highlight_keys=self._supervision_highlight_keys,
                highlight_pulse=self._supervision_blink_on,
                alarm_states=self._supervision_alarm_states,
                hint_text=tr("monitor_supervision_offscreen_span"),
            )

    def _draw_markers(self, painter: QPainter, plot) -> None:
        holder: list[QRect | None] = [None]
        hits: list[tuple[int, QRect, QRect]] = []
        draggable = self._markers_draggable()
        label_power = None if self._marker_drag_active else self._label_measure_power
        draw_markers_on_plot(
            painter,
            plot,
            self._params,
            freqs=self._freqs,
            power=label_power if label_power is not None else self._power,
            freq_to_x=self._freq_to_plot_x,
            draw_labels=True,
            active_label_rect=holder,
            label_hit_regions=hits,
            show_drag_handles=draggable,
            live_measurements=not self._marker_drag_active,
            allow_peak_search=False,
        )
        self._marker_label_rect = holder[0]
        self._marker_label_hits = hits

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        rect = self.rect()
        margin = self._margins()
        plot = self._plot_rect()

        bg = QColor(12, 16, 22)
        grid = QColor(40, 48, 58)
        trace = spectrum_trace_color(self._params)
        text = QColor(180, 190, 200)
        unit = self._params.amplitude_unit
        unit_label = amplitude_axis_label(unit)
        painter.fillRect(rect, bg)

        if plot.width() <= 0 or plot.height() <= 0:
            painter.setPen(text)
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, tr("monitor_spectrum_waiting"))
            painter.end()
            return

        top_disp, bottom_disp = self._display_top_bottom()
        span_disp = max(top_disp - bottom_disp, 1.0)
        for i in range(11):
            y = plot.top() + int(i / 10 * plot.height())
            painter.setPen(QPen(grid, 1))
            painter.drawLine(plot.left(), y, plot.right(), y)
            level = top_disp - i * (self._ref_range_db / 10.0)
            painter.setPen(text)
            painter.setFont(QFont("Consolas", 8))
            label = format_amplitude_value(level, unit)
            painter.drawText(4, y + 4, label)

        painter.setPen(QColor(90, 110, 130))
        painter.drawText(4, margin.top - 6, unit_label)

        self._draw_demod_bandwidth_shade(painter, plot)

        plot_start, plot_stop = self._plot_freq_bounds()
        plot_span = plot_stop - plot_start
        for i in range(9):
            x = plot.left() + int(i / 8 * plot.width())
            painter.setPen(QPen(grid, 1))
            painter.drawLine(x, plot.top(), x, plot.bottom())
            freq = plot_start + i / 8 * plot_span if plot_span > 0 else plot_start
            painter.setPen(text)
            painter.drawText(x - 28, plot.bottom() + 18, _format_freq_hz(freq))

        painter.setPen(QPen(trace, 1.5))
        trace_start, trace_stop, trace_freqs, trace_power_raw = self._trace_arrays()
        if trace_freqs.size >= 2 and trace_power_raw.size >= 2:
            offset = self._params.ref_offset_db
            n_cols = max(2, plot.width())
            trace_power = resample_power_to_grid(
                trace_freqs,
                trace_power_raw,
                start_hz=trace_start,
                stop_hz=trace_stop,
                num_columns=n_cols,
            )
            for i in range(n_cols - 1):
                x1 = plot.left() + i
                x2 = plot.left() + i + 1
                p1 = dbm_to_display(float(trace_power[i]), unit, ref_offset_db=offset)
                p2 = dbm_to_display(float(trace_power[i + 1]), unit, ref_offset_db=offset)
                y1 = self._level_to_y(p1, plot, top_disp, bottom_disp)
                y2 = self._level_to_y(p2, plot, top_disp, bottom_disp)
                painter.drawLine(x1, y1, x2, y2)
        else:
            painter.setPen(text)
            painter.drawText(plot, Qt.AlignmentFlag.AlignCenter, tr("monitor_spectrum_waiting"))

        self._draw_supervision_targets(painter, plot)
        self._draw_markers(painter, plot)
        draw_fc_center_indicator(
            painter,
            plot,
            self._params,
            freqs=self._freqs,
            power=self._power,
        )
        draw_f_tune_indicator(
            painter,
            plot,
            self._params,
            freqs=self._freqs,
            power=self._power,
            freq_to_x=self._freq_to_plot_x,
        )
        self._draw_freq_window_edges(painter, plot)
        self._draw_recording_banner(painter, plot)
        self._draw_alert_banner(painter, plot)

        painter.end()

    def _draw_recording_banner(self, painter: QPainter, plot) -> None:
        if not self._recording_message or not self._recording_blink_on:
            return
        bg = QColor(160, 24, 24, 230)
        fg = QColor(255, 230, 230)
        font = QFont("Segoe UI", 10)
        font.setBold(True)
        painter.setFont(font)
        metrics = painter.fontMetrics()
        pad_x, pad_y = 12, 5
        text_w = metrics.horizontalAdvance(self._recording_message)
        banner_w = min(plot.width() - 16, text_w + pad_x * 2)
        banner_h = metrics.height() + pad_y * 2
        banner_x = plot.left() + (plot.width() - banner_w) // 2
        banner_y = plot.top() + 36
        painter.fillRect(banner_x, banner_y, banner_w, banner_h, bg)
        painter.setPen(fg)
        painter.drawText(
            banner_x + pad_x,
            banner_y + pad_y + metrics.ascent(),
            self._recording_message,
        )

    def _draw_alert_banner(self, painter: QPainter, plot) -> None:
        if not self._alert_message:
            return
        tone = self._alert_tone or "warn"
        if tone == "error":
            bg = QColor(120, 24, 24, 220)
            fg = QColor(255, 220, 220)
        elif tone == "info":
            bg = QColor(24, 56, 96, 210)
            fg = QColor(210, 230, 255)
        else:
            bg = QColor(96, 72, 16, 210)
            fg = QColor(255, 240, 190)
        font = QFont("Segoe UI", 9)
        font.setBold(True)
        painter.setFont(font)
        metrics = painter.fontMetrics()
        pad_x, pad_y = 10, 4
        text_w = metrics.horizontalAdvance(self._alert_message)
        banner_w = min(plot.width() - 16, text_w + pad_x * 2)
        banner_h = metrics.height() + pad_y * 2
        banner_x = plot.left() + (plot.width() - banner_w) // 2
        banner_y = plot.top() + 8
        painter.fillRect(banner_x, banner_y, banner_w, banner_h, bg)
        painter.setPen(fg)
        painter.drawText(
            banner_x + pad_x,
            banner_y + pad_y + metrics.ascent(),
            self._alert_message,
        )

    def _demod_tune_hz(self) -> float:
        """Centro del sombreado demod: FC → centro; F → frecuencia seleccionada."""
        params = self._params
        if params.freq_readout == "f" and params.selected_freq_hz > 0:
            return float(params.selected_freq_hz)
        if params.freq_readout == "fc":
            return float(params.center_freq_hz)
        if params.vfo_freq_hz > 0:
            return float(params.vfo_freq_hz)
        return float(params.center_freq_hz)

    def _draw_demod_bandwidth_shade(self, painter: QPainter, plot) -> None:
        params = self._params
        if not params.show_demod_bandwidth:
            return
        if params.capture_mode != "iq" or not params.demod_enabled():
            return
        tune_hz = self._demod_tune_hz()
        half_bw = max(float(params.demod_bandwidth_hz) * 0.5, 1.0)
        f_start = tune_hz - half_bw
        f_stop = tune_hz + half_bw
        plot_start, plot_stop = self._plot_freq_bounds()
        if f_stop < plot_start or f_start > plot_stop:
            return
        x0 = self._freq_to_plot_x(max(f_start, plot_start), plot)
        x1 = self._freq_to_plot_x(min(f_stop, plot_stop), plot)
        if x1 <= x0:
            return
        trace = spectrum_trace_color(params)
        fill = spectrum_trace_fill_color(params)
        painter.fillRect(x0, plot.top(), x1 - x0, plot.height(), fill)
        from gui.monitor.monitor_freq_readout_labels import freq_readout_mode_abbr

        mode = freq_readout_mode_abbr(params)
        label = f"DEMOD · {mode} · {_format_freq_hz(tune_hz)}"
        painter.setFont(QFont("Consolas", 7, QFont.Weight.Bold))
        label_color = QColor(trace)
        label_color.setAlpha(220)
        painter.setPen(label_color)
        painter.drawText(x0 + 3, plot.top() + 10, label)

    def _draw_freq_window_edges(self, painter: QPainter, plot) -> None:
        if self._params.capture_mode == "iq":
            return
        if not self._params.uses_start_stop_window():
            return
        start = self._params.freq_start_hz()
        stop = self._params.freq_stop_hz()
        color = (
            QColor(255, 170, 70, 180)
            if self._params.freq_readout == "f"
            else QColor(100, 180, 255, 180)
        )
        painter.setPen(QPen(color, 1, Qt.PenStyle.DotLine))
        for freq in (start, stop):
            x = self._freq_to_plot_x(freq, plot)
            painter.drawLine(x, plot.top(), x, plot.bottom())
        painter.setPen(color)
        painter.setFont(QFont("Consolas", 7))
        painter.drawText(plot.left() + 2, plot.top() + 36, _format_freq_hz(start))
        painter.drawText(plot.right() - 72, plot.top() + 36, _format_freq_hz(stop))

    @staticmethod
    def _level_to_y(level: float, plot, top: float, bottom: float) -> int:
        t = level_to_normalized_y(level, top, bottom)
        return plot.top() + int(t * plot.height())
