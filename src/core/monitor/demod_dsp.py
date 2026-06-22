"""Demodulación IQ → audio de banda base (FM/AM) para modo SDR."""
from __future__ import annotations

import math
import time
from dataclasses import dataclass, field

import numpy as np

from core.monitor.analog_demod_profiles import deemphasis_tau_sec, normalize_analog_demod_mode
from core.monitor.spectrum_params import SpectrumParams
from core.monitor.iq_constants import IQ_DEMOD_CHUNK_SAMPLES, IQ_DEMOD_MAX_SAMPLES
from core.monitor.wfm_mpx import MPX_RATE_HZ, WfmMpxState, decode_wfm_audio, resample_to_rate
from core.monitor.wfm_rds import RdsDecoderState, feed_rds_mpx

AUDIO_RATE_HZ = 48_000.0
RDS_FEED_MIN_INTERVAL_SEC = 0.05
SCOPE_SAMPLES = 2048
VU_ATTACK = 0.35
VU_RELEASE = 0.08
AGC_ATTACK = 0.015
AGC_RELEASE = 0.003
AGC_TARGET_RMS = 0.18
WFM_PCM_TARGET_PEAK = 0.82
SQUELCH_HYSTERESIS_DB = 6.0
SQUELCH_NOISE_ATTACK = 0.12
SQUELCH_NOISE_RELEASE = 0.004
SQUELCH_MIN_SNR_DB = 10.0
# Por debajo de este umbral el squelch queda abierto (efectivamente OFF).
SQUELCH_OFF_THRESHOLD_DB = -112.0
WFM_MAX_DEVIATION_HZ = 75_000.0
WFM_MIN_CHANNEL_BW_HZ = 150_000.0
NFM_COMPLEX_LPF_MAX_HZ = 100_000.0
DEEMP_TAU_SEC = 50e-6
AUDIO_LPF_HZ = 15_000.0
DC_BLOCK_ALPHA = 0.9985


@dataclass
class DemodStreamState:
    """Estado entre bloques IQ para audio continuo."""

    prev_iq: complex = 0j
    has_prev_iq: bool = False
    mix_sample_index: int = 0
    prev_phase: float | None = None
    decim_tail: np.ndarray = field(default_factory=lambda: np.zeros(0, dtype=np.float64))
    in_audio_samples: int = 0
    out_audio_samples: float = 0.0
    dc_estimate: float = 0.0
    chan_lp_i: float = 0.0
    chan_lp_q: float = 0.0
    iq_audio_lp_y: float = 0.0
    lp_audio_y: float = 0.0
    deemph_y: float = 0.0
    agc_gain: float = 1.0
    vu_level: float = -120.0
    vu_peak: float = -120.0
    squelch_open: bool = False
    squelch_noise_floor_dbfs: float = -120.0
    last_squelch_threshold_db: float = -120.0
    scope_buffer: np.ndarray | None = None
    wfm_mpx: WfmMpxState = field(default_factory=WfmMpxState)
    rds: RdsDecoderState = field(default_factory=RdsDecoderState)
    rds_last_feed_mono: float = 0.0

    def __post_init__(self) -> None:
        if self.scope_buffer is None:
            self.scope_buffer = np.zeros(SCOPE_SAMPLES, dtype=np.float32)

    def reset_signal(self) -> None:
        self.prev_iq = 0j
        self.has_prev_iq = False
        self.mix_sample_index = 0
        self.prev_phase = None
        self.decim_tail = np.zeros(0, dtype=np.float64)
        self.in_audio_samples = 0
        self.out_audio_samples = 0.0
        self.dc_estimate = 0.0
        self.chan_lp_i = 0.0
        self.chan_lp_q = 0.0
        self.iq_audio_lp_y = 0.0
        self.lp_audio_y = 0.0
        self.deemph_y = 0.0
        self.wfm_mpx.reset_signal()
        self.rds.reset()


def iq_samples_for_demod(params: SpectrumParams, *, fft_size: int) -> int:
    """Muestras IQ por bloque del hilo de demod (referencia / tests)."""
    n_fft = max(256, int(fft_size))
    if not params.demod_enabled():
        return n_fft
    chunk = max(n_fft, int(float(params.sample_rate_hz) / 40.0))
    return min(chunk, IQ_DEMOD_MAX_SAMPLES, IQ_DEMOD_CHUNK_SAMPLES * 4)


