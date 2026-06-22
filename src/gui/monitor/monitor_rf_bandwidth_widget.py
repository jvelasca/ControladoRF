"""Franja demod BW (ajustable) + OBW medido y valor numérico alineado."""

from __future__ import annotations



from typing import TYPE_CHECKING, Optional



from PyQt6.QtCore import Qt, QRect, pyqtSignal

from PyQt6.QtGui import QColor, QMouseEvent, QPainter, QPen

from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSpinBox, QVBoxLayout



from i18n.json_translation import tr



if TYPE_CHECKING:

    from gui.monitor.monitor_rf_bandwidth_widget import MonitorRfBandwidthStripWidget





class _BwPlotArea(QFrame):

    """Área de trazado — el dibujo va aquí, no en el padre (evita quedar tapado por el hijo)."""



    _HANDLE_PX = 7



    def __init__(self, strip: "MonitorRfBandwidthStripWidget") -> None:

        super().__init__(strip)

        self._strip = strip

        self.setMinimumHeight(44)

        self.setFrameShape(QFrame.Shape.NoFrame)

        self.setMouseTracking(True)



    def paintEvent(self, _event) -> None:

        painter = QPainter(self)

        plot = self.rect()

        if plot.width() < 8 or plot.height() < 8:

            painter.end()

            return

        painter.fillRect(plot, QColor(8, 10, 14))

        mid_x = plot.center().x()

        painter.setPen(QPen(QColor(70, 80, 95), 1, Qt.PenStyle.DashLine))

        painter.drawLine(mid_x, plot.top(), mid_x, plot.bottom())



        obw_hz = self._strip._obw_hz

        if obw_hz and obw_hz > 1.0:

            half_obw = obw_hz * 0.5

            ox0 = self._strip._hz_to_x(-half_obw, plot)

            ox1 = self._strip._hz_to_x(half_obw, plot)

            obw_rect = QRect(min(ox0, ox1), plot.top() + 4, abs(ox1 - ox0), plot.height() - 8)

            painter.fillRect(obw_rect, QColor(70, 170, 220, 70))

            painter.setPen(QPen(QColor(90, 190, 240), 1))

            painter.drawRect(obw_rect)



        left, right = self._strip._demod_edges(plot)

        demod_rect = QRect(left, plot.top() + 8, max(8, right - left), plot.height() - 16)

        painter.fillRect(demod_rect, QColor(80, 200, 120, 100))

        painter.setPen(QPen(QColor(100, 220, 140), 1.5))

        painter.drawRect(demod_rect)

        painter.fillRect(left - 2, demod_rect.top(), 4, demod_rect.height(), QColor(220, 240, 230))

        painter.fillRect(right - 2, demod_rect.top(), 4, demod_rect.height(), QColor(220, 240, 230))

        painter.end()



    def _edge_hit(self, pos) -> str | None:

        plot = self.rect()

        if not plot.contains(pos):

            return None

        left, right = self._strip._demod_edges(plot)

        if abs(pos.x() - left) <= self._HANDLE_PX:

            return "left"

        if abs(pos.x() - right) <= self._HANDLE_PX:

            return "right"

        return None



    def mousePressEvent(self, event: QMouseEvent) -> None:

        if event.button() != Qt.MouseButton.LeftButton:

            return super().mousePressEvent(event)

        edge = self._edge_hit(event.position().toPoint())

        if edge:

            self._strip._drag_edge = edge

            event.accept()

            return

        super().mousePressEvent(event)



    def mouseMoveEvent(self, event: QMouseEvent) -> None:

        if self._strip._drag_edge:

            plot = self.rect()

            new_bw = self._strip._x_to_bw_hz(int(event.position().x()), plot)

            if abs(new_bw - self._strip._demod_bw_hz) >= self._strip._bw_step_hz * 0.5:

                self._strip._demod_bw_hz = new_bw

                self._strip._sync_spin_value()

                self._strip.bandwidth_changed.emit(new_bw)

                self.update()

            event.accept()

            return

        edge = self._edge_hit(event.position().toPoint())

        self.setCursor(

            Qt.CursorShape.SizeHorCursor if edge else Qt.CursorShape.ArrowCursor

        )

        super().mouseMoveEvent(event)



    def mouseReleaseEvent(self, event: QMouseEvent) -> None:

        self._strip._drag_edge = None

        self.setCursor(Qt.CursorShape.ArrowCursor)

        super().mouseReleaseEvent(event)





