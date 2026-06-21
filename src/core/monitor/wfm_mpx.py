"""Cadena MPX WFM broadcast — estéreo 19/38 kHz y alimentación RDS."""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from core.monitor.analog_demod_profiles import deemphasis_tau_sec

MPX_RATE_HZ = 228_000.0
PILOT_HZ = 19_000.0
RDS_SUBCARRIER_HZ = 57_000.0
AUDIO_LPF_HZ = 15_000.0
PILOT_PLL_ALPHA = 0.02
PILOT_BW_HZ = 350.0
DSB_BW_HZ = 15_000.0


@dataclass
class ResampleChainState:
    decim_tail: np.ndarray = field(default_factory=lambda: np.zeros(0, dtype=np.float64))
    in_audio_samples: int = 0
    out_audio_samples: float = 0.0

    def reset(self) -> None:
        self.decim_tail = np.zeros(0, dtype=np.float64)
        self.in_audio_samples = 0
        self.out_audio_samples = 0.0


@dataclass
class WfmMpxState:
    """Estado entre bloques para demod MPX / estéreo."""

    iq_to_mpx: ResampleChainState = field(default_factory=ResampleChainState)
    mpx_to_l: ResampleChainState = field(default_factory=ResampleChainState)
    mpx_to_r: ResampleChainState = field(default_factory=ResampleChainState)
    pilot_phase: float = 0.0
    pilot_freq_hz: float = PILOT_HZ
    pilot_i: float = 0.0
    pilot_q: float = 0.0
    deemph_l: float = 0.0
    deemph_r: float = 0.0
    audio_lp_l: float = 0.0
    audio_lp_r: float = 0.0
    mpx_phase: int = 0

    def reset_signal(self) -> None:
        self.iq_to_mpx.reset()
        self.mpx_to_l.reset()
        self.mpx_to_r.reset()
        self.pilot_phase = 0.0
        self.pilot_freq_hz = PILOT_HZ
        self.pilot_i = 0.0
        self.pilot_q = 0.0
        self.deemph_l = 0.0
        self.deemph_r = 0.0
        self.audio_lp_l = 0.0
        self.audio_lp_r = 0.0
        self.mpx_phase = 0


def _one_pole_alpha(cutoff_hz: float, sample_rate_hz: float) -> float:
    fc = max(80.0, min(float(cutoff_hz), float(sample_rate_hz) * 0.45))
    return math.exp(-2.0 * math.pi * fc / float(sample_rate_hz))


def _iir_one_pole(
    audio: np.ndarray,
    *,
    alpha: float,
    y0: float,
) -> tuple[np.ndarray, float]:
    x = np.asarray(audio, dtype=np.float64).reshape(-1)
    n = int(x.size)
    if n == 0:
        return x, float(y0)
    b0 = 1.0 - alpha
    n_taps = min(n, max(2, int(math.ceil(math.log(1e-12) / math.log(alpha)))))
    h = b0 * np.power(alpha, np.arange(n_taps, dtype=np.float64))
    y = np.convolve(x, h, mode="full")[:n]
    if y0 != 0.0:
        y += y0 * np.power(alpha, np.arange(1, n + 1, dtype=np.float64))
    weights = b0 * np.power(alpha, np.arange(n - 1, -1, -1, dtype=np.float64))
    y_final = float(y0 * (alpha**n) + np.dot(x, weights))
    return y, y_final


def _lowpass(
    audio: np.ndarray,
    *,
    cutoff_hz: float,
    sample_rate_hz: float,
    y0: float,
) -> tuple[np.ndarray, float]:
    if audio.size == 0:
        return audio, y0
    alpha = _one_pole_alpha(cutoff_hz, sample_rate_hz)
    return _iir_one_pole(audio, alpha=alpha, y0=y0)


def _deemphasis_cutoff_hz(tau_sec: float) -> float:
    return 1.0 / (2.0 * math.pi * max(tau_sec, 1e-9))


def _apply_deemphasis(
    audio: np.ndarray,
    *,
    deemphasis: str,
    sample_rate_hz: float,
    y0: float,
) -> tuple[np.ndarray, float]:
    tau = deemphasis_tau_sec(deemphasis)
    if tau is None or audio.size == 0:
        return audio, y0
    return _lowpass(
        audio,
        cutoff_hz=_deemphasis_cutoff_hz(tau),
        sample_rate_hz=sample_rate_hz,
        y0=y0,
    )