def _fm_discriminator(samples: np.ndarray, state: DemodStreamState) -> np.ndarray:
    """Demod FM por producto cruzado (continuidad entre bloques, estilo GQRX)."""
    x = np.asarray(samples, dtype=np.complex64).reshape(-1)
    if x.size == 0:
        return np.zeros(0, dtype=np.float64)
    if x.size == 1:
        if state.has_prev_iq:
            d = float(np.angle(x[0] * np.conjugate(state.prev_iq)))
            state.prev_iq = complex(x[0])
            return np.array([d], dtype=np.float64)
        state.prev_iq = complex(x[0])
        state.has_prev_iq = True
        return np.zeros(1, dtype=np.float64)

    if state.has_prev_iq:
        first = np.angle(x[0] * np.conjugate(state.prev_iq))
        rest = np.angle(x[1:] * np.conjugate(x[:-1]))
        dphase = np.concatenate(([first], rest))
    else:
        dphase = np.angle(x[1:] * np.conjugate(x[:-1]))
        dphase = np.concatenate(([dphase[0]], dphase))
    state.prev_iq = complex(x[-1])
    state.has_prev_iq = True
    return dphase.astype(np.float64)


def _apply_iq_correction(samples: np.ndarray) -> np.ndarray:
    """Corrección IQ básica: DC + balance I/Q por bloque."""
    x = np.asarray(samples, dtype=np.complex64).reshape(-1)
    if x.size == 0:
        return x
    i = x.real.astype(np.float64)
    q = x.imag.astype(np.float64)
    i -= float(np.mean(i))
    q -= float(np.mean(q))
    i_std = float(np.std(i) + 1e-9)
    q_std = float(np.std(q) + 1e-9)
    q *= i_std / q_std
    return (i + 1j * q).astype(np.complex64)


def _one_pole_alpha(cutoff_hz: float, sample_rate_hz: float) -> float:
    fc = max(80.0, min(float(cutoff_hz), float(sample_rate_hz) * 0.45))
    return math.exp(-2.0 * math.pi * fc / float(sample_rate_hz))


def _iir_one_pole(
    audio: np.ndarray,
    *,
    alpha: float,
    y0: float,
) -> tuple[np.ndarray, float]:
    """IIR y[n]=alpha*y[n-1]+(1-alpha)*x[n] vectorizado (NumPy)."""
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


