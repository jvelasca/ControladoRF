"""Asistente de instalación/conexión SDR en panel FUENTE."""

from __future__ import annotations



from typing import List, Optional



from PyQt6.QtCore import Qt, pyqtSignal

from PyQt6.QtGui import QFont

from PyQt6.QtWidgets import (

    QApplication,

    QComboBox,

    QFormLayout,

    QFrame,

    QLabel,

    QPushButton,

    QSizePolicy,

    QTextEdit,

    QVBoxLayout,

    QWidget,

)



from core.monitor.sdr_catalog import SdrDeviceSpec, get_device_spec, hardware_device_specs

from core.monitor.sdr_setup import DeviceSetupReport, get_platform_info, recommended_next_steps

from i18n.json_translation import tr





class MonitorSourceSetupWidget(QWidget):

    """Estado USB/driver/backend + pasos de instalación por plataforma."""



    open_wizard_requested = pyqtSignal(str)

    recheck_requested = pyqtSignal(bool)



    def __init__(self, parent: Optional[QWidget] = None) -> None:

        super().__init__(parent)

        self._reports: List[DeviceSetupReport] = []

        self._platform = get_platform_info()

        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self._build()



    def _build(self) -> None:

        layout = QVBoxLayout(self)

        layout.setContentsMargins(0, 6, 0, 0)

        layout.setSpacing(6)



        header = QLabel(tr("monitor_setup_intro"))

        header.setWordWrap(True)

        header.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        layout.addWidget(header)



        platform_line = QLabel(

            tr("monitor_setup_platform").format(

                os=self._platform.system,

                arch=self._platform.machine,

                py=self._platform.python_version,

            )

        )

        platform_line.setWordWrap(True)

        platform_line.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        platform_line.setStyleSheet("color: #858585; font-size: 11px;")

        layout.addWidget(platform_line)



        self._family_combo = QComboBox()

        self._family_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self._family_combo.setMinimumContentsLength(12)

        for spec in hardware_device_specs():

            label = spec.display_name

            if spec.is_default:

                label += f" ({tr('monitor_setup_default')})"

            self._family_combo.addItem(label, spec.device_id)

        self._family_combo.currentIndexChanged.connect(self._refresh_detail)

        layout.addWidget(self._family_combo)



        self._status_frame = QFrame()

        self._status_frame.setFrameShape(QFrame.Shape.StyledPanel)

        self._status_frame.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        status_layout = QFormLayout(self._status_frame)

        status_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        status_layout.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)

        status_layout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)

        status_layout.setContentsMargins(8, 8, 8, 8)

        self._usb_label = QLabel("—")

        self._cli_label = QLabel("—")

        self._lib_label = QLabel("—")

        self._py_label = QLabel("—")

        self._ready_label = QLabel("—")

        for label in (self._usb_label, self._cli_label, self._lib_label, self._py_label, self._ready_label):

            label.setWordWrap(True)

            label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

            mono = QFont("Consolas", 9)

            mono.setStyleHint(QFont.StyleHint.Monospace)

            label.setFont(mono)

        status_layout.addRow(tr("monitor_setup_check_usb"), self._usb_label)

        status_layout.addRow(tr("monitor_setup_check_cli"), self._cli_label)

        status_layout.addRow(tr("monitor_setup_check_lib"), self._lib_label)

        status_layout.addRow(tr("monitor_setup_check_python"), self._py_label)

        status_layout.addRow(tr("monitor_setup_check_ready"), self._ready_label)

        layout.addWidget(self._status_frame)



        self._steps_title = QLabel(tr("monitor_setup_steps_title"))

        self._steps_title.setWordWrap(True)

        layout.addWidget(self._steps_title)

        self._steps_text = QTextEdit()

        self._steps_text.setReadOnly(True)

        self._steps_text.setMinimumHeight(100)

        self._steps_text.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)

        self._steps_text.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        layout.addWidget(self._steps_text, stretch=1)



        self._recheck_btn = QPushButton(tr("monitor_setup_recheck"))

        self._copy_btn = QPushButton(tr("monitor_setup_copy_cmd"))

        self._wizard_btn = QPushButton(tr("monitor_setup_open_wizard"))

        for button in (self._recheck_btn, self._copy_btn, self._wizard_btn):

            button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self._recheck_btn.clicked.connect(lambda: self.recheck_requested.emit(True))

        self._copy_btn.clicked.connect(self._copy_first_command)

        self._wizard_btn.clicked.connect(self._open_wizard)

        layout.addWidget(self._recheck_btn)

        layout.addWidget(self._copy_btn)

        layout.addWidget(self._wizard_btn)



    def set_reports(self, reports: List[DeviceSetupReport]) -> None:

        self._reports = reports

        self._refresh_detail()



    def _current_spec(self) -> Optional[SdrDeviceSpec]:

        device_id = self._family_combo.currentData()

        return get_device_spec(str(device_id)) if device_id else None



    def _report_for(self, device_id: str) -> Optional[DeviceSetupReport]:

        for report in self._reports:

            if report.device_id == device_id:

                return report

        return None



    def _status_line(self, result) -> str:

        flag = "OK" if result.ok else "—"

        detail = result.detail or result.summary

        return f"[{flag}] {result.summary}" + (f" — {detail}" if detail else "")



    def _refresh_detail(self) -> None:

        spec = self._current_spec()

        if not spec:

            return

        report = self._report_for(spec.device_id)

        if not report:

            self._usb_label.setText("—")

            self._cli_label.setText("—")

            self._lib_label.setText("—")

            self._py_label.setText("—")

            self._ready_label.setText(tr("monitor_setup_pending_scan"))

            self._steps_text.setPlainText("")

            return



        self._usb_label.setText(self._status_line(report.usb))

        self._cli_label.setText(self._status_line(report.cli))

        self._lib_label.setText(self._status_line(report.native_lib))

        self._py_label.setText(self._status_line(report.python_backend))

        if report.ready_for_capture:

            self._ready_label.setText(tr("monitor_setup_ready_yes"))

        else:

            self._ready_label.setText(tr("monitor_setup_ready_no"))



        steps = recommended_next_steps(report)

        if not steps:

            self._steps_text.setPlainText(tr("monitor_setup_no_steps_needed"))

            return

        lines = []

        for index, step in enumerate(steps, start=1):

            title = tr(step.title_key)

            detail = tr(step.detail_key)

            cmd = tr(step.command_key) if step.command_key else ""

            lines.append(f"{index}. {title}\n{detail}")

            if cmd:

                lines.append(f"   $ {cmd}")

            if step.doc_url:

                lines.append(f"   {step.doc_url}")

            lines.append("")

        self._steps_text.setPlainText("\n".join(lines).strip())



    def _copy_first_command(self) -> None:

        spec = self._current_spec()

        if not spec:

            return

        report = self._report_for(spec.device_id)

        if not report:

            return

        steps = recommended_next_steps(report)

        for step in steps:

            cmd = tr(step.command_key) if step.command_key else ""

            if cmd:

                QApplication.clipboard().setText(cmd)

                return



    def _open_wizard(self) -> None:

        device_id = self._family_combo.currentData()

        if device_id:

            self.open_wizard_requested.emit(str(device_id))



    def recargar_textos(self) -> None:

        self._refresh_detail()