class MonitorRfBandwidthStripWidget(QFrame):

    """Barra central: verde = ancho demodulado (arrastrable), cian = OBW real."""



    bandwidth_changed = pyqtSignal(float)



    _HEADER_HEIGHT = 18



    def __init__(self, parent: Optional[QFrame] = None) -> None:

        super().__init__(parent)

        self.setObjectName("MonitorRfBandwidthStrip")

        self.setMinimumHeight(72)

        self._demod_bw_hz = 200_000.0

        self._obw_hz: Optional[float] = None

        self._bw_min_hz = 100_000.0

        self._bw_max_hz = 250_000.0

        self._bw_step_hz = 25_000.0

        self._drag_edge: str | None = None

        self._syncing_spin = False



        layout = QVBoxLayout(self)

        layout.setContentsMargins(0, 0, 0, 0)

        layout.setSpacing(2)



        header = QHBoxLayout()

        header.setContentsMargins(8, 0, 8, 0)

        header.setSpacing(8)

        self._legend_demod = QLabel(tr("monitor_rf_bw_legend_demod"))

        self._legend_obw = QLabel(tr("monitor_rf_bw_legend_obw"))

        self._legend_demod.setObjectName("MonitorRfBwLegend")

        self._legend_obw.setObjectName("MonitorRfBwLegend")

        self._bw_spin = QSpinBox(self)

        self._bw_spin.setObjectName("MonitorRfBwSpin")

        self._bw_spin.setSuffix(" Hz")

        self._bw_spin.setGroupSeparatorShown(True)

        self._bw_spin.setAlignment(Qt.AlignmentFlag.AlignRight)

        self._bw_spin.valueChanged.connect(self._on_spin_changed)

        header.addWidget(self._legend_demod)

        header.addWidget(self._legend_obw)

        header.addStretch(1)

        header.addWidget(QLabel(tr("monitor_radio_bandwidth") + ":"))

        header.addWidget(self._bw_spin)

        layout.addLayout(header)



        self._plot_host = _BwPlotArea(self)

        layout.addWidget(self._plot_host, stretch=1)



        self._obw_label = QLabel("—")

        self._obw_label.setObjectName("MonitorRfBwObwLabel")

        self._obw_label.setAlignment(Qt.AlignmentFlag.AlignRight)

        obw_row = QHBoxLayout()

        obw_row.setContentsMargins(8, 0, 8, 2)

        obw_row.addStretch(1)

        obw_row.addWidget(self._obw_label)

        layout.addLayout(obw_row)



    def set_limits(self, *, min_hz: float, max_hz: float, step_hz: float) -> None:

        self._bw_min_hz = float(min_hz)

        self._bw_max_hz = float(max_hz)

        self._bw_step_hz = max(float(step_hz), 1.0)

        self._sync_spin_limits()



    def set_demod_bandwidth_hz(self, bw_hz: float) -> None:

        self._demod_bw_hz = max(self._bw_min_hz, min(self._bw_max_hz, float(bw_hz)))

        self._sync_spin_value()

        self._plot_host.update()



    def set_obw_hz(self, obw_hz: Optional[float]) -> None:

        self._obw_hz = None if obw_hz is None else max(0.0, float(obw_hz))

        if self._obw_hz is None:

            self._obw_label.setText("OBW —")

        else:

            self._obw_label.setText(f"OBW {self._obw_hz / 1000:.1f} kHz")

        self._plot_host.update()



    def _sync_spin_limits(self) -> None:

        self._syncing_spin = True

        try:

            self._bw_spin.setRange(int(round(self._bw_min_hz)), int(round(self._bw_max_hz)))

            self._bw_spin.setSingleStep(max(1, int(round(self._bw_step_hz))))

            self._sync_spin_value()

        finally:

            self._syncing_spin = False



    def _sync_spin_value(self) -> None:

        self._syncing_spin = True

        try:

            target = int(round(self._demod_bw_hz))

            if self._bw_spin.value() != target:

                self._bw_spin.setValue(target)

        finally:

            self._syncing_spin = False



    def _on_spin_changed(self, value: int) -> None:

        if self._syncing_spin:

            return

        bw = float(value)

        if abs(bw - self._demod_bw_hz) < self._bw_step_hz * 0.25:

            return

        self._demod_bw_hz = max(self._bw_min_hz, min(self._bw_max_hz, bw))

        self.bandwidth_changed.emit(self._demod_bw_hz)

        self._plot_host.update()



    def _half_span_hz(self) -> float:

        half_demod = self._demod_bw_hz * 0.55

        half_obw = (self._obw_hz or 0.0) * 0.55

        return max(120_000.0, half_demod, half_obw)



    def _hz_to_x(self, delta_hz: float, plot: QRect) -> int:

        half = self._half_span_hz()

        ratio = max(-1.0, min(1.0, delta_hz / half))

        mid = plot.center().x()

        return int(mid + ratio * (plot.width() * 0.48))



    def _x_to_bw_hz(self, x: int, plot: QRect) -> float:

        mid = plot.center().x()

        half_px = max(plot.width() * 0.48, 1.0)

        ratio = abs(x - mid) / half_px

        raw = ratio * self._half_span_hz() * 2.0

        stepped = round(raw / self._bw_step_hz) * self._bw_step_hz

        return max(self._bw_min_hz, min(self._bw_max_hz, stepped))



    def _demod_edges(self, plot: QRect) -> tuple[int, int]:

        half_bw = self._demod_bw_hz * 0.5

        left = self._hz_to_x(-half_bw, plot)

        right = self._hz_to_x(half_bw, plot)

        return min(left, right), max(left, right)



    def recargar_textos(self) -> None:

        self._legend_demod.setText(tr("monitor_rf_bw_legend_demod"))

        self._legend_obw.setText(tr("monitor_rf_bw_legend_obw"))


