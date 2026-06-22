"""Espectrograma (waterfall) del Monitor."""
from __future__ import annotations

from collections import deque
from typing import Deque, Optional

import numpy as np
from PyQt6.QtCore import Qt, QRect, QTimer, pyqtSlot
from PyQt6.QtGui import QColor, QImage, QPainter, QShowEvent
from PyQt6.QtWidgets import QWidget

from core.monitor.spectrum_params import SpectrumFrame, SpectrumParams
from core.monitor.spectrum_plot_mapping import plot_freq_bounds, resample_power_to_grid
from core.monitor.monitor_bw_profile import plot_resample_method
from core.monitor.waterfall_colormap import (
    HISTORY_AUTO_MARGIN_DB,
    power_db_to_rgb,
    resolve_waterfall_levels,
)
from gui.monitor.monitor_marker_draw import draw_f_tune_indicator, draw_fc_center_indicator, draw_markers_on_plot
from gui.monitor.monitor_supervision_draw import (
    draw_supervision_offscreen_indicators,
    draw_supervision_targets_on_plot,
)
from gui.monitor.monitor_plot_layout import (
    DOCK_COLLAPSED_WIDTH,
    FREQ_PLOT_LEFT_MARGIN,
    WATERFALL_SLIDER_PANEL_WIDTH,
    freq_plot_column_count,
    freq_plot_rect,
    unified_freq_plot_right_gutter,
)
from gui.monitor.monitor_waterfall_overlays import MonitorWaterfallLevelSliders


