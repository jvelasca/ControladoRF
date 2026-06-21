"""Acciones GUI de exportación del Monitor."""
from __future__ import annotations

from typing import Optional, Protocol

from PyQt6.QtWidgets import QFileDialog, QMessageBox, QWidget

from core.monitor.monitor_export import (
    MonitorExportError,
    TraceExportFormat,
    default_export_filename,
    rf_tool_scan_filename,
)
from core.monitor.monitor_export_paths import (
    EXPORT_PNG_SPECTRUM,
    EXPORT_PNG_WATERFALL,
    EXPORT_TRACE_CSV,
    EXPORT_TRACE_CSV_SOUNDBASE,
    EXPORT_TRACE_CSV_WORKBENCH,
    remember_save_path,
    resolve_save_path,
)
from i18n.json_translation import tr


class MonitorExportHost(Protocol):
    def get_params(self): ...

    def get_last_frame(self): ...

    def export_spectrum_csv(
        self,
        path: str,
        *,
        export_format: TraceExportFormat | str = TraceExportFormat.CONTROLADORF,
    ) -> tuple[bool, str]: ...

    def export_widget_png(self, widget, path: str) -> tuple[bool, str]: ...

    def get_spectrum_widget(self): ...

    def get_waterfall_widget(self): ...


def _save_path(
    parent: QWidget,
    *,
    export_type: str,
    title_key: str,
    filter_key: str,
    default_name: str,
) -> Optional[str]:
    initial = resolve_save_path(export_type, default_name)
    path, _filter = QFileDialog.getSaveFileName(
        parent,
        tr(title_key),
        initial,
        tr(filter_key),
    )
    if not path:
        return None
    return path


def export_spectrum_csv_action(
    host: MonitorExportHost,
    parent: QWidget,
    *,
    export_format: TraceExportFormat = TraceExportFormat.CONTROLADORF,
) -> None:
    frame = host.get_last_frame()
    if frame is None:
        QMessageBox.information(parent, tr("monitor_export_title"), tr("monitor_export_no_trace"))
        return

    if export_format is TraceExportFormat.WORKBENCH:
        default = rf_tool_scan_filename(frame)
        export_type = EXPORT_TRACE_CSV_WORKBENCH
        title_key = "monitor_export_csv_workbench_title"
    elif export_format is TraceExportFormat.SOUNDBASE:
        default = rf_tool_scan_filename(frame)
        export_type = EXPORT_TRACE_CSV_SOUNDBASE
        title_key = "monitor_export_csv_soundbase_title"
    else:
        default = default_export_filename("trace", extension="csv")
        export_type = EXPORT_TRACE_CSV
        title_key = "monitor_export_csv_title"

    path = _save_path(
        parent,
        export_type=export_type,
        title_key=title_key,
        filter_key="monitor_export_filter_csv",
        default_name=default,
    )
    if path is None:
        return

    ok, msg = host.export_spectrum_csv(path, export_format=export_format)
    if ok:
        remember_save_path(export_type, path)
    _show_result(parent, ok, msg)


def export_spectrum_png_action(host: MonitorExportHost, parent: QWidget) -> None:
    widget = host.get_spectrum_widget()
    default = default_export_filename("spectrum", extension="png")
    path = _save_path(
        parent,
        export_type=EXPORT_PNG_SPECTRUM,
        title_key="monitor_export_png_spectrum_title",
        filter_key="monitor_export_filter_png",
        default_name=default,
    )
    if path is None:
        return
    ok, msg = host.export_widget_png(widget, path)
    if ok:
        remember_save_path(EXPORT_PNG_SPECTRUM, path)
    _show_result(parent, ok, msg)


def export_waterfall_png_action(host: MonitorExportHost, parent: QWidget) -> None:
    widget = host.get_waterfall_widget()
    default = default_export_filename("waterfall", extension="png")
    path = _save_path(
        parent,
        export_type=EXPORT_PNG_WATERFALL,
        title_key="monitor_export_png_waterfall_title",
        filter_key="monitor_export_filter_png",
        default_name=default,
    )
    if path is None:
        return
    ok, msg = host.export_widget_png(widget, path)
    if ok:
        remember_save_path(EXPORT_PNG_WATERFALL, path)
    _show_result(parent, ok, msg)


def _show_result(parent: QWidget, ok: bool, message: str) -> None:
    if ok:
        QMessageBox.information(parent, tr("monitor_export_done_title"), message)
    else:
        QMessageBox.warning(parent, tr("monitor_export_error_title"), message)
