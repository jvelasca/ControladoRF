"""Rama demodulador IQ → visualización / audio (modo SDR)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

import numpy as np

from core.monitor.analog_demod_profiles import normalize_analog_demod_mode
from core.monitor.demod_dsp import DemodStreamState, demod_iq_to_audio
from core.monitor.spectrum_params import SpectrumParams


@dataclass(frozen=True)
class DemodState:
    level_dbfs: float
    peak_dbfs: float
    vu_dbfs: float
    squelch_open: bool
    waveform: np.ndarray
    scope: np.ndarray
    pcm: np.ndarray
    status: str
    mode: str
    vfo_hz: float
    bandwidth_hz: float
    stereo: bool = False
    rds_text: str = ""
    rds_pi: str = ""
    rds_ps: str = ""
    rds_country: str = ""
    rds_coverage: str = ""
    rds_reference: str = ""
    rds_pty: str = ""
    rds_music: str = ""


@dataclass(frozen=True)
class DemodUiState:
    """Estado ligero para la GUI (sin PCM de audio)."""

    level_dbfs: float
    peak_dbfs: float
    vu_dbfs: float
    squelch_open: bool
    waveform: np.ndarray
    scope: np.ndarray
    status: str
    mode: str
    vfo_hz: float
    bandwidth_hz: float
    stereo: bool = False
    rds_text: str = ""
    rds_pi: str = ""
    rds_ps: str = ""
    rds_country: str = ""
    rds_coverage: str = ""
    rds_reference: str = ""
    rds_pty: str = ""
    rds_music: str = ""

    @classmethod
    def from_state(cls, state: DemodState) -> DemodUiState:
        return cls(
            level_dbfs=state.level_dbfs,
            peak_dbfs=state.peak_dbfs,
            vu_dbfs=state.vu_dbfs,
            squelch_open=state.squelch_open,
            waveform=state.waveform.copy(),
            scope=state.scope.copy(),
            status=state.status,
            mode=state.mode,
            vfo_hz=state.vfo_hz,
            bandwidth_hz=state.bandwidth_hz,
            stereo=state.stereo,
            rds_text=state.rds_text,
            rds_pi=state.rds_pi,
            rds_ps=state.rds_ps,
            rds_country=state.rds_country,
            rds_coverage=state.rds_coverage,
            rds_reference=state.rds_reference,
            rds_pty=state.rds_pty,
            rds_music=state.rds_music,
        )


class DemodBranch:
    """Procesa muestras IQ para nivel, osciloscopio y PCM de audio."""

    def __init__(self) -> None:
        self._last_state: Optional[DemodState] = None
        self._stream = DemodStreamState()

    @property
    def last_state(self) -> Optional[DemodState]:
        return self._last_state

    def reset(self) -> None:
        self._stream = DemodStreamState()
        self._last_state = None

    def reset_signal_chain(self) -> None:
        """Tras hueco en buffer IQ — reinicia continuidad FM sin borrar AGC/VU."""
        self._stream.reset_signal()

    def relax_squelch(self) -> None:
        """Tras bajar umbral de squelch — permite reabrir audio de inmediato."""
        self._stream.squelch_open = True
        self._stream.squelch_noise_floor_dbfs = -120.0

    def process_iq(
        self,
        iq_samples: Any,
        params: SpectrumParams,
        *,
        sample_rate_hz: float,
    ) -> None:
        if not params.demod_enabled():
            self.reset()
            return
        result = demod_iq_to_audio(
            iq_samples,
            params,
            sample_rate_hz=sample_rate_hz,
            stream_state=self._stream,
        )
        mode = normalize_analog_demod_mode(params.demod_mode).upper()
        status = (
            f"{mode} · {params.demod_bandwidth_hz / 1e3:.0f} kHz · "
            f"VFO {params.vfo_freq_hz / 1e6:.3f} MHz · "
            f"{result.level_dbfs:.1f} dBFS"
        )
        if result.stereo:
            status += " · ST"
        elif mode == "WFM":
            status += " · MONO"
        if result.rds_text:
            status += f" · RDS {result.rds_text}"
        if not result.squelch_open:
            status += " · SQ"
        self._last_state = DemodState(
            level_dbfs=result.level_dbfs,
            peak_dbfs=result.peak_dbfs,
            vu_dbfs=result.vu_dbfs,
            squelch_open=result.squelch_open,
            waveform=result.waveform,
            scope=result.scope,
            pcm=result.pcm,
            status=status,
            mode=mode,
            vfo_hz=float(params.vfo_freq_hz),
            bandwidth_hz=float(params.demod_bandwidth_hz),
            stereo=result.stereo,
            rds_text=result.rds_text,
            rds_pi=result.rds_pi,
            rds_ps=result.rds_ps,
            rds_country=result.rds_country,
            rds_coverage=result.rds_coverage,
            rds_reference=result.rds_reference,
            rds_pty=result.rds_pty,
            rds_music=result.rds_music,
        )

    def status_for_params(self, params: SpectrumParams) -> Optional[str]:
        if not params.demod_enabled():
            return None
        if self._last_state is not None:
            return self._last_state.status
        mode = normalize_analog_demod_mode(params.demod_mode).upper()
        return f"{mode} · {params.demod_bandwidth_hz / 1e3:.0f} kHz"