def _lowpass_one_pole(
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


def _complex_lowpass_one_pole(
    samples: np.ndarray,
    *,
    cutoff_hz: float,
    sample_rate_hz: float,
    y0_i: float,
    y0_q: float,
) -> tuple[np.ndarray, float, float]:
    """Filtro paso-bajo complejo (I/Q) para canal WFM antes del discriminador."""
    x = np.asarray(samples, dtype=np.complex64).reshape(-1)
    if x.size == 0:
        return x, y0_i, y0_q
    alpha = _one_pole_alpha(cutoff_hz, sample_rate_hz)
    i_out, y_i = _iir_one_pole(x.real, alpha=alpha, y0=y0_i)
    q_out, y_q = _iir_one_pole(x.imag, alpha=alpha, y0=y0_q)
    return (i_out + 1j * q_out).astype(np.complex64), y_i, y_q


def _resample_to_audio_rate(
    audio: np.ndarray,
    *,
    sample_rate_hz: float,
    state: DemodStreamState,
) -> np.ndarray:
    """Remuestreo exacto a 48 kHz desde la tasa IQ de la cadena FM."""
    in_rate = float(sample_rate_hz)
    chunk = np.asarray(audio, dtype=np.float64).reshape(-1)
    if chunk.size == 0:
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

    t0 = max((k0 + 1) / AUDIO_RATE_HZ, buf_start / in_rate)
    t1 = (buf_end - 2) / in_rate
    if t1 <= t0:
        keep = min(buf.size, max(2, int(in_rate / AUDIO_RATE_HZ) + 3))
        state.decim_tail = buf[-keep:].copy()
        return np.zeros(0, dtype=np.float64)

    n_out = int(math.floor((t1 - t0) * AUDIO_RATE_HZ)) + 1
    if n_out <= 0:
        keep = min(buf.size, max(2, int(in_rate / AUDIO_RATE_HZ) + 3))
        state.decim_tail = buf[-keep:].copy()
        return np.zeros(0, dtype=np.float64)

    ks = k0 + 1 + np.arange(n_out, dtype=np.float64)
    in_pos = ks / AUDIO_RATE_HZ * in_rate - buf_start
    valid = (in_pos >= 0.0) & (in_pos <= buf.size - 2)
    if not np.any(valid):
        keep = min(buf.size, max(2, int(in_rate / AUDIO_RATE_HZ) + 3))
        state.decim_tail = buf[-keep:].copy()
        return np.zeros(0, dtype=np.float64)

    in_pos = in_pos[valid]
    ks = ks[valid]
    idx = np.arange(buf.size, dtype=np.float64)
    out = np.interp(in_pos, idx, buf)
    state.out_audio_samples = float(ks[-1])
    keep = min(buf.size, max(2, int(in_rate / AUDIO_RATE_HZ) + 3))
    state.decim_tail = buf[-keep:].copy()
    return out.astype(np.float64)


def _dc_block(audio: np.ndarray, state: DemodStreamState) -> np.ndarray:
    if audio.size == 0:
        return audio
    x = np.asarray(audio, dtype=np.float64).reshape(-1)
    alpha = DC_BLOCK_ALPHA
    est, state.dc_estimate = _iir_one_pole(x, alpha=alpha, y0=state.dc_estimate)
    return x - est


def _deemphasis_cutoff_hz(tau_sec: float) -> float:
    return 1.0 / (2.0 * math.pi * max(tau_sec, 1e-9))


def demod_tune_freq_hz(params: SpectrumParams) -> float:
    """Frecuencia de demodulación efectiva (VFO / marcador F / centro)."""
    if str(getattr(params, "freq_readout", "fc") or "fc").lower() == "f":
        selected = float(getattr(params, "selected_freq_hz", 0.0) or 0.0)
        if selected > 0.0:
            return selected
    vfo = float(getattr(params, "vfo_freq_hz", 0.0) or 0.0)
    if vfo > 0.0:
        return vfo
    return float(params.center_freq_hz)


def _fm_max_deviation_hz(mode: str, demod_bw: float) -> float:
    if mode == "nfm":
        return max(2_500.0, min(float(demod_bw) * 0.6, 25_000.0))
    if mode == "wfm":
        return WFM_MAX_DEVIATION_HZ
    return WFM_MAX_DEVIATION_HZ


def _channel_filter_cutoff_hz(mode: str, demod_bw: float, sample_rate_hz: float) -> float:
    """Ancho del filtro IF complejo previo al discriminador FM (no es el SPAN del espectro)."""
    bw = max(500.0, float(demod_bw))
    if mode == "wfm":
        bw = max(bw, WFM_MIN_CHANNEL_BW_HZ)
        # Mitad del canal (~100 kHz para BW 200 kHz), como SDR++ channel filter
        cutoff = bw * 0.5
    else:
        cutoff = bw * 0.45
    return min(cutoff, float(sample_rate_hz) * 0.45)


def _audio_lowpass_cutoff_hz(mode: str, demod_bw: float) -> float:
    """Filtro de audio tras la demodulación (15 kHz en WFM broadcast)."""
    if mode == "wfm":
        return AUDIO_LPF_HZ
    return min(max(500.0, float(demod_bw)) * 0.45, AUDIO_LPF_HZ)


def _apply_deemphasis(
    audio: np.ndarray,
    state: DemodStreamState,
    *,
    deemphasis: str,
) -> np.ndarray:
    tau = deemphasis_tau_sec(deemphasis)
    if tau is None or audio.size == 0:
        return audio
    out, state.deemph_y = _lowpass_one_pole(
        audio,
        cutoff_hz=_deemphasis_cutoff_hz(tau),
        sample_rate_hz=AUDIO_RATE_HZ,
        y0=state.deemph_y,
    )
    return out


def _apply_noise_blanker(audio: np.ndarray, nb_db: float) -> np.ndarray:
    if audio.size == 0 or nb_db <= 0.0:
        return audio
    x = np.asarray(audio, dtype=np.float64).reshape(-1)
    envelope = np.abs(x)
    floor = float(np.percentile(envelope, 25)) * (10.0 ** (float(nb_db) / 20.0))
    if floor <= 0.0:
        return x
    gated = x.copy()
    gated[envelope < floor] *= 0.05
    return gated


def _agc_rates(attack: float, decay: float) -> tuple[float, float]:
    attack_rate = min(1.0, max(0.001, 1.0 / max(float(attack), 1.0)))
    decay_rate = min(1.0, max(0.001, 1.0 / max(float(decay), 0.1)))
    return attack_rate, decay_rate


def _scale_wfm_pcm(audio: np.ndarray) -> np.ndarray:
    """Normalización suave WFM (sin AGC fuerte — más dinámica como SDR++)."""
    x = np.asarray(audio, dtype=np.float64).reshape(-1)
    if x.size == 0:
        return np.zeros(0, dtype=np.float32)
    peak = float(np.max(np.abs(x)))
    if peak < 1e-9:
        return x.astype(np.float32)
    gain = min(4.0, WFM_PCM_TARGET_PEAK / peak)
    return np.clip(x * gain, -1.0, 1.0).astype(np.float32)


def _apply_agc(audio: np.ndarray, state: DemodStreamState) -> np.ndarray:
    return _apply_agc_tuned(audio, state, attack=AGC_ATTACK, decay=AGC_RELEASE)


def _apply_agc_tuned(
    audio: np.ndarray,
    state: DemodStreamState,
    *,
    attack: float,
    decay: float,
) -> np.ndarray:
    if audio.size == 0:
        return audio.astype(np.float32)
    attack_rate, decay_rate = _agc_rates(attack, decay)
    x = audio.astype(np.float64)
    rms = float(np.sqrt(np.mean(np.square(x)) + 1e-18))
    if rms > 1e-9:
        desired = AGC_TARGET_RMS / rms
        rate = attack_rate if desired < state.agc_gain else decay_rate
        state.agc_gain = (1.0 - rate) * state.agc_gain + rate * desired
    gain = max(0.05, min(state.agc_gain, 25.0))
    return np.clip(x * gain, -1.0, 1.0).astype(np.float32)


def _apply_wfm_chain(
    audio: np.ndarray,
    state: DemodStreamState,
    *,
    deemphasis: str,
    max_deviation_hz: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Filtros FM @ 48 kHz: DC block → de-emphasis opcional → escala por desviación."""
    x = _dc_block(audio, state)
    x = _apply_deemphasis(x, state, deemphasis=deemphasis)
    normalized = x / max(max_deviation_hz, 1.0)
    return x, normalized


def _push_scope(state: DemodStreamState, samples: np.ndarray) -> None:
    buf = state.scope_buffer
    if buf is None or samples.size == 0:
        return
    s = np.asarray(samples, dtype=np.float32).reshape(-1)
    n = int(s.size)
    if n >= buf.size:
        state.scope_buffer = s[-buf.size :].copy()
        return
    state.scope_buffer = np.concatenate((buf[n:], s))


def _update_vu(state: DemodStreamState, pcm: np.ndarray) -> tuple[float, float]:
    if pcm.size == 0:
        return state.vu_level, state.vu_peak
    rms = float(np.sqrt(np.mean(np.square(pcm.astype(np.float64))) + 1e-18))
    peak = float(np.max(np.abs(pcm)))
    level_db = 20.0 * math.log10(rms + 1e-12)
    peak_db = 20.0 * math.log10(peak + 1e-12)
    if level_db > state.vu_level:
        state.vu_level = (1.0 - VU_ATTACK) * state.vu_level + VU_ATTACK * level_db
    else:
        state.vu_level = (1.0 - VU_RELEASE) * state.vu_level + VU_RELEASE * level_db
    if peak_db > state.vu_peak:
        state.vu_peak = peak_db
    else:
        state.vu_peak = (1.0 - VU_RELEASE) * state.vu_peak + VU_RELEASE * peak_db
    return state.vu_level, state.vu_peak



def squelch_passes_audio(
    *,
    squelch_enabled: bool,
    squelch_db: float,
    squelch_open: bool,
) -> bool:
    """True = audio audible (squelch desactivado o por encima del umbral)."""
    if not squelch_enabled or float(squelch_db) <= SQUELCH_OFF_THRESHOLD_DB:
        return True
    return bool(squelch_open)


def _update_squelch(
    state: DemodStreamState,
    level_dbfs: float,
    threshold_db: float,
    *,
    enabled: bool = True,
) -> bool:
    """Squelch dBFS: umbral directo con histéresis (ajuste suave en sintonía)."""
    level = float(level_dbfs)
    threshold = float(threshold_db)
    if not enabled or threshold <= SQUELCH_OFF_THRESHOLD_DB:
        state.squelch_open = True
        state.squelch_noise_floor_dbfs = -120.0
        state.last_squelch_threshold_db = threshold
        return True

    if threshold != state.last_squelch_threshold_db:
        state.last_squelch_threshold_db = threshold
        state.squelch_noise_floor_dbfs = -120.0
        state.squelch_open = level >= threshold
        return state.squelch_open

    open_db = threshold
    close_db = threshold - SQUELCH_HYSTERESIS_DB

    if not state.squelch_open:
        nf = float(state.squelch_noise_floor_dbfs)
        if nf <= -119.0:
            state.squelch_noise_floor_dbfs = min(level, threshold - 3.0)
        elif level <= nf + SQUELCH_MIN_SNR_DB:
            nf = nf + SQUELCH_NOISE_ATTACK * (level - nf)
            if level < nf:
                nf = level
            state.squelch_noise_floor_dbfs = max(-120.0, nf)
    elif state.squelch_open and state.squelch_noise_floor_dbfs > threshold - 3.0:
        nf = float(state.squelch_noise_floor_dbfs)
        state.squelch_noise_floor_dbfs = nf + 0.35 * ((threshold - 3.0) - nf)

    if state.squelch_open:
        if level < close_db:
            state.squelch_open = False
    elif level >= open_db:
        state.squelch_open = True
    return state.squelch_open


def _apply_squelch_mute(pcm: np.ndarray, *, open_: bool) -> np.ndarray:
    if open_ or pcm.size == 0:
        return pcm
    return np.zeros_like(pcm)


@dataclass(frozen=True)
class DemodAudioResult:
    pcm: np.ndarray
    waveform: np.ndarray
    scope: np.ndarray
    level_dbfs: float
    peak_dbfs: float
    vu_dbfs: float
    squelch_open: bool
    stereo: bool = False
    rds_text: str = ""
    rds_pi: str = ""
    rds_ps: str = ""
    rds_country: str = ""
    rds_coverage: str = ""
    rds_reference: str = ""
    rds_pty: str = ""
    rds_music: str = ""


def demod_iq_to_audio(
    samples: np.ndarray,
    params: SpectrumParams,
    *,
    sample_rate_hz: float,
    stream_state: DemodStreamState | None = None,
) -> DemodAudioResult:
    """PCM mono float32 @ 48 kHz, osciloscopio, VU y squelch."""
    empty_scope = np.zeros(SCOPE_SAMPLES, dtype=np.float32)
    empty = DemodAudioResult(
        pcm=np.zeros(0, dtype=np.float32),
        waveform=empty_scope,
        scope=empty_scope.copy(),
        level_dbfs=-120.0,
        peak_dbfs=-120.0,
        vu_dbfs=-120.0,
        squelch_open=False,
    )
    if samples.size < 32 or sample_rate_hz <= 0:
        return empty

    state = stream_state if stream_state is not None else DemodStreamState()
    x = np.asarray(samples, dtype=np.complex64).reshape(-1)
    if bool(getattr(params, "demod_iq_invert", False)):
        x = np.conjugate(x)
    if bool(getattr(params, "demod_iq_correction", False)):
        x = _apply_iq_correction(x)
    offset_hz = demod_tune_freq_hz(params) - float(params.center_freq_hz)
    if abs(offset_hz) >= 0.5:
        n = int(x.size)
        idx = state.mix_sample_index + np.arange(n, dtype=np.float64)
        phase = -2.0 * math.pi * offset_hz * idx / float(sample_rate_hz)
        shifted = x * np.exp(1j * phase).astype(np.complex64)
        state.mix_sample_index += n
    else:
        shifted = x

    mode = normalize_analog_demod_mode(params.demod_mode)
    demod_bw = max(500.0, float(params.demod_bandwidth_hz))

    if mode == "am":
        audio = np.abs(shifted).astype(np.float64)
        audio = _resample_to_audio_rate(
            audio,
            sample_rate_hz=float(sample_rate_hz),
            state=state,
        )
        if audio.size < 8:
            return empty
        audio, state.lp_audio_y = _lowpass_one_pole(
            audio,
            cutoff_hz=min(demod_bw * 0.45, AUDIO_LPF_HZ),
            sample_rate_hz=AUDIO_RATE_HZ,
            y0=state.lp_audio_y,
        )
        meter_src = audio / max(float(np.max(np.abs(audio))), 1e-6)
        pcm = _apply_agc(audio, state)
        meter = meter_src.astype(np.float64)
        rms = float(np.sqrt(np.mean(np.square(meter)) + 1e-18))
        level_dbfs = 20.0 * math.log10(rms + 1e-9)
        peak_dbfs = 20.0 * math.log10(float(np.max(np.abs(meter))) + 1e-9)
        vu_dbfs, _vu_peak = _update_vu(state, meter.astype(np.float32))
    elif mode == "dsb":
        audio = shifted.real.astype(np.float64)
        audio = _resample_to_audio_rate(
            audio,
            sample_rate_hz=float(sample_rate_hz),
            state=state,
        )
        if audio.size < 8:
            return empty
        audio = _apply_noise_blanker(audio, float(params.demod_noise_blanker_db))
        audio, state.lp_audio_y = _lowpass_one_pole(
            audio,
            cutoff_hz=min(demod_bw * 0.45, AUDIO_LPF_HZ),
            sample_rate_hz=AUDIO_RATE_HZ,
            y0=state.lp_audio_y,
        )
        meter = audio.astype(np.float64)
        pcm = _apply_agc_tuned(
            audio,
            state,
            attack=float(params.demod_agc_attack),
            decay=float(params.demod_agc_decay),
        )
        rms = float(np.sqrt(np.mean(np.square(meter)) + 1e-18))
        level_dbfs = 20.0 * math.log10(rms + 1e-9)
        peak_dbfs = 20.0 * math.log10(float(np.max(np.abs(meter))) + 1e-9)
        vu_dbfs, _vu_peak = _update_vu(state, meter.astype(np.float32))
    else:
        max_dev = _fm_max_deviation_hz(mode, demod_bw)
        if mode in ("nfm", "wfm"):
            chan_cutoff = _channel_filter_cutoff_hz(mode, demod_bw, float(sample_rate_hz))
            shifted, state.chan_lp_i, state.chan_lp_q = _complex_lowpass_one_pole(
                shifted,
                cutoff_hz=chan_cutoff,
                sample_rate_hz=float(sample_rate_hz),
                y0_i=state.chan_lp_i,
                y0_q=state.chan_lp_q,
            )
        audio = _fm_discriminator(shifted, state)
        audio = audio * (float(sample_rate_hz) / (2.0 * math.pi * max_dev))
        if mode == "wfm":
            nb = float(params.demod_noise_blanker_db)
            if nb > 0.0:
                audio = _apply_noise_blanker(audio, nb)
            mpx_state = state.wfm_mpx
            mpx = resample_to_rate(
                audio,
                in_rate_hz=float(sample_rate_hz),
                out_rate_hz=MPX_RATE_HZ,
                state=mpx_state.iq_to_mpx,
            )
            if mpx.size < 16:
                return empty
            stereo_on = bool(getattr(params, "demod_wfm_stereo", True))
            left, right = decode_wfm_audio(
                mpx,
                sample_rate_hz=MPX_RATE_HZ,
                state=mpx_state,
                stereo=stereo_on,
                deemphasis=str(params.demod_deemphasis),
                lowpass=bool(getattr(params, "demod_wfm_lowpass", True)),
            )
            if left.size < 8:
                return empty
            rds_text = ""
            rds_pi = ""
            rds_ps = ""
            rds_country = ""
            rds_coverage = ""
            rds_reference = ""
            rds_pty = ""
            rds_music = ""
            if bool(getattr(params, "demod_wfm_rds", False)):
                now = time.monotonic()
                if now - float(state.rds_last_feed_mono) >= RDS_FEED_MIN_INTERVAL_SEC:
                    state.rds_last_feed_mono = now
                    rds_text = feed_rds_mpx(mpx, sample_rate_hz=MPX_RATE_HZ, state=state.rds)
                else:
                    rds_text = state.rds.status
                rds_pi = state.rds.pi_hex
                rds_ps = (state.rds.ps_name or "").strip()
                rds_country = state.rds.country_code
                rds_coverage = state.rds.program_coverage
                rds_reference = state.rds.reference_display
                rds_pty = state.rds.program_type
                rds_music = state.rds.music_label
            else:
                state.rds.reset()
            left_48 = resample_to_rate(
                left,
                in_rate_hz=MPX_RATE_HZ,
                out_rate_hz=AUDIO_RATE_HZ,
                state=mpx_state.mpx_to_l,
            )
            if stereo_on:
                right_48 = resample_to_rate(
                    right,
                    in_rate_hz=MPX_RATE_HZ,
                    out_rate_hz=AUDIO_RATE_HZ,
                    state=mpx_state.mpx_to_r,
                )
            else:
                right_48 = left_48
            n = min(left_48.size, right_48.size)
            if n < 8:
                return empty
            left_48 = left_48[:n]
            right_48 = right_48[:n]
            meter = (0.5 * (left_48 + right_48)).astype(np.float64)
            left_pcm = _scale_wfm_pcm(left_48)
            right_pcm = _scale_wfm_pcm(right_48)
            rms = float(np.sqrt(np.mean(np.square(meter)) + 1e-18))
            level_dbfs = 20.0 * math.log10(rms + 1e-9)
            peak_dbfs = 20.0 * math.log10(float(np.max(np.abs(meter))) + 1e-9)
            vu_dbfs, _vu_peak = _update_vu(state, meter.astype(np.float32))
            squelch_open = _update_squelch(
                state,
                level_dbfs,
                float(params.squelch_db),
                enabled=bool(params.squelch_enabled),
            )
            left_pcm = _apply_squelch_mute(left_pcm, open_=squelch_open)
            right_pcm = _apply_squelch_mute(right_pcm, open_=squelch_open)
            if stereo_on:
                pcm = np.empty(n * 2, dtype=np.float32)
                pcm[0::2] = left_pcm
                pcm[1::2] = right_pcm
            else:
                pcm = left_pcm
            _push_scope(state, left_pcm)
            scope = state.scope_buffer if state.scope_buffer is not None else empty_scope
            tail = scope[-SCOPE_SAMPLES:]
            peak = float(np.max(np.abs(tail)) + 1e-9)
            waveform = (tail / peak).astype(np.float32)
            return DemodAudioResult(
                pcm=pcm,
                waveform=waveform,
                scope=scope,
                level_dbfs=level_dbfs,
                peak_dbfs=peak_dbfs,
                vu_dbfs=vu_dbfs,
                squelch_open=squelch_open,
                stereo=stereo_on,
                rds_text=rds_text,
                rds_pi=rds_pi,
                rds_ps=rds_ps,
                rds_country=rds_country,
                rds_coverage=rds_coverage,
                rds_reference=rds_reference,
                rds_pty=rds_pty,
                rds_music=rds_music,
            )
        audio = _resample_to_audio_rate(
            audio,
            sample_rate_hz=float(sample_rate_hz),
            state=state,
        )
        if audio.size < 8:
            return empty
        audio = _dc_block(audio, state)
        audio = _apply_deemphasis(audio, state, deemphasis=str(params.demod_deemphasis))
        audio, state.lp_audio_y = _lowpass_one_pole(
            audio,
            cutoff_hz=_audio_lowpass_cutoff_hz(mode, demod_bw),
            sample_rate_hz=AUDIO_RATE_HZ,
            y0=state.lp_audio_y,
        )
        meter = audio.astype(np.float64)
        pcm = _apply_agc(audio, state)
        rms = float(np.sqrt(np.mean(np.square(meter)) + 1e-18))
        level_dbfs = 20.0 * math.log10(rms + 1e-9)
        peak_dbfs = 20.0 * math.log10(float(np.max(np.abs(meter))) + 1e-9)
        vu_dbfs, _vu_peak = _update_vu(state, meter.astype(np.float32))
    _push_scope(state, pcm)
    squelch_open = _update_squelch(
        state,
        level_dbfs,
        float(params.squelch_db),
        enabled=bool(params.squelch_enabled),
    )
    pcm = _apply_squelch_mute(pcm, open_=squelch_open)

    scope = state.scope_buffer if state.scope_buffer is not None else empty_scope
    tail = scope[-SCOPE_SAMPLES:]
    peak = float(np.max(np.abs(tail)) + 1e-9)
    waveform = (tail / peak).astype(np.float32)

    return DemodAudioResult(
        pcm=pcm,
        waveform=waveform,
        scope=scope,
        level_dbfs=level_dbfs,
        peak_dbfs=peak_dbfs,
        vu_dbfs=vu_dbfs,
        squelch_open=squelch_open,
    )