class MonitorWaterfallWidget(QWidget):
    """Historial temporal de líneas FFT apiladas verticalmente."""

    def __init__(
        self,
        module_id: str,
        panel_id: str,
        *,
        history_lines: int = 120,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.module_id = module_id
        self.panel_id = panel_id
        self._history_lines = history_lines
        self._history: Deque[np.ndarray] = deque(maxlen=history_lines)
        self._params = SpectrumParams()
        self._freqs: Optional[np.ndarray] = None
        self._plot_columns = 512
        self._ref_dbm = 0.0
        self._ref_range_db = 100.0
        self._right_gutter = unified_freq_plot_right_gutter(dock_width=DOCK_COLLAPSED_WIDTH)
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
        self._image: Optional[QImage] = None
        self._contrast_bottom_ema: float | None = None
        self._contrast_top_ema: float | None = None
        self._ref_smooth: tuple[float, float] | None = None
        self.setMinimumHeight(120)

        self.levels = MonitorWaterfallLevelSliders(self)
        self.levels.show()
        self._reposition_overlays()

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        self._reposition_overlays()

    def resizeEvent(self, event) -> None:
        old_cols = self._plot_columns
        super().resizeEvent(event)
        self._reposition_overlays()
        new_cols = self._plot_column_count()
        if self._history and abs(new_cols - old_cols) > 8:
            self.clear_history()
        self.update()

    def set_analyzer_params(self, params: SpectrumParams) -> None:
        from core.monitor.monitor_flow_log import (
            WATERFALL_DISPLAY_PARAM_KEYS,
            changed_param_key_names,
        )

        prev = self._params
        old_start, old_stop = plot_freq_bounds(prev, self._freqs)
        self._params = params.copy()
        self.levels.set_params(
            params,
            ref_level_dbm=self._ref_dbm,
            ref_range_db=self._ref_range_db,
        )
        new_start, new_stop = plot_freq_bounds(self._params, self._freqs)
        if (old_start, old_stop) != (new_start, new_stop) and self._history:
            self.clear_history()
        elif self._history and changed_param_key_names(
            prev, self._params, WATERFALL_DISPLAY_PARAM_KEYS
        ):
            self._rebuild_image()
            self.update()

    def set_freq_plot_right_gutter(self, gutter: int) -> None:
        gutter = max(int(gutter), int(WATERFALL_SLIDER_PANEL_WIDTH))
        if gutter == self._right_gutter:
            return
        self._right_gutter = gutter
        self._reposition_overlays()
        if self._history:
            self._rebuild_image()
        self.update()

    def _freq_plot_rect(self) -> QRect:
        return freq_plot_rect(
            self.rect(),
            right_gutter=self._right_gutter,
            top=2,
            bottom=2,
        )

    def _plot_column_count(self) -> int:
        return freq_plot_column_count(self._freq_plot_rect())

    def _reposition_overlays(self) -> None:
        self.levels.reposition(
            self.width(),
            self.height(),
            right_gutter=self._right_gutter,
        )
        self.levels.raise_()

    def _overlay_hit(self, point) -> bool:
        return self.levels.geometry().contains(point)

    def clear_history(self) -> None:
        """Vacía el historial (p. ej. al cambiar RBW/fft_size)."""
        self._history.clear()
        self._image = None
        self._contrast_bottom_ema = None
        self._contrast_top_ema = None
        self._ref_smooth = None

    def _track_contrast_ema(self, row: np.ndarray) -> None:
        """Suaviza min/max por línea (evita parpadeos horizontales en AUTO contraste)."""
        if row.size == 0:
            return
        row_min = float(np.min(row))
        row_max = float(np.max(row))
        alpha = 0.06
        margin = HISTORY_AUTO_MARGIN_DB
        if self._contrast_bottom_ema is None:
            self._contrast_bottom_ema = row_min - margin
            self._contrast_top_ema = row_max + margin
            return
        self._contrast_bottom_ema = (
            self._contrast_bottom_ema * (1.0 - alpha) + (row_min - margin) * alpha
        )
        self._contrast_top_ema = (
            self._contrast_top_ema * (1.0 - alpha) + (row_max + margin) * alpha
        )

    @pyqtSlot(object)
    def update_frame(self, frame: SpectrumFrame) -> None:
        freqs = np.asarray(frame.freqs_hz, dtype=float)
        power = np.asarray(frame.power_db, dtype=np.float32)
        self._freqs = freqs
        start, stop = plot_freq_bounds(self._params, freqs)
        n_cols = self._plot_column_count()
        self._plot_columns = n_cols
        resampled = resample_power_to_grid(
            freqs,
            power,
            start_hz=start,
            stop_hz=stop,
            num_columns=n_cols,
            method=plot_resample_method(self._params),
        )
        if self._history and int(self._history[-1].shape[0]) != int(resampled.shape[0]):
            self.clear_history()
        if self._params.ref_scale_auto:
            from core.rf.presentation.scale import stabilize_ref_level_dbm, stabilize_ref_range_db

            target_ref = float(frame.ref_level_dbm)
            target_rng = float(frame.ref_range_db)
            if self._ref_smooth is None:
                self._ref_dbm = target_ref
                self._ref_range_db = stabilize_ref_range_db(target_rng, None)
                self._ref_smooth = (self._ref_dbm, self._ref_range_db)
            else:
                prev_ref, prev_rng = self._ref_smooth
                self._ref_dbm = stabilize_ref_level_dbm(target_ref, prev_ref)
                self._ref_range_db = stabilize_ref_range_db(target_rng, prev_rng)
                self._ref_smooth = (self._ref_dbm, self._ref_range_db)
        else:
            self._ref_smooth = None
            self._ref_dbm = float(self._params.ref_level_dbm)
            self._ref_range_db = float(self._params.ref_range_db)
        self._history.append(resampled)
        if self._params.waterfall_contrast_auto:
            self._track_contrast_ema(resampled)
        self._append_scrolled_line(resampled)
        self.update()

    def _waterfall_levels(self, history_power_db: np.ndarray | None = None) -> tuple[float, float]:
        if (
            self._params.waterfall_contrast_auto
            and self._contrast_bottom_ema is not None
            and self._contrast_top_ema is not None
            and (history_power_db is None or history_power_db.size == 0)
        ):
            bottom = float(self._contrast_bottom_ema)
            top = float(self._contrast_top_ema)
            if bottom >= top:
                top = bottom + 20.0
            return bottom, top
        return resolve_waterfall_levels(
            min_db=self._params.waterfall_min_db,
            max_db=self._params.waterfall_max_db,
            link_spectrum=self._params.waterfall_auto_levels,
            contrast_auto=self._params.waterfall_contrast_auto,
            ref_level_dbm=self._ref_dbm,
            ref_range_db=self._ref_range_db,
            history_power_db=history_power_db,
        )

    def _append_scrolled_line(self, row: np.ndarray) -> None:
        width = int(row.shape[0])
        height = self._history_lines
        if width < 2 or height < 2:
            self._rebuild_image()
            return
        if (
            self._image is None
            or self._image.isNull()
            or self._image.width() != width
            or self._image.height() != height
        ):
            self._rebuild_image()
            return

        min_db, max_db = self._waterfall_levels()
        rgb_row = power_db_to_rgb(
            row.reshape(1, -1),
            min_db=min_db,
            max_db=max_db,
            colormap=self._params.waterfall_colormap,
        )[0]
        row_img = QImage(
            np.ascontiguousarray(rgb_row).data,
            width,
            1,
            width * 3,
            QImage.Format.Format_RGB888,
        ).copy()

        painter = QPainter(self._image)
        src = self._image.copy(QRect(0, 0, width, height - 1))
        painter.drawImage(0, 1, src)
        painter.drawImage(0, 0, row_img)
        painter.end()

    def set_display_params(self, ref_level_dbm: float, ref_range_db: float) -> None:
        self._ref_dbm = float(ref_level_dbm)
        self._ref_range_db = float(ref_range_db)
        self.levels.set_params(
            self._params,
            ref_level_dbm=self._ref_dbm,
            ref_range_db=self._ref_range_db,
        )
        if self._history:
            self._rebuild_image()
        self.update()

    def _rebuild_image(self) -> None:
        if not self._history:
            self._image = None
            return
        widths = {int(row.shape[0]) for row in self._history}
        if len(widths) != 1:
            self.clear_history()
            return
        try:
            rows = np.stack(list(self._history), axis=0)
        except ValueError:
            self.clear_history()
            return
        if rows.size == 0:
            self._image = None
            return
        height, width = rows.shape
        min_db, max_db = self._waterfall_levels(history_power_db=rows)
        rgb = power_db_to_rgb(
            rows,
            min_db=min_db,
            max_db=max_db,
            colormap=self._params.waterfall_colormap,
        )
        rgb = np.flipud(rgb)
        rgb = np.ascontiguousarray(rgb)
        self._image = QImage(
            rgb.data,
            width,
            height,
            width * 3,
            QImage.Format.Format_RGB888,
        ).copy()

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

    def recargar_textos(self) -> None:
        self.levels.recargar_textos()
        self.update()

    def apply_visual_theme(self, _style_key: str) -> None:
        self.update()

    def mousePressEvent(self, event) -> None:
        if self._overlay_hit(event.position().toPoint()):
            super().mousePressEvent(event)
            return
        super().mousePressEvent(event)

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        bg = QColor(8, 10, 14)
        painter.fillRect(self.rect(), bg)
        plot = self._freq_plot_rect()
        if self._image is not None and not self._image.isNull() and plot.width() > 0 and plot.height() > 0:
            painter.drawImage(plot, self._image)

        def _freq_to_x(freq_hz: float, plot_rect: QRect) -> int:
            start, stop = plot_freq_bounds(self._params, self._freqs)
            span = stop - start
            if span <= 0:
                return plot_rect.left() + plot_rect.width() // 2
            ratio = (float(freq_hz) - start) / span
            ratio = max(0.0, min(1.0, ratio))
            return plot_rect.left() + int(ratio * plot_rect.width())

        has_pulse = bool(self._supervision_highlight_keys and self._supervision_blink_on)
        if (self._supervision_visible and self._supervision_targets) or (
            has_pulse and self._supervision_pulse_targets
        ):
            draw_supervision_targets_on_plot(
                painter,
                plot,
                self._supervision_targets if self._supervision_visible else [],
                freq_to_x=_freq_to_x,
                draw_labels=False,
                alarm_states=self._supervision_alarm_states,
                highlight_keys=self._supervision_highlight_keys,
                highlight_pulse=self._supervision_blink_on,
                pulse_targets=self._supervision_pulse_targets if has_pulse else None,
            )
            if has_pulse and self._supervision_pulse_targets:
                start, stop = plot_freq_bounds(self._params, self._freqs)
                from i18n.json_translation import tr

                draw_supervision_offscreen_indicators(
                    painter,
                    plot,
                    self._supervision_pulse_targets,
                    plot_start_hz=start,
                    plot_stop_hz=stop,
                    highlight_keys=self._supervision_highlight_keys,
                    highlight_pulse=self._supervision_blink_on,
                    alarm_states=self._supervision_alarm_states,
                    hint_text=tr("monitor_supervision_offscreen_span"),
                )

        draw_markers_on_plot(
            painter,
            plot,
            self._params,
            freqs=self._freqs,
            power=None,
            freq_to_x=_freq_to_x,
            draw_labels=False,
            allow_peak_search=False,
        )
        draw_fc_center_indicator(
            painter,
            plot,
            self._params,
            freqs=self._freqs,
            power=None,
        )
        draw_f_tune_indicator(
            painter,
            plot,
            self._params,
            freqs=self._freqs,
            power=None,
            freq_to_x=_freq_to_x,
        )
        painter.end()