def resample_to_rate(
    audio: np.ndarray,
    *,
    in_rate_hz: float,
    out_rate_hz: float,
    state: ResampleChainState,
) -> np.ndarray:
    """Remuestreo exacto a la tasa destino (p. ej. IQ → MPX o MPX → audio)."""
    in_rate = float(in_rate_hz)
    out_rate = float(out_rate_hz)
    chunk = np.asarray(audio, dtype=np.float64).reshape(-1)
    if chunk.size == 0 or out_rate <= 0.0 or in_rate <= 0.0:
        return np.zeros(0, dtype=np.float64)

    if state.decim_tail.size:
        buf = np.concatenate([state.decim_tail, chunk])
        buf_start = state.in_audio_samples - state.decim_tail.size
    else:
        buf = chunk
        buf_start = state.in_audio_samples
    buf_end = buf_start + buf.size
    state.in_audio_samples = buf_end

    k0 = int(state.out_audio_samples)
    if buf.size < 2:
        return np.zeros(0, dtype=np.float64)

    t0 = max((k0 + 1) / out_rate, buf_start / in_rate)
    t1 = (buf_end - 2) / in_rate
    if t1 <= t0:
        keep = min(buf.size, max(2, int(in_rate / out_rate) + 3))
        state.decim_tail = buf[-keep:].copy()
        return np.zeros(0, dtype=np.float64)

    n_out = int(math.floor((t1 - t0) * out_rate)) + 1
    if n_out <= 0:
        keep = min(buf.size, max(2, int(in_rate / out_rate) + 3))
        state.decim_tail = buf[-keep:].copy()
        return np.zeros(0, dtype=np.float64)

    ks = k0 + 1 + np.arange(n_out, dtype=np.float64)
    in_pos = ks / out_rate * in_rate - buf_start
    valid = (in_pos >= 0.0) & (in_pos <= buf.size - 2)
    if not np.any(valid):
        keep = min(buf.size, max(2, int(in_rate / out_rate) + 3))
        state.decim_tail = buf[-keep:].copy()
        return np.zeros(0, dtype=np.float64)

    in_pos = in_pos[valid]
    ks = ks[valid]
    idx = np.arange(buf.size, dtype=np.float64)
    out = np.interp(in_pos, idx, buf)
    state.out_audio_samples = float(ks[-1])
    keep = min(buf.size, max(2, int(in_rate / out_rate) + 3))
    state.decim_tail = buf[-keep:].copy()
    return out.astype(np.float64)


def _track_pilot_pll(
    mpx: np.ndarray,
    *,
    sample_rate_hz: float,
    state: WfmMpxState,
) -> None:
    """PLL sobre el piloto 19 kHz para regenerar fase de portadora estéreo."""
    x = np.asarray(mpx, dtype=np.float64).reshape(-1)
    if x.size == 0:
        return
    alpha = _one_pole_alpha(PILOT_BW_HZ, sample_rate_hz)
    n = x.size
    idx = state.mpx_phase + np.arange(n, dtype=np.float64)
    t = idx / float(sample_rate_hz)
    ref_cos = np.cos(2.0 * math.pi * state.pilot_freq_hz * t + state.pilot_phase)
    ref_sin = np.sin(2.0 * math.pi * state.pilot_freq_hz * t + state.pilot_phase)
    mix_i = x * ref_cos
    mix_q = x * ref_sin
    i_acc = state.pilot_i
    q_acc = state.pilot_q
    for sample_i, sample_q in zip(mix_i, mix_q):
        i_acc = alpha * i_acc + (1.0 - alpha) * float(sample_i)
        q_acc = alpha * q_acc + (1.0 - alpha) * float(sample_q)
        phase_err = math.atan2(q_acc, i_acc + 1e-12)
        state.pilot_phase += PILOT_PLL_ALPHA * phase_err
        freq_corr = PILOT_PLL_ALPHA * 0.25 * phase_err
        state.pilot_freq_hz = max(18_500.0, min(19_500.0, state.pilot_freq_hz + freq_corr))
    state.pilot_i = i_acc
    state.pilot_q = q_acc


def decode_wfm_audio(
    mpx: np.ndarray,
    *,
    sample_rate_hz: float,
    state: WfmMpxState,
    stereo: bool,
    deemphasis: str,
    lowpass: bool = True,
) -> tuple[np.ndarray, np.ndarray]:
    """Devuelve canales L/R @ sample_rate_hz (mono: L==R)."""
    x = np.asarray(mpx, dtype=np.float64).reshape(-1)
    if x.size == 0:
        return np.zeros(0, dtype=np.float64), np.zeros(0, dtype=np.float64)

    if lowpass:
        l_plus_r, state.audio_lp_l = _lowpass(
            x,
            cutoff_hz=AUDIO_LPF_HZ,
            sample_rate_hz=sample_rate_hz,
            y0=state.audio_lp_l,
        )
    else:
        l_plus_r = x
        state.audio_lp_l = 0.0

    if not stereo:
        mono, state.deemph_l = _apply_deemphasis(
            l_plus_r,
            deemphasis=deemphasis,
            sample_rate_hz=sample_rate_hz,
            y0=state.deemph_l,
        )
        state.mpx_phase += x.size
        return mono, mono.copy()

    _track_pilot_pll(x, sample_rate_hz=sample_rate_hz, state=state)
    n = x.size
    idx = state.mpx_phase + np.arange(n, dtype=np.float64)
    t = idx / float(sample_rate_hz)
    ref38 = np.cos(4.0 * math.pi * state.pilot_freq_hz * t + 2.0 * state.pilot_phase)
    product = x * ref38
    if lowpass:
        l_minus_r, _ = _lowpass(
            product,
            cutoff_hz=DSB_BW_HZ,
            sample_rate_hz=sample_rate_hz,
            y0=0.0,
        )
    else:
        l_minus_r = product
    state.mpx_phase += n
    left = 0.5 * (l_plus_r + l_minus_r)
    right = 0.5 * (l_plus_r - l_minus_r)
    left, state.deemph_l = _apply_deemphasis(
        left,
        deemphasis=deemphasis,
        sample_rate_hz=sample_rate_hz,
        y0=state.deemph_l,
    )
    right, state.deemph_r = _apply_deemphasis(
        right,
        deemphasis=deemphasis,
        sample_rate_hz=sample_rate_hz,
        y0=state.deemph_r,
    )
    return left, right
