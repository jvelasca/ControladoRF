"""Menú de registro / exportación del Monitor."""
from __future__ import annotations

from typing import Callable, Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QMenu, QToolButton, QWidget

from core.monitor.monitor_export import TraceExportFormat
from gui.monitor.monitor_export_actions import (
    export_spectrum_csv_action,
    export_spectrum_png_action,
    export_waterfall_png_action,
)
from i18n.json_translation import tr


class MonitorExportMenuButton(QToolButton):
    """Botón desplegable — instantáneas y exportación CSV."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("MonitorToolbarExportBtn")
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        self.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.setMinimumSize(32, 28)
        self._host = None
        self._menu = QMenu(self)
        self.setMenu(self._menu)
        self._build_menu()

    def bind_host(self, host) -> None:
        self._host = host
        self._build_menu()

    def _build_menu(self) -> None:
        self._menu.clear()
        host = self._host
        parent = self.window()

        snap = self._menu.addMenu(tr("monitor_export_menu_snapshot"))
        self._add_action(
            snap,
            "monitor_export_png_screen",
            lambda: export_spectrum_png_action(host, parent) if host and parent else None,
            enabled=host is not None,
        )
        self._add_action(
            snap,
            "monitor_export_png_waterfall",
            lambda: export_waterfall_png_action(host, parent) if host and parent else None,
            enabled=host is not None,
        )

        data = self._menu.addMenu(tr("monitor_export_menu_data"))
        self._add_action(
            data,
            "monitor_export_csv_spectrum",
            lambda: export_spectrum_csv_action(host, parent) if host and parent else None,
            enabled=host is not None,
        )
        self._add_action(
            data,
            "monitor_export_csv_workbench",
            lambda: export_spectrum_csv_action(
                host,
                parent,
                export_format=TraceExportFormat.WORKBENCH,
            )
            if host and parent
            else None,
            enabled=host is not None,
            tooltip_key="monitor_export_csv_workbench_tip",
        )
        self._add_action(
            data,
            "monitor_export_csv_soundbase",
            lambda: export_spectrum_csv_action(
                host,
                parent,
                export_format=TraceExportFormat.SOUNDBASE,
            )
            if host and parent
            else None,
            enabled=host is not None,
            tooltip_key="monitor_export_csv_soundbase_tip",
        )
        self._add_disabled(data, "monitor_export_csv_markers")
        self._add_disabled(data, "monitor_export_csv_waterfall")

        rec = self._menu.addMenu(tr("monitor_export_menu_record"))
        self._add_disabled(rec, "monitor_export_record_iq")
        self._add_disabled(rec, "monitor_export_record_sweep")

    @staticmethod
    def _add_action(
        menu: QMenu,
        key: str,
        slot: Callable[[], None],
        *,
        enabled: bool = True,
        tooltip_key: str = "",
    ) -> None:
        act = menu.addAction(tr(key))
        act.setEnabled(enabled)
        if tooltip_key:
            act.setToolTip(tr(tooltip_key))
        if enabled:
            act.triggered.connect(slot)

    @staticmethod
    def _add_disabled(menu: QMenu, key: str) -> None:
        act = menu.addAction(tr(key))
        act.setEnabled(False)

    def recargar_textos(self) -> None:
        self.setToolTip(tr("monitor_tip_export_menu"))
        self._build_menu()

    def apply_icon(self, icon) -> None:
        self.setIcon(icon)
