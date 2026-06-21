"""ViewModel Monitor — fachada GUI sobre RfSession / RfSpectrumRunner."""

from __future__ import annotations



from core.monitor.spectrum_params import SpectrumFrame, SpectrumParams

from core.rf.bridge import legacy_frame_from_display, operator_intent_from_params

from core.rf.runner import RfSpectrumRunner

from core.rf.session import RfSession

from core.rf.types import RfTelemetry, SpectrumDisplayFrame





class MonitorRfViewModel:

    """Estado RF v2 para el módulo Monitor (sin PyQt)."""



    def __init__(self) -> None:

        self._runner: RfSpectrumRunner | None = None



    @property

    def session(self) -> RfSession:

        if self._runner is None:

            raise RuntimeError("RfSpectrumRunner not bound — call bind_runner first")

        return self._runner.session



    def bind_runner(self, runner: RfSpectrumRunner) -> None:

        self._runner = runner



    def reset_trace_state(self) -> None:

        if self._runner is not None:

            self._runner.session.reset_analysis_pipeline()



    def apply_params(self, params: SpectrumParams) -> SpectrumParams:

        updated = params.copy()

        if self._runner is not None:

            self._runner.sync_from_params(updated)

        return updated



    def capture_preview(self) -> SpectrumDisplayFrame:

        session = self.session

        if session.device is None:

            raise RuntimeError("No device attached — call apply_params first")

        if not session.device.is_open:

            session.open()

        return session.capture_once()



    def telemetry(self) -> RfTelemetry:

        if self._runner is not None:

            return self._runner.telemetry()

        return self.session.telemetry()



    @staticmethod

    def to_legacy_frame(display: SpectrumDisplayFrame, params: SpectrumParams) -> SpectrumFrame:

        return legacy_frame_from_display(

            display,

            center_freq_hz=params.center_freq_hz,

            span_hz=max(params.span_hz, params.display_span_hz()),

        )

