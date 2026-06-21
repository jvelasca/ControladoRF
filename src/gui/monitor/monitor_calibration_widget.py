"""Asistente DEBUG: calibración guiada — panel amplio + lanzador compacto."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Callable

from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from core.monitor.calibration.calibration_checklist import CALIBRATION_STEPS, apply_step
from core.monitor.calibration.step_analyzer import (
    StepAnalysis,
    analyze_step,
    evaluate_record_coherence,
)
from core.monitor.calibration.wizard_session import new_session, record_step, save_session
from core.monitor.spectrum_params import SpectrumParams
from i18n.json_translation import tr

_LOG_DIR = Path(__file__).resolve().parents[3] / "logs" / "calibration"

_VERDICT_ICON = {
    "pending": "○",
    "pass": "✓",
    "fail": "✗",
    "skip": "—",
}


class _OfflineMatrixWorker(QThread):
    line = pyqtSignal(str)
    finished_ok = pyqtSignal(bool)

    def run(self) -> None:
        from app_paths import is_frozen
        from i18n.json_translation import tr

        if is_frozen():
            self.line.emit(tr("cal_offline_unavailable_packaged"))
            self.finished_ok.emit(False)
            return
        root = Path(__file__).resolve().parents[3]
        script = root / "scripts" / "run_monitor_calibration.py"
        try:
            from utils.subprocess_platform import no_window_kwargs

            proc = subprocess.run(
                [sys.executable, str(script), "--quick"],
                cwd=str(root),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                **no_window_kwargs(),
            )
            for line in (proc.stdout or "").splitlines():
                self.line.emit(line)
            self.finished_ok.emit(proc.returncode == 0)
        except Exception as exc:
            self.line.emit(str(exc))
            self.finished_ok.emit(False)


class MonitorCalibrationPanel(QWidget):
    """Panel completo del checklist — pensado para ventana amplia."""

    calibration_step_requested = pyqtSignal(object)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._get_params: Callable[[], SpectrumParams] | None = None
        self._is_running: Callable[[], bool] | None = None
        self._index = 0
        self._session = new_session()
        self._verdicts: dict[str, str] = {s.id: "pending" for s in CALIBRATION_STEPS}
        self._draft_comments: dict[str, str] = {}
        self._last_analysis: StepAnalysis | None = None
        self._base_before_apply: SpectrumParams | None = None
        self._matrix_worker: _OfflineMatrixWorker | None = None
        self._build_ui()
        self._populate_list()
        self._show_step(0)

    def _build_ui(self) -> None:
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(8)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        root.addWidget(splitter)

        # —— Columna izquierda: checklist ——
        left = QWidget()
        left.setMinimumWidth(260)
        left.setMaximumWidth(360)
        left_lay = QVBoxLayout(left)
        left_lay.setContentsMargins(0, 0, 4, 0)
        left_lay.setSpacing(6)

        intro = QLabel(tr("cal_wizard_intro_short"))
        intro.setWordWrap(True)
        left_lay.addWidget(intro)

        self._progress = QLabel()
        left_lay.addWidget(self._progress)

        self._step_list = QListWidget()
        self._step_list.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        self._step_list.currentRowChanged.connect(self._on_list_row)
        left_lay.addWidget(self._step_list, stretch=1)

        self._summary = QLabel()
        self._summary.setWordWrap(True)
        self._summary.setObjectName("MonitorCalSummary")
        left_lay.addWidget(self._summary)
        self._update_summary()

        splitter.addWidget(left)

        # —— Columna derecha: paso + backend + comentario ——
        right = QWidget()
        right_lay = QVBoxLayout(right)
        right_lay.setContentsMargins(4, 0, 0, 0)
        right_lay.setSpacing(8)

        detail = QFrame()
        detail.setFrameShape(QFrame.Shape.StyledPanel)
        dlay = QVBoxLayout(detail)
        dlay.setContentsMargins(10, 10, 10, 10)
        self._title = QLabel()
        self._title.setWordWrap(True)
        font = self._title.font()
        font.setBold(True)
        font.setPointSize(font.pointSize() + 1)
        self._title.setFont(font)
        self._body = QLabel()
        self._body.setWordWrap(True)
        self._observe = QLabel()
        self._observe.setWordWrap(True)
        self._observe.setObjectName("MonitorCalObserve")
        dlay.addWidget(self._title)
        dlay.addWidget(self._body)
        dlay.addWidget(self._observe)
        right_lay.addWidget(detail)

        self._backend_verdict = QLabel()
        self._backend_verdict.setObjectName("MonitorCalBackendVerdict")
        right_lay.addWidget(self._backend_verdict)

        editor_split = QSplitter(Qt.Orientation.Vertical)
        editor_split.setChildrenCollapsible(False)

        backend_wrap = QWidget()
        bw_lay = QVBoxLayout(backend_wrap)
        bw_lay.setContentsMargins(0, 0, 0, 0)
        bw_lay.addWidget(QLabel(tr("cal_wizard_backend_label")))
        self._backend = QPlainTextEdit()
        self._backend.setReadOnly(True)
        self._backend.setMaximumBlockCount(500)
        self._backend.setMinimumHeight(140)
        self._backend.setPlaceholderText(tr("cal_wizard_backend_placeholder"))
        bw_lay.addWidget(self._backend)
        editor_split.addWidget(backend_wrap)

        comment_wrap = QWidget()
        cw_lay = QVBoxLayout(comment_wrap)
        cw_lay.setContentsMargins(0, 0, 0, 0)
        cw_lay.addWidget(QLabel(tr("cal_wizard_comment_label")))
        self._comment = QPlainTextEdit()
        self._comment.setPlaceholderText(tr("cal_wizard_comment_placeholder"))
        self._comment.setMinimumHeight(120)
        self._comment.setMaximumBlockCount(120)
        cw_lay.addWidget(self._comment)
        editor_split.addWidget(comment_wrap)

        editor_split.setStretchFactor(0, 3)
        editor_split.setStretchFactor(1, 2)
        right_lay.addWidget(editor_split, stretch=1)

        self._coherence = QLabel()
        self._coherence.setWordWrap(True)
        self._coherence.setObjectName("MonitorCalCoherence")
        right_lay.addWidget(self._coherence)

        row_apply = QHBoxLayout()
        self._apply_btn = QPushButton(tr("cal_wizard_apply"))
        self._apply_btn.clicked.connect(self._on_apply)
        self._reanalyze_btn = QPushButton(tr("cal_wizard_reanalyze"))
        self._reanalyze_btn.clicked.connect(self._refresh_backend)
        row_apply.addWidget(self._apply_btn)
        row_apply.addWidget(self._reanalyze_btn)
        row_apply.addStretch(1)
        right_lay.addLayout(row_apply)

        row_verdict = QHBoxLayout()
        self._ok_btn = QPushButton(tr("cal_wizard_ok"))
        self._fail_btn = QPushButton(tr("cal_wizard_fail"))
        self._skip_btn = QPushButton(tr("cal_wizard_skip"))
        self._ok_btn.clicked.connect(lambda: self._record_verdict("pass"))
        self._fail_btn.clicked.connect(lambda: self._record_verdict("fail"))
        self._skip_btn.clicked.connect(lambda: self._record_verdict("skip"))
        row_verdict.addWidget(self._ok_btn)
        row_verdict.addWidget(self._fail_btn)
        row_verdict.addWidget(self._skip_btn)
        row_verdict.addStretch(1)
        self._matrix_btn = QPushButton(tr("cal_wizard_matrix_quick"))
        self._matrix_btn.clicked.connect(self._run_offline_matrix)
        row_verdict.addWidget(self._matrix_btn)
        right_lay.addLayout(row_verdict)

        row_nav = QHBoxLayout()
        self._prev_btn = QPushButton(tr("cal_wizard_prev"))
        self._next_btn = QPushButton(tr("cal_wizard_next"))
        self._prev_btn.clicked.connect(self._go_prev)
        self._next_btn.clicked.connect(self._go_next)
        row_nav.addWidget(self._prev_btn)
        row_nav.addWidget(self._next_btn)
        row_nav.addStretch(1)
        right_lay.addLayout(row_nav)

        self._status = QLabel()
        self._status.setWordWrap(True)
        right_lay.addWidget(self._status)

        splitter.addWidget(right)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([300, 700])

    def bind_controller(
        self,
        get_params: Callable[[], SpectrumParams],
        is_running: Callable[[], bool],
    ) -> None:
        self._get_params = get_params
        self._is_running = is_running
        self._show_step(self._index)

    def save_draft(self) -> None:
        self._save_comment_draft()

    def session_summary_text(self) -> str:
        return tr("cal_wizard_launcher_summary").format(
            pass_n=self._session.passed_count,
            fail_n=self._session.failed_count,
            total=len(CALIBRATION_STEPS),
        )

    def _update_summary(self) -> None:
        self._summary.setText(self.session_summary_text())

    def _current_step(self):
        return CALIBRATION_STEPS[self._index]

    def _step_comment_draft(self, step_id: str) -> str:
        rec = self._session.records.get(step_id)
        if rec and rec.user_comment:
            return rec.user_comment
        return self._draft_comments.get(step_id, "")

    def _save_comment_draft(self) -> None:
        step = self._current_step()
        self._draft_comments[step.id] = self._comment.toPlainText()

    def _populate_list(self) -> None:
        self._step_list.blockSignals(True)
        self._step_list.clear()
        for i, step in enumerate(CALIBRATION_STEPS):
            icon = _VERDICT_ICON.get(self._verdicts.get(step.id, "pending"), "○")
            rec = self._session.records.get(step.id)
            note_mark = " 💬" if rec and rec.user_comment else ""
            item = QListWidgetItem(f"{icon} {i + 1}. {tr(step.title_key)}{note_mark}")
            item.setData(Qt.ItemDataRole.UserRole, i)
            self._step_list.addItem(item)
        self._step_list.blockSignals(False)

    def _set_backend_verdict_label(self, analysis: StepAnalysis | None) -> None:
        if analysis is None:
            self._backend_verdict.setText(tr("cal_wizard_backend_pending"))
            return
        key = "cal_wizard_backend_pass" if analysis.backend_passed else "cal_wizard_backend_fail"
        self._backend_verdict.setText(tr(key))

    def _show_step(self, index: int) -> None:
        self._save_comment_draft()
        index = max(0, min(index, len(CALIBRATION_STEPS) - 1))
        self._index = index
        step = self._current_step()
        self._step_list.setCurrentRow(index)
        self._progress.setText(
            tr("cal_wizard_progress").format(
                current=index + 1,
                total=len(CALIBRATION_STEPS),
                phase=tr(step.phase_key),
            )
        )
        self._title.setText(tr(step.title_key))
        self._body.setText(tr(step.body_key))
        self._observe.setText(tr("cal_wizard_observe_prefix") + " " + tr(step.observe_key))

        rec = self._session.records.get(step.id)
        self._comment.setPlainText(self._step_comment_draft(step.id))
        self._coherence.clear()

        if rec and rec.backend_analysis:
            self._last_analysis = None
            self._backend.setPlainText(self._format_saved_analysis(rec.backend_analysis))
            self._set_backend_verdict_label_from_dict(rec.backend_analysis)
            if rec.coherence.get("issues"):
                self._coherence.setText("⚠ " + " | ".join(rec.coherence["issues"]))
        else:
            self._backend.clear()
            self._last_analysis = None
            self._set_backend_verdict_label(None)

        self._prev_btn.setEnabled(index > 0)
        self._next_btn.setEnabled(index < len(CALIBRATION_STEPS) - 1)
        play_ok = not step.requires_play or (self._is_running() if self._is_running else False)
        self._apply_btn.setEnabled(self._get_params is not None and play_ok)
        self._reanalyze_btn.setEnabled(self._get_params is not None)
        if step.requires_play and not play_ok:
            self._status.setText(tr("cal_wizard_need_play"))
        else:
            self._status.setText("")

    @staticmethod
    def _format_saved_analysis(data: dict) -> str:
        lines = []
        if data.get("actual"):
            act = data["actual"]
            lines.append(
                f"modo={act.get('capture_mode')} SPAN={act.get('span_mhz', 0):.2f} MHz "
                f"RBW={act.get('rbw_khz', 0):.1f} kHz FFT={act.get('fft_size')}"
            )
        for key in ("mismatches", "failed_checks", "hints", "diagnosis"):
            items = data.get(key) or []
            if items:
                lines.append(f"— {key} —")
                for item in items:
                    if isinstance(item, dict):
                        lines.append(f"✗ {item.get('name')}: {item.get('detail')}")
                    else:
                        lines.append(str(item))
        return "\n".join(lines)

    def _set_backend_verdict_label_from_dict(self, data: dict) -> None:
        passed = data.get("backend_passed")
        if passed is True:
            self._backend_verdict.setText(tr("cal_wizard_backend_pass"))
        elif passed is False:
            self._backend_verdict.setText(tr("cal_wizard_backend_fail"))
        else:
            self._set_backend_verdict_label(None)

    def _on_list_row(self, row: int) -> None:
        if row >= 0:
            self._show_step(row)

    def _go_prev(self) -> None:
        self._show_step(self._index - 1)

    def _go_next(self) -> None:
        self._show_step(self._index + 1)

    def _on_apply(self) -> None:
        if self._get_params is None:
            return
        step = self._current_step()
        self._base_before_apply = self._get_params().copy()
        try:
            updated = apply_step(step, self._base_before_apply)
        except Exception as exc:
            self._backend.setPlainText(f"ERROR apply: {exc}")
            return
        self.calibration_step_requested.emit(updated)
        QTimer.singleShot(700, self._refresh_backend)

    def _refresh_backend(self) -> None:
        if self._get_params is None:
            return
        step = self._current_step()
        params = self._get_params()
        self._last_analysis = analyze_step(
            step,
            params,
            base_before_apply=self._base_before_apply,
        )
        self._backend.setPlainText("\n".join(self._last_analysis.summary_lines()))
        self._set_backend_verdict_label(self._last_analysis)
        if not self._last_analysis.backend_passed and not self._comment.toPlainText().strip():
            self._comment.setPlaceholderText(tr("cal_wizard_comment_required_hint"))

    def _record_verdict(self, verdict: str) -> None:
        step = self._current_step()
        comment = self._comment.toPlainText().strip()

        if verdict == "fail" and not comment:
            self._status.setText(tr("cal_wizard_comment_required"))
            self._comment.setFocus()
            return

        if self._last_analysis is None:
            self._refresh_backend()

        analysis = self._last_analysis
        backend_passed = analysis.backend_passed if analysis else None
        coherence = evaluate_record_coherence(
            user_verdict=verdict,
            backend_passed=backend_passed,
            user_comment=comment,
        )

        if coherence.get("issues"):
            self._coherence.setText("⚠ " + " | ".join(coherence["issues"]))

        analysis_dict = analysis.to_snapshot() if analysis else {}
        record_step(
            self._session,
            step_id=step.id,
            index=self._index,
            title=tr(step.title_key),
            user_verdict=verdict,
            backend_passed=backend_passed,
            backend_analysis=analysis_dict,
            user_comment=comment,
            coherence=coherence,
        )
        self._verdicts[step.id] = verdict
        self._draft_comments[step.id] = comment
        _, md_path = save_session(self._session, _LOG_DIR)
        self._populate_list()
        self._step_list.setCurrentRow(self._index)
        self._update_summary()

        if verdict == "pass":
            self._status.setText(tr("cal_wizard_step_pass"))
        elif verdict == "fail":
            self._status.setText(tr("cal_wizard_step_fail_saved").format(path=md_path.name))
        else:
            self._status.setText(tr("cal_wizard_step_skip"))

        if verdict in ("pass", "skip") and self._index < len(CALIBRATION_STEPS) - 1:
            QTimer.singleShot(500, lambda: self._show_step(self._index + 1))
        elif self._index == len(CALIBRATION_STEPS) - 1:
            from datetime import datetime, timezone

            self._session.finished_at = datetime.now(timezone.utc).isoformat()
            _, md_path = save_session(self._session, _LOG_DIR)
            self._status.setText(
                tr("cal_wizard_complete").format(
                    pass_n=self._session.passed_count,
                    fail_n=self._session.failed_count,
                )
                + f" → {md_path.name}"
            )

    def _run_offline_matrix(self) -> None:
        if self._matrix_worker is not None and self._matrix_worker.isRunning():
            return
        self._backend.clear()
        self._matrix_worker = _OfflineMatrixWorker(self)
        self._matrix_worker.line.connect(self._backend.appendPlainText)
        self._matrix_worker.finished_ok.connect(self._on_matrix_done)
        self._matrix_btn.setEnabled(False)
        self._matrix_worker.start()

    def _on_matrix_done(self, ok: bool) -> None:
        self._matrix_btn.setEnabled(True)
        self._status.setText(
            tr("cal_wizard_matrix_ok") if ok else tr("cal_wizard_matrix_fail")
        )

    def recargar_textos(self) -> None:
        self._populate_list()
        self._show_step(self._index)
        self._update_summary()
        self._apply_btn.setText(tr("cal_wizard_apply"))
        self._reanalyze_btn.setText(tr("cal_wizard_reanalyze"))
        self._ok_btn.setText(tr("cal_wizard_ok"))
        self._fail_btn.setText(tr("cal_wizard_fail"))
        self._skip_btn.setText(tr("cal_wizard_skip"))
        self._prev_btn.setText(tr("cal_wizard_prev"))
        self._next_btn.setText(tr("cal_wizard_next"))
        self._matrix_btn.setText(tr("cal_wizard_matrix_quick"))


class MonitorCalibrationWidget(QWidget):
    """Lanzador compacto en el panel DEBUG — abre ventana amplia."""

    calibration_step_requested = pyqtSignal(object)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._panel = MonitorCalibrationPanel()
        self._panel.calibration_step_requested.connect(self.calibration_step_requested.emit)
        self._dialog = None
        self._get_params: Callable[[], SpectrumParams] | None = None
        self._is_running: Callable[[], bool] | None = None

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)

        hint = QLabel(tr("cal_wizard_launcher_hint"))
        hint.setWordWrap(True)
        lay.addWidget(hint)

        self._summary = QLabel()
        self._summary.setWordWrap(True)
        lay.addWidget(self._summary)

        self._open_btn = QPushButton(tr("cal_wizard_open_window"))
        self._open_btn.setMinimumHeight(36)
        self._open_btn.clicked.connect(self._open_window)
        lay.addWidget(self._open_btn)

        lay.addStretch(1)
        self._refresh_summary()

    def bind_controller(
        self,
        get_params: Callable[[], SpectrumParams],
        is_running: Callable[[], bool],
    ) -> None:
        self._get_params = get_params
        self._is_running = is_running
        self._panel.bind_controller(get_params, is_running)

    def _ensure_dialog(self):
        from gui.monitor.monitor_calibration_dialog import MonitorCalibrationDialog

        if self._dialog is None:
            parent = self.window()
            self._dialog = MonitorCalibrationDialog(self._panel, parent=parent)
            self._dialog.closed.connect(self._refresh_summary)
            if self._get_params is not None and self._is_running is not None:
                self._panel.bind_controller(self._get_params, self._is_running)
        return self._dialog

    def _open_window(self) -> None:
        dialog = self._ensure_dialog()
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()
        self._refresh_summary()

    def _refresh_summary(self) -> None:
        self._summary.setText(self._panel.session_summary_text())

    def recargar_textos(self) -> None:
        self._open_btn.setText(tr("cal_wizard_open_window"))
        self._panel.recargar_textos()
        self._refresh_summary()
