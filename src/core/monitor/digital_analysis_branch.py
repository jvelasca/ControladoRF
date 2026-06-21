"""Rama análisis digital IQ → constelación / EVM (independiente del audio)."""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Any, Deque, Optional

from core.monitor.digital_mod_analysis import DigitalModAnalysis, analyze_digital_modulation
from core.monitor.digital_signal_profiles import get_digital_profile
from core.monitor.spectrum_params import SpectrumParams

MER_SMOOTH_WINDOW = 8


@dataclass(frozen=True)
class DigitalAnalysisUiState:
    valid: bool
    profile_id: str
    modulation: str
    symbol_rate_hz: float
    evm_rms_pct: float | None
    mer_db: float | None
    mer_db_smoothed: float | None
    constellation: Any
    status: str
    dab_sync_ok: bool = False
    dab_ensemble_detected: bool = False
    dab_active_carriers: int = 0
    dab_block_center_mhz: float | None = None
    welle_cli_available: bool = False
    carrier_locked: bool = False
    timing_locked: bool = False
    sync_ok: bool = False

    @classmethod
    def from_analysis(
        cls,
        result: DigitalModAnalysis,
        *,
        mer_db_smoothed: float | None = None,
    ) -> DigitalAnalysisUiState:
        return cls(
            valid=result.valid,
            profile_id=result.profile_id,
            modulation=result.modulation,
            symbol_rate_hz=result.symbol_rate_hz,
            evm_rms_pct=result.evm_rms_pct,
            mer_db=result.mer_db,
            mer_db_smoothed=mer_db_smoothed if mer_db_smoothed is not None else result.mer_db_smoothed,
            constellation=result.constellation.copy(),
            status=result.status,
            dab_sync_ok=result.dab_sync_ok,
            dab_ensemble_detected=result.dab_ensemble_detected,
            dab_active_carriers=result.dab_active_carriers,
            dab_block_center_mhz=result.dab_block_center_mhz,
            welle_cli_available=result.welle_cli_available,
            carrier_locked=result.carrier_locked,
            timing_locked=result.timing_locked,
            sync_ok=result.sync_ok,
        )


class DigitalAnalysisBranch:
    def __init__(self) -> None:
        self._last: Optional[DigitalModAnalysis] = None
        self._mer_history: Deque[float] = deque(maxlen=MER_SMOOTH_WINDOW)

    @property
    def last_analysis(self) -> Optional[DigitalModAnalysis]:
        return self._last

    @property
    def mer_db_smoothed(self) -> float | None:
        if not self._mer_history:
            return None
        return float(sum(self._mer_history) / len(self._mer_history))

    def reset(self) -> None:
        self._last = None
        self._mer_history.clear()

    def _smooth_mer(self, mer_db: float | None) -> float | None:
        if mer_db is None:
            return self.mer_db_smoothed
        self._mer_history.append(float(mer_db))
        return self.mer_db_smoothed

    def process_iq(
        self,
        iq_samples: Any,
        params: SpectrumParams,
        *,
        sample_rate_hz: float,
    ) -> DigitalModAnalysis | None:
        if not params.digital_analysis_active():
            self.reset()
            return None
        profile = get_digital_profile(params.digital_profile)
        result = analyze_digital_modulation(
            iq_samples,
            params,
            sample_rate_hz=sample_rate_hz,
            profile=profile,
        )
        mer_smooth = self._smooth_mer(result.mer_db)
        self._last = DigitalModAnalysis(
            valid=result.valid,
            profile_id=result.profile_id,
            modulation=result.modulation,
            symbol_rate_hz=result.symbol_rate_hz,
            samples_per_symbol=result.samples_per_symbol,
            evm_rms_pct=result.evm_rms_pct,
            mer_db=result.mer_db,
            constellation=result.constellation,
            status=result.status,
            dab_sync_ok=result.dab_sync_ok,
            dab_ensemble_detected=result.dab_ensemble_detected,
            dab_active_carriers=result.dab_active_carriers,
            dab_block_center_mhz=result.dab_block_center_mhz,
            welle_cli_available=result.welle_cli_available,
            carrier_locked=result.carrier_locked,
            timing_locked=result.timing_locked,
            sync_ok=result.sync_ok,
            mer_db_smoothed=mer_smooth,
        )
        return self._last

    def ui_state(self) -> DigitalAnalysisUiState | None:
        if self._last is None:
            return None
        return DigitalAnalysisUiState.from_analysis(
            self._last,
            mer_db_smoothed=self.mer_db_smoothed,
        )
