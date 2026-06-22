"""Vúmetro LED compacto reutilizable (demod VU, ACP dBc, etc.)."""
from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import Qt, QRect
from PyQt6.QtGui import QColor, QFont, QPainter, QPen
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QWidget


def _vu_segment_color(db: float) -> QColor:
    if db >= -3.0:
        return QColor(235, 70, 70)
    if db >= -12.0:
        return QColor(240, 170, 55)
    return QColor(55, 205, 95)


def _acp_segment_color(db: float) -> QColor:
    if db < 15.0:
        return QColor(235, 85, 85)
    if db < 30.0:
        return QColor(240, 170, 55)
    return QColor(55, 205, 95)


class CompactLedMeterBar(QFrame):
    """Barra LED horizontal estilo broadcast (compacta)."""

    def __init__(
        self,
        *,
        segments: int = 12,
        height: int = 12,
        min_db: float = -54.0,
        max_db: float = 0.0,
        mode: str = "vu",
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._segments = max(4, int(segments))
        self._min_db = float(min_db)
        self._max_db = float(max_db)
        self._mode = mode
        self._value_db: Optional[float] = None
        self._peak_db: Optional[float] = None
        self._active = False
        self.setFixedHeight(height)

    def set_level(
        self,
        value_db: Optional[float],
        *,
        peak_db: Optional[float] = None,
        active: bool = True,
    ) -> None:
        self._value_db = value_db
        self._peak_db = peak_db if peak_db is not None else value_db
        self._active = active and value_db is not None
        self.update()

    def _segment_color(self, db: float) -> QColor:
        if self._mode == "acp":
            return _acp_segment_color(db)
        return _vu_segment_color(db)

    def _lit_index(self) -> int:
        if not self._active or self._value_db is None:
            return -1
        span = max(self._max_db - self._min_db, 1e-9)
        ratio = (float(self._value_db) - self._min_db) / span
        ratio = max(0.0, min(1.0, ratio))
        return int(round(ratio * (self._segments - 1)))

    def _peak_index(self) -> int:
        if not self._active or self._peak_db is None:
            return -1
        span = max(self._max_db - self._min_db, 1e-9)
        ratio = (float(self._peak_db) - self._min_db) / span
        ratio = max(0.0, min(1.0, ratio))
        return int(round(ratio * (self._segments - 1)))

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        rect = self.rect().adjusted(0, 1, 0, -1)
        gap = 2
        seg_w = max(3, (rect.width() - gap * (self._segments - 1)) // self._segments)
        lit_idx = self._lit_index()
        peak_idx = self._peak_index()
        for i in range(self._segments):
            x = rect.left() + i * (seg_w + gap)
            seg_rect = QRect(x, rect.top(), seg_w, rect.height())
            db = self._min_db + (i / max(self._segments - 1, 1)) * (self._max_db - self._min_db)
            if not self._active:
                color = QColor(28, 32, 38)
            elif i <= lit_idx:
                color = self._segment_color(db)
            else:
                color = self._segment_color(db).darker(280)
            painter.fillRect(seg_rect, color)
            if self._active and i == peak_idx and i > lit_idx:
                painter.fillRect(seg_rect, self._segment_color(db).lighter(130))
            painter.setPen(QPen(QColor(8, 10, 12)))
            painter.drawRect(seg_rect)
        painter.end()


class LabeledCompactLedMeter(QFrame):
    """Etiqueta + barra LED + lectura numérica opcional."""

    def __init__(
        self,
        label: str,
        *,
        segments: int = 12,
        bar_height: int = 12,
        min_db: float = -54.0,
        max_db: float = 0.0,
        mode: str = "vu",
        value_suffix: str = "",
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self._label = QLabel(label)
        self._label.setFixedWidth(12)
        font = QFont("Consolas", 7, QFont.Weight.Bold)
        self._label.setFont(font)
        layout.addWidget(self._label)

        self._bar = CompactLedMeterBar(
            segments=segments,
            height=bar_height,
            min_db=min_db,
            max_db=max_db,
            mode=mode,
            parent=self,
        )
        layout.addWidget(self._bar, stretch=1)

        self._readout = QLabel("—")
        self._readout.setFont(QFont("Consolas", 7))
        self._readout.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._readout.setFixedWidth(44 if mode == "acp" else 52)
        self._value_suffix = value_suffix
        layout.addWidget(self._readout)

    def set_level(
        self,
        value_db: Optional[float],
        *,
        peak_db: Optional[float] = None,
        active: bool = True,
    ) -> None:
        self._bar.set_level(value_db, peak_db=peak_db, active=active)
        if not active or value_db is None:
            self._readout.setText("—")
        else:
            self._readout.setText(f"{float(value_db):.0f}{self._value_suffix}")