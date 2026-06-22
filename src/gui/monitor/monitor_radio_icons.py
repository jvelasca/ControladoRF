"""Iconos compactos para la barra de herramientas RADIO."""
from __future__ import annotations

from PyQt6.QtGui import QBrush, QColor, QFont, QIcon, QPainter, QPen, QPixmap, QPolygonF
from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtWidgets import QWidget

from gui.monitor.monitor_supervision_icons import toolbar_icon_color

_ICON_PX = 18


def make_auto_tune_icon(widget: QWidget) -> QIcon:
    """Flecha circular / sintonía automática."""
    color = toolbar_icon_color(widget)
    px = _ICON_PX
    pixmap = QPixmap(px, px)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    pen = QPen(color, 1.4)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    margin = 2
    painter.drawArc(margin, margin, px - margin * 2, px - margin * 2, 45 * 16, 270 * 16)
    painter.drawLine(px - 4, 3, px - 2, 6)
    painter.drawLine(px - 4, 3, px - 7, 4)
    painter.end()
    return QIcon(pixmap)


def make_fm_broadcast_icon(widget: QWidget) -> QIcon:
    """Etiqueta FM compacta."""
    color = toolbar_icon_color(widget)
    px = _ICON_PX
    pixmap = QPixmap(px, px)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QBrush(QColor(color.red(), color.green(), color.blue(), 48)))
    painter.drawRoundedRect(0, 2, px, px - 4, 2, 2)
    painter.setPen(QPen(color, 1.0))
    font = QFont("Segoe UI", 6, QFont.Weight.Bold)
    painter.setFont(font)
    painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "FM")
    painter.end()
    return QIcon(pixmap)


def make_stereo_icon(widget: QWidget) -> QIcon:
    """Dos canales L/R."""
    color = toolbar_icon_color(widget)
    px = _ICON_PX
    pixmap = QPixmap(px, px)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    pen = QPen(color, 1.2)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    mid = px // 2
    painter.drawEllipse(2, 4, mid - 3, px - 8)
    painter.drawEllipse(mid + 1, 4, mid - 3, px - 8)
    painter.end()
    return QIcon(pixmap)


def make_rds_icon(widget: QWidget) -> QIcon:
    """Etiqueta RDS."""
    color = toolbar_icon_color(widget)
    px = _ICON_PX
    pixmap = QPixmap(px, px)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setPen(QPen(color, 1.0))
    font = QFont("Segoe UI", 5, QFont.Weight.Bold)
    painter.setFont(font)
    painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "RDS")
    painter.end()
    return QIcon(pixmap)


def make_demod_bw_icon(widget: QWidget) -> QIcon:
    """Banda verde de ancho demodulado."""
    color = toolbar_icon_color(widget)
    px = _ICON_PX
    pixmap = QPixmap(px, px)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setPen(QPen(color, 1.0))
    painter.setBrush(QBrush(QColor(80, 210, 140, 90)))
    painter.drawRect(2, 5, px - 4, px - 10)
    painter.setPen(QPen(color, 1.0, Qt.PenStyle.DashLine))
    painter.drawLine(2, px // 2, px - 2, px // 2)
    painter.end()
    return QIcon(pixmap)


def make_lowpass_icon(widget: QWidget) -> QIcon:
    """Icono LPF."""
    color = toolbar_icon_color(widget)
    px = _ICON_PX
    pixmap = QPixmap(px, px)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setPen(QPen(color, 1.0))
    painter.setFont(QFont("Segoe UI", 6, QFont.Weight.Bold))
    painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "LP")
    painter.end()
    return QIcon(pixmap)


def make_iq_correction_icon(widget: QWidget) -> QIcon:
    """Icono IQ correction."""
    color = toolbar_icon_color(widget)
    px = _ICON_PX
    pixmap = QPixmap(px, px)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setPen(QPen(color, 1.0))
    painter.setFont(QFont("Segoe UI", 5, QFont.Weight.Bold))
    painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "IQ")
    painter.drawLine(2, px - 4, px - 2, px - 4)
    painter.end()
    return QIcon(pixmap)


def make_iq_invert_icon(widget: QWidget) -> QIcon:
    """Icono inversión IQ."""
    color = toolbar_icon_color(widget)
    px = _ICON_PX
    pixmap = QPixmap(px, px)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setPen(QPen(color, 1.2))
    painter.drawLine(3, px - 3, px - 3, 3)
    painter.drawLine(px - 6, 3, px - 3, 3)
    painter.drawLine(px - 3, 3, px - 3, 6)
    painter.end()
    return QIcon(pixmap)


def make_bias_tee_icon(widget: QWidget) -> QIcon:
    """Icono Bias-T."""
    color = toolbar_icon_color(widget)
    px = _ICON_PX
    pixmap = QPixmap(px, px)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setPen(QPen(color, 1.0))
    painter.setFont(QFont("Segoe UI", 5, QFont.Weight.Bold))
    painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "BT")
    painter.end()
    return QIcon(pixmap)


def make_audio_mute_icon(widget: QWidget, *, muted: bool = False) -> QIcon:
    """Altavoz; tachado si muted."""
    color = toolbar_icon_color(widget)
    px = _ICON_PX
    pixmap = QPixmap(px, px)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    pen = QPen(color, 1.3)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    # Cono + base
    painter.drawPolygon(
        QPolygonF(
            [
                QPointF(3, 6),
                QPointF(7, 6),
                QPointF(12, 3),
                QPointF(12, 15),
                QPointF(7, 12),
                QPointF(3, 12),
            ]
        )
    )
    painter.drawRect(13, 8, 2, 4)
    if muted:
        pen.setWidthF(1.6)
        painter.setPen(pen)
        painter.drawLine(2, 15, 16, 3)
    painter.end()
    return QIcon(pixmap)


def make_squelch_icon(widget: QWidget, *, enabled: bool = True) -> QIcon:
    """SQ con indicador; tachado si desactivado."""
    color = toolbar_icon_color(widget)
    px = _ICON_PX
    pixmap = QPixmap(px, px)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    pen = QPen(color, 1.2)
    painter.setPen(pen)
    font = painter.font()
    font.setBold(True)
    font.setPointSize(7)
    painter.setFont(font)
    painter.drawText(2, 13, "SQ")
    if not enabled:
        pen.setWidthF(1.6)
        painter.setPen(pen)
        painter.drawLine(2, 15, 16, 3)
    painter.end()
    return QIcon(pixmap)
