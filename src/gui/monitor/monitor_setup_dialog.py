"""Diálogo asistente de instalación SDR."""
from __future__ import annotations

from typing import List, Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from core.monitor.sdr_catalog import get_device_spec, hardware_device_specs
from core.monitor.sdr_setup import DeviceSetupReport, get_platform_info, recommended_next_steps
from gui.dialog_styles import apply_professional_dialog_style, build_dialog_header
from i18n.json_translation import tr


class MonitorSetupDialog(QDialog):
    """Asistente modal con resumen por equipo y pasos de la plataforma actual."""

    def __init__(
        self,
        *,
        reports: List[DeviceSetupReport],
        focus_device_id: Optional[str] = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._reports = reports
        self._focus_device_id = focus_device_id or "hackrf"
        self.setWindowTitle(tr("monitor_setup_wizard_title"))
        apply_professional_dialog_style(self)
        self.resize(640, 520)
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        pinfo = get_platform_info()
        layout.addWidget(
            build_dialog_header(
                tr("monitor_setup_wizard_title"),
                tr("monitor_setup_wizard_subtitle").format(
                    platform=pinfo.platform_key,
                    py=pinfo.python_version,
                ),
            )
        )

        intro = QLabel(tr("monitor_setup_wizard_body"))
        intro.setWordWrap(True)
        layout.addWidget(intro)

        for spec in hardware_device_specs():
            report = next((r for r in self._reports if r.device_id == spec.device_id), None)
            if not report:
                continue
            title = spec.display_name
            if spec.is_default:
                title += f" ({tr('monitor_setup_default')})"
            block = QLabel(self._format_report(title, report))
            block.setWordWrap(True)
            block.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            if spec.device_id == self._focus_device_id:
                block.setStyleSheet("background: rgba(0,120,212,0.12); padding: 8px; border-radius: 4px;")
            layout.addWidget(block)

        layout.addWidget(QLabel(tr("monitor_setup_wizard_hint")))

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    @staticmethod
    def _format_report(title: str, report: DeviceSetupReport) -> str:
        lines = [
            f"▸ {title}",
            f"  USB: {report.usb.summary} — {report.usb.detail}",
            f"  CLI: {report.cli.summary} — {report.cli.detail}",
            f"  Lib: {report.native_lib.summary} — {report.native_lib.detail}",
            f"  Python: {report.python_backend.summary} — {report.python_backend.detail}",
        ]
        if report.ready_for_capture:
            lines.append(f"  {tr('monitor_setup_ready_yes')}")
        else:
            steps = recommended_next_steps(report)
            if steps:
                lines.append(f"  {tr('monitor_setup_steps_title')}:")
                for step in steps[:3]:
                    lines.append(f"    • {tr(step.title_key)}")
        return "\n".join(lines)
