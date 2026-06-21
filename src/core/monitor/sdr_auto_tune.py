"""Ajuste automático de ganancia, span y squelch para demodulación SDR."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from core.monitor.display_scale import SPAN_STEPS_HZ, snap_lna_gain_db, snap_vga_gain_db
from core.monitor.iq_fft import dc_exclude_hz, find_peak_excluding_dc
from core.monitor.marker_analysis import estimate_snr_db, interpolate_power_db
from core.monitor.hackrf_rx_gains import snap_gains
from core.monitor.analog_demod_profiles import normalize_analog_demod_mode
from core.monitor.receive_mode_logic import (
    apply_receive_mode,
    infer_digital_profile_from_freq,
    is_digital_receive_mode,
    refresh_digital_profile_for_vfo,
)

FM_DEMOD_BW_HZ = 200_000.0
AM_DEMOD_BW_HZ = 1_000.0
FM_BROADCAST_SPAN_HZ = 2_000_000.0
MIN_FM_SAMPLE_RATE_HZ = FM_BROADCAST_SPAN_HZ
PEAK_SEARCH_HZ = 450_000.0
PREAMP_SNR_PENALTY_DB = 2.5
WFM_MIN_LNA_DB = 32
WFM_MIN_VGA_DB = 40


@dataclass(frozen=True)
class SdrAutoTuneResult:
    params: SpectrumParams
    summary: str
    ok: bool


@dataclass(frozen=True)
class _RfGainChoice:
    lna: int
    vga: int
    amp: bool


def _resolve_iq_sample_rate(params: SpectrumParams, *, wfm: bool = False) -> float:
    """WFM: span IQ fijo 2 MHz (SDR++). Otros modos: sube solo si está por debajo del mínimo."""
    if wfm:
        from core.monitor.display_scale import snap_iq_sample_rate_hz

        return float(snap_iq_sample_rate_hz(FM_BROADCAST_SPAN_HZ))
    current = max(float(params.sample_rate_hz), float(params.span_hz))
    if current >= MIN_FM_SAMPLE_RATE_HZ:
        return current
    for step in SPAN_STEPS_HZ:
        if step >= MIN_FM_SAMPLE_RATE_HZ:
            return float(step)
    return float(SPAN_STEPS_HZ[-1])


def _tune_hz(params: SpectrumParams) -> float:
    if params.freq_readout == "f" and params.selected_freq_hz > 0:
        return float(params.selected_freq_hz)
    if params.vfo_freq_hz > 0:
        return float(params.vfo_freq_hz)
    return float(params.center_freq_hz)


def _select_wfm_rf_gains(
    params: SpectrumParams,
    *,
    signal_db: float,
    snr: float | None,
) -> _RfGainChoice:
    """Ganancias conservadoras para WFM — evita LNA/VGA mínimos que degradan el audio."""
    snr_val = float(snr if snr is not None else signal_db + 90.0)
    lna, vga, amp = WFM_MIN_LNA_DB, WFM_MIN_VGA_DB, False
    if signal_db < -45.0:
        if snr_val < 8.0:
            lna, vga, amp = 40, 50, False
        elif snr_val < 12.0:
            lna, vga, amp = 40, 40, False
        if signal_db < -52.0 and snr_val < 10.0:
            amp = True
    elif signal_db > -14.0:
        lna, vga, amp = 16, 20, False
    elif signal_db > -22.0:
        lna, vga, amp = 24, 28, False
    choice = _clamp_gains(params, lna, vga, amp)
    if choice.lna < WFM_MIN_LNA_DB and signal_db < -18.0:
        choice = _clamp_gains(params, WFM_MIN_LNA_DB, max(choice.vga, WFM_MIN_VGA_DB), choice.amp)
    if choice.vga < WFM_MIN_VGA_DB and signal_db < -18.0:
        choice = _clamp_gains(params, choice.lna, WFM_MIN_VGA_DB, choice.amp)
    return choice


def _compute_wfm_auto_tune(params: SpectrumParams, frame: SpectrumFrame) -> SdrAutoTuneResult:
    """AUTO WFM: preset SDR++ (2 MHz, LNA 40, VGA 18, P ON) sin recalcular ganancias."""
    from core.monitor.wfm_broadcast_profile import apply_sdrpp_wfm_reference

    tune = _tune_hz(params)
    preserved_squelch = float(params.squelch_db)

    updated = apply_sdrpp_wfm_reference(params.copy(), tune_hz=tune)
    updated.squelch_db = preserved_squelch

    signal_db, noise_db, snr, _peak_hz = _measure_at_vfo(frame, updated, tune)
    if signal_db is None or noise_db is None:
        return SdrAutoTuneResult(params=updated, summary="monitor_auto_tune_no_signal", ok=False)

    snr_txt = f"{snr:.0f}" if snr is not None else "—"
    summary = (
        f"AUTO WFM · {tune / 1e6:.3f} MHz · IQ {updated.sample_rate_hz / 1e6:.1f} MHz · "
        f"LNA {updated.lna_gain_db} VGA {updated.vga_gain_db} "
        f"{'P+' if updated.rf_amp_enable else 'P−'} · SNR {snr_txt} dB"
    )
    return SdrAutoTuneResult(params=updated, summary=summary, ok=True)


def _measure_at_vfo(
    frame: SpectrumFrame,
    params: SpectrumParams,
    vfo_hz: float,
) -> tuple[float | None, float | None, float | None, float]:
    """Potencia en VFO, pico cercano (sin DC), ruido y SNR desde el trazo FFT."""
    freqs = np.asarray(frame.freqs_hz, dtype=float).reshape(-1)
    power = np.asarray(frame.power_db, dtype=float).reshape(-1)
    if freqs.size == 0 or power.size == 0:
        return None, None, None, float(vfo_hz)
    n = min(freqs.size, power.size)
    freqs = freqs[:n]
    power = power[:n]

    search = max(25_000.0, float(PEAK_SEARCH_HZ))
    peak = find_peak_excluding_dc(
        freqs,
        power,
        center_freq_hz=params.center_freq_hz,
        sample_rate_hz=params.sample_rate_hz,
    )
    if peak is not None:
        peak_hz, _peak_db = peak
    else:
        peak_hz = float(vfo_hz)

    signal_db = interpolate_power_db(freqs, power, vfo_hz)
    if signal_db is None and peak is not None:
        near_vfo = find_peak_excluding_dc(
            freqs,
            power,
            center_freq_hz=params.center_freq_hz,
            sample_rate_hz=params.sample_rate_hz,
            search_center_hz=vfo_hz,
            search_half_width_hz=search,
        )
        if near_vfo is not None:
            signal_db = near_vfo[1]
        else:
            signal_db = peak[1]

    if signal_db is None:
        return None, None, None, peak_hz

    noise_db = float(np.percentile(power, 20))
    snr = estimate_snr_db(power, signal_db)
    if snr is not None:
        noise_db = float(signal_db - snr)
    return signal_db, noise_db, snr, peak_hz


def _clamp_gains(
    params: SpectrumParams,
    lna: int,
    vga: int,
    amp: bool,
) -> _RfGainChoice:
    lna = snap_lna_gain_db(lna)
    vga = snap_vga_gain_db(vga)
    g = snap_gains(lna, vga, amp)
    return _RfGainChoice(g.lna_db, g.vga_db, g.amp_enable)


def _gains_for_level(
    params: SpectrumParams,
    *,
    signal_db: float,
    snr: float,
    allow_amp: bool,
) -> _RfGainChoice:
    """Tabla LNA/VGA; preamp solo si allow_amp y señal muy débil."""
    if signal_db > -18.0:
        lna, vga, amp = 8, 8, False
    elif signal_db > -26.0:
        lna, vga, amp = 16, 12, False
    elif snr >= 22.0:
        lna, vga, amp = 16, 16, False
    elif snr >= 14.0:
        lna, vga, amp = 24, 20, False
    elif snr >= 8.0:
        lna, vga, amp = 24, 28, False
    elif snr >= 4.0:
        lna, vga, amp = 32, 36, False
    elif allow_amp:
        lna, vga, amp = 32, 40, True
    else:
        lna, vga, amp = 40, 22, False

    choice = _clamp_gains(params, lna, vga, amp)
    if not allow_amp and choice.amp:
        return _clamp_gains(params, choice.lna, choice.vga, False)
    return choice


def _max_gains_off(params: SpectrumParams) -> _RfGainChoice:
    return _clamp_gains(params, 40, 62, False)


def _is_off_adequate(*, snr: float | None, signal_db: float) -> bool:
    """Señal suficiente para FM con preamp apagado."""
    if signal_db > -20.0:
        return True
    if snr is None:
        return False
    if snr >= 12.0:
        return True
    return snr >= 8.0 and signal_db > -38.0


def _demod_score(*, snr: float | None, signal_db: float, choice: _RfGainChoice) -> float:
    base = float(snr if snr is not None else signal_db + 90.0)
    score = base
    if choice.amp:
        score -= PREAMP_SNR_PENALTY_DB
    if signal_db > -20.0 and (choice.lna >= 24 or choice.amp):
        score -= max(0.0, signal_db + 20.0) * 0.75
    if -45.0 <= signal_db <= -25.0:
        score += 3.0
    score -= (choice.lna + choice.vga) * 0.015
    if choice.amp:
        score -= 0.5
    return score


def _select_rf_gains(
    params: SpectrumParams,
    *,
    signal_db: float,
    noise_db: float,
    snr: float | None,
) -> _RfGainChoice:
    """P OFF primero; si es bajo, compara OFF máximo vs ON y elige el mejor."""
    if snr is None:
        snr = float(signal_db - noise_db)

    off = _gains_for_level(params, signal_db=signal_db, snr=snr, allow_amp=False)
    if _is_off_adequate(snr=snr, signal_db=signal_db):
        return off

    candidates = [off, _max_gains_off(params)]
    on = _gains_for_level(params, signal_db=signal_db, snr=snr, allow_amp=True)
    if on.amp:
        candidates.append(on)

    best = max(candidates, key=lambda c: _demod_score(snr=snr, signal_db=signal_db, choice=c))
    if best.amp:
        best_off = max(candidates[:2], key=lambda c: _demod_score(snr=snr, signal_db=signal_db, choice=c))
        if _demod_score(snr=snr, signal_db=signal_db, choice=best_off) >= _demod_score(
            snr=snr, signal_db=signal_db, choice=best
        ) - 1.5:
            return best_off
    return best


def _apply_peak_tuning(params: SpectrumParams, peak_hz: float) -> None:
    """Alinea VFO al pico; ignora la fuga LO en el centro del espectro."""
    if abs(peak_hz - float(params.center_freq_hz)) <= dc_exclude_hz(params.sample_rate_hz):
        return
    params.vfo_freq_hz = peak_hz
    params.selected_freq_hz = peak_hz
    half_bw = float(params.sample_rate_hz) * 0.5
    center = float(params.center_freq_hz)
    margin = half_bw * 0.82
    if abs(peak_hz - center) > margin:
        params.center_freq_hz = peak_hz


def compute_digital_auto_tune(params: SpectrumParams, frame: SpectrumFrame | None) -> SdrAutoTuneResult:
    """AUTO en modo DIG: perfil por frecuencia + ganancia RF + centrado."""
    if frame is None or frame.freqs_hz.size < 8:
        return SdrAutoTuneResult(params=params.copy(), summary="monitor_auto_tune_no_frame", ok=False)

    updated = apply_receive_mode(params.copy(), "dig")
    updated.operating_mode = "sdr"
    if updated.span_mode not in ("manual", "last"):
        updated.span_mode = "manual"

    vfo = float(updated.vfo_freq_hz)
    if vfo <= 0.0:
        vfo = float(updated.center_freq_hz)
    signal_db, noise_db, snr, peak_hz = _measure_at_vfo(frame, updated, vfo)
    if signal_db is None or noise_db is None:
        return SdrAutoTuneResult(params=updated, summary="monitor_auto_tune_no_signal", ok=False)

    _apply_peak_tuning(updated, peak_hz)
    updated = refresh_digital_profile_for_vfo(updated)
    profile = infer_digital_profile_from_freq(updated.vfo_freq_hz)
    updated.digital_profile = profile

    gain = _select_rf_gains(updated, signal_db=signal_db, noise_db=noise_db, snr=snr)
    updated.lna_gain_db = gain.lna
    updated.vga_gain_db = gain.vga
    updated.rf_amp_enable = gain.amp
    if updated.capture_mode != "iq":
        updated.rf_attenuation_db = max(0.0, 40.0 - gain.lna)
    updated.ref_scale_auto = True
    updated.sync_iq_display()

    prof_label = profile.upper().replace("_", " ")
    snr_txt = f"{snr:.0f}" if snr is not None else "—"
    summary = (
        f"AUTO DIG · {updated.vfo_freq_hz / 1e6:.3f} MHz · {prof_label} · "
        f"IQ {updated.sample_rate_hz / 1e6:.1f} MHz · "
        f"LNA {gain.lna} VGA {gain.vga} {'P+' if gain.amp else 'P−'} · SNR {snr_txt} dB"
    )
    return SdrAutoTuneResult(params=updated, summary=summary, ok=True)


def compute_sdr_auto_tune(params: SpectrumParams, frame: SpectrumFrame | None) -> SdrAutoTuneResult:
    """Calcula parámetros optimizados para audio FM/AM o análisis DIG en modo SDR."""
    if not params.operating_mode_enum().demod_enabled():
        return SdrAutoTuneResult(params=params.copy(), summary="monitor_auto_tune_not_sdr", ok=False)
    if is_digital_receive_mode(params):
        return compute_digital_auto_tune(params, frame)
    if frame is None or frame.freqs_hz.size < 8:
        return SdrAutoTuneResult(params=params.copy(), summary="monitor_auto_tune_no_frame", ok=False)

    updated = params.copy()
    updated.operating_mode = "sdr"
    updated.audio_enabled = True
    updated.capture_mode = "iq"
    if updated.span_mode not in ("manual", "last"):
        updated.span_mode = "manual"

    mode = normalize_analog_demod_mode(updated.demod_mode)
    if mode == "am":
        updated.demod_bandwidth_hz = AM_DEMOD_BW_HZ
    elif mode == "nfm":
        updated.demod_bandwidth_hz = 12_500.0
    elif mode == "dsb":
        updated.demod_bandwidth_hz = 4_600.0
    else:
        return _compute_wfm_auto_tune(params, frame)

    rate = _resolve_iq_sample_rate(updated, wfm=False)
    updated.span_hz = rate
    updated.manual_span_hz = rate
    updated.sample_rate_hz = rate
    updated.apply_span_as_sample_rate()

    vfo = float(updated.vfo_freq_hz)
    if vfo <= 0.0:
        vfo = float(updated.center_freq_hz)
    signal_db, noise_db, snr, peak_hz = _measure_at_vfo(frame, updated, vfo)
    if signal_db is None or noise_db is None:
        return SdrAutoTuneResult(params=updated, summary="monitor_auto_tune_no_signal", ok=False)

    _apply_peak_tuning(updated, peak_hz)
    if updated.freq_readout == "f":
        from core.monitor.analog_demod_profiles import snap_vfo_freq_hz

        updated.vfo_freq_hz = snap_vfo_freq_hz(float(updated.vfo_freq_hz), updated.demod_snap_interval)
        updated.selected_freq_hz = updated.vfo_freq_hz

    gain = _select_rf_gains(updated, signal_db=signal_db, noise_db=noise_db, snr=snr)
    updated.lna_gain_db = gain.lna
    updated.vga_gain_db = gain.vga
    updated.rf_amp_enable = gain.amp
    if updated.capture_mode != "iq":
        updated.rf_attenuation_db = max(0.0, 40.0 - gain.lna)

    if updated.squelch_db > -40.0:
        updated.squelch_db = -81.0

    updated.ref_scale_auto = True
    updated.sync_iq_display()

    snr_txt = f"{snr:.0f}" if snr is not None else "—"
    summary = (
        f"AUTO · {updated.vfo_freq_hz / 1e6:.3f} MHz · IQ {updated.sample_rate_hz / 1e6:.1f} MHz · "
        f"LNA {gain.lna} VGA {gain.vga} {'P+' if gain.amp else 'P−'} · "
        f"SNR {snr_txt} dB"
    )
    return SdrAutoTuneResult(params=updated, summary=summary, ok=True)
