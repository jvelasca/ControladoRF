"""Estilos LCD para toolbar Monitor (aspecto analizador R&S)."""
from __future__ import annotations

from PyQt6.QtWidgets import QFrame, QWidget

_LCD_QSS = """
#MonitorLcdReadout {
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #0c1824, stop:0.45 #081018, stop:1 #040a10);
    border: 1px solid #1e3a52;
    border-radius: 3px;
    min-width: 72px;
}
#MonitorLcdReadout:hover {
    border-color: #3a7ab8;
}
#MonitorLcdLabel {
    color: #5a8aaa;
    font-size: 9px;
    font-weight: 600;
    letter-spacing: 0.5px;
}
#MonitorLcdLabel[readoutMode="fc"] {
    color: #7ec8ff;
}
#MonitorLcdLabel[readoutMode="f"] {
    color: #ffc878;
}
#MonitorLcdValue {
    color: #8dff8d;
    font-size: 11px;
    font-weight: 600;
}
#MonitorLcdDateTime {
    color: #7ec8ff;
    font-size: 11px;
    font-weight: 600;
}
#MonitorGraticuleFrame {
    background-color: #121820;
    border: 1px solid #2a3540;
    border-radius: 2px;
}
#MonitorToolbarGroup {
    background-color: rgba(30, 35, 42, 0.6);
    border: 1px solid #3a4048;
    border-radius: 4px;
}
#MonitorToolbarGroupBtn {
    background-color: #2a3038;
    color: #d0d8e0;
    border: 1px solid #454d58;
    border-radius: 3px;
    padding: 4px 8px;
    font-weight: 600;
    font-size: 11px;
}
#MonitorToolbarGroupBtn:hover {
    background-color: #353d48;
    border-color: #0078d4;
}
#MonitorToolbarGroupBtn::menu-indicator {
    image: none;
    width: 0;
}
#MonitorToolbarTransportBtn {
    border-radius: 4px;
    padding: 6px 14px;
    font-weight: 700;
    font-size: 12px;
    border: 1px solid #3a6a40;
}
#MonitorToolbarTransportBtn[monitorState="idle"] {
    background-color: #1e5c28;
    color: #e8ffe8;
    border-color: #3ecf5a;
}
#MonitorToolbarTransportBtn[monitorState="idle"]:hover {
    background-color: #268034;
}
#MonitorToolbarTransportBtn[monitorState="running"] {
    background-color: #6a1e1e;
    color: #ffe8e8;
    border-color: #ef4444;
}
#MonitorToolbarTransportBtn[monitorState="running"]:hover {
    background-color: #802626;
}
#MonitorToolbarTransportBtn[monitorState="connecting"] {
    background-color: #5a4a18;
    color: #fff4cc;
    border-color: #d4a017;
}
#MonitorToolbarMode {
    background-color: rgba(22, 28, 36, 0.85);
    border: 1px solid #3a5060;
    border-radius: 6px;
    padding: 5px 6px;
}
#MonitorToolbarFreqGroup {
    background-color: rgba(24, 36, 44, 0.92);
    border: 1px solid #3a6878;
    border-radius: 6px;
}
#MonitorToolbarRfGroup {
    background-color: rgba(32, 38, 32, 0.92);
    border: 1px solid #4a6848;
    border-radius: 6px;
}
#MonitorToolbarMode QToolButton {
    background-color: #2a3038;
    color: #c8d0d8;
    border: 1px solid #454d58;
    border-radius: 4px;
    padding: 7px 18px;
    min-width: 92px;
    min-height: 28px;
    font-weight: 600;
    font-size: 11px;
}
#MonitorToolbarMode QToolButton:hover {
    background-color: #353d48;
    border-color: #5a8098;
}
#MonitorToolbarMode_spectrum:checked {
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #1a7038, stop:1 #0d5a28);
    color: #e8ffe8;
    border-color: #4ae878;
}
#MonitorToolbarMode_sdr:checked {
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #1a6090, stop:1 #0d4a7a);
    color: #e8f4ff;
    border-color: #4aa8e8;
}
#MonitorFreqReadout {
    min-width: 170px;
}
#MonitorNumericSpin {
    background-color: #081018;
    color: #8dff8d;
    border: 1px solid #1e3a52;
    border-radius: 2px;
    padding: 1px 4px;
    min-height: 22px;
    font-family: Consolas, monospace;
    font-size: 11px;
}
#MonitorNumericSpin[valueMode="auto"] {
    color: #9ec8e8;
    font-style: normal;
}
#MonitorNumericSpin[valueMode="manual"] {
    color: #ffd080;
    font-style: italic;
}
#MonitorNumericMenuBtn {
    background-color: #2a3038;
    color: #c8d0d8;
    border: 1px solid #454d58;
    border-radius: 2px;
    padding: 0 2px;
    font-weight: 700;
}
#MonitorNumericMenuBtn:hover {
    border-color: #0078d4;
    color: #ffffff;
}
#MonitorPreampBtn {
    background-color: #2a3038;
    color: #888;
    border: 1px solid #454d58;
    border-radius: 2px;
    padding: 0;
    font-weight: 700;
    font-size: 10px;
}
#MonitorPreampBtn:hover {
    border-color: #0078d4;
    color: #c8d0d8;
}
#MonitorPreampBtn:checked {
    background-color: #1a4a28;
    color: #8dff8d;
    border-color: #3ecf5a;
}
#MonitorPreampBtn:checked:hover {
    background-color: #268034;
}
#MonitorFreqModeBtn {
    background-color: #2a3038;
    border: 1px solid #454d58;
    border-radius: 2px;
    padding: 0;
}
#MonitorFreqModeBtn:hover {
    border-color: #0078d4;
}
#MonitorFreqModeBtn[readoutMode="fc"] {
    border-color: #3a7090;
}
#MonitorFreqModeBtn[readoutMode="f"] {
    border-color: #a07040;
    background-color: #3a2a18;
}
#MonitorToolbarBwGroup {
    background-color: rgba(28, 38, 52, 0.92);
    border: 1px solid #4a6888;
    border-radius: 6px;
}
#MonitorToolbarUtilsGroup {
    background-color: rgba(36, 34, 48, 0.92);
    border: 1px solid #6a5888;
    border-radius: 6px;
}
#MonitorToolbarTriggerBtn {
    background-color: #3a3050;
    color: #ecd8ff;
    border: 1px solid #8a70b0;
    border-radius: 4px;
    padding: 6px 10px;
    min-width: 72px;
    font-weight: 700;
    font-size: 11px;
}
#MonitorToolbarTriggerBtn:hover {
    background-color: #4a4068;
    border-color: #b090e0;
    color: #ffffff;
}
#MonitorToolbarTriggerBtn:disabled {
    background-color: #2a2838;
    color: #666;
    border-color: #444;
}
#MonitorToolbarCaptureBtn {
    background-color: #2a4560;
    color: #d8ecff;
    border: 1px solid #5a8ab0;
    border-radius: 4px;
    padding: 6px 12px;
    min-width: 88px;
    font-weight: 700;
    font-size: 11px;
}
#MonitorToolbarExportBtn {
    background-color: #2a4560;
    border: 1px solid #5a8ab0;
    border-radius: 4px;
    padding: 4px 6px;
    min-width: 32px;
    min-height: 28px;
}
#MonitorToolbarExportBtn:hover {
    background-color: #345878;
    border-color: #7ab8e8;
}
#MonitorToolbarExportBtn:pressed {
    background-color: #1a3850;
}
#MonitorToolbarExportBtn::menu-indicator {
    image: none;
    width: 0;
}
#MonitorToolbarCaptureBtn:hover {
    background-color: #345878;
    border-color: #7ab8e8;
    color: #ffffff;
}
#MonitorToolbarCaptureBtn:pressed {
    background-color: #1a3850;
}
"""


def apply_lcd_readout_style(widget: QFrame) -> None:
    widget.setStyleSheet(_LCD_QSS)


def apply_monitor_toolbar_chrome(widget: QWidget) -> None:
    existing = widget.styleSheet() or ""
    if _LCD_QSS not in existing:
        widget.setStyleSheet(existing + _LCD_QSS)
