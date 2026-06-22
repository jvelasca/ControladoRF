"""Perfil resolución vs suavizado según modo de captura (IQ/SDR++ vs barrido).

La UI del Monitor separa dos conceptos que en analizadores clásicos se llaman RBW y VBW,
pero aquí se modelan de forma explícita para evitar confusión:

+------------------+---------------------------+---------------------------+
| Modo captura     | Control resolución (UI)   | Control suavizado (UI)    |
+==================+===========================+===========================+
| ``iq`` (SDR++)   | FFT — ``fft_size``        | SUAV — ``trace_smooth_*`` |
| ``sweep``        | RBW — ``rbw_hz``          | SUAV — ``trace_smooth_*`` |
+------------------+---------------------------+---------------------------+

Documentación completa: ``docs/monitor_bw_trace.md``.
"""
from __future__ import annotations

from core.monitor.monitor_format import format_bw_hz
from core.monitor.spectrum_params import SpectrumParams

# Puntos FFT (SDR++, libhackrf IQ) — control de resolución en pantalla.
IQ_FFT_PRESETS = (256, 512, 1024, 2048, 4096, 8192)

# Suavizado de traza = bins adyacentes fusionados (independiente de la resolución).
TRACE_SMOOTH_BIN_PRESETS = (1, 3, 5, 11, 21, 51)


def fft_resolution_auto(params: SpectrumParams) -> bool:
    """True si la rejilla FFT está en AUTO (IQ y barrido usan ``fft_auto``)."""
    return bool(params.fft_auto)


def uses_iq_resolution(params: SpectrumParams) -> bool:
    """True si la resolución la fija el tamaño FFT (modo IQ), no hackrf_sweep."""
    return params.capture_mode == "iq"


def iq_trace_sharp_active(params: SpectrumParams) -> bool:
    """Traza fina IQ: remuestreo por pico y FFT AUTO ampliada en span ancho."""
    return uses_iq_resolution(params) and bool(getattr(params, "iq_trace_sharp", False))


def plot_resample_method(params: SpectrumParams) -> str:
    """Método de remuestreo al pintar espectro/waterfall."""
    return "peak" if iq_trace_sharp_active(params) else "linear"


def resolution_title_key(params: SpectrumParams) -> str:
    """Clave i18n del título LCD de resolución (FFT o RBW)."""
    return "monitor_lcd_fft" if uses_iq_resolution(params) else "monitor_lcd_rbw"


def smoothing_title_key(_params: SpectrumParams) -> str:
    """Clave i18n del título LCD de suavizado (siempre SUAV)."""
    return "monitor_lcd_smooth"


def resolution_tip_key(params: SpectrumParams) -> str:
    return "monitor_tip_fft" if uses_iq_resolution(params) else "monitor_tip_rbw"


def resolution_menu_tip_key(params: SpectrumParams) -> str:
    return "monitor_tip_fft_menu" if uses_iq_resolution(params) else "monitor_tip_rbw_menu"


def smoothing_tip_key(_params: SpectrumParams) -> str:
    return "monitor_tip_smooth"


def smoothing_menu_tip_key(_params: SpectrumParams) -> str:
    return "monitor_tip_smooth_menu"


def trace_smoothing_bins(params: SpectrumParams) -> int:
    """Ancho efectivo del suavizado en bins FFT (1 = sin suavizado extra)."""
    return params.effective_trace_smooth_bins()


def format_resolution_status(params: SpectrumParams) -> str:
    """Texto corto para la franja de estado (resolución)."""
    from core.monitor.monitor_operating_mode import MonitorOperatingMode

    fft_part = f"FFT {params.fft_size}"
    if params.operating_mode_enum() is MonitorOperatingMode.SPECTRUM:
        if uses_iq_resolution(params):
            bin_hz = params.effective_rbw_hz()
            return f"{fft_part} · {format_bw_hz(bin_hz)}"
        rbw = format_bw_hz(params.effective_rbw_hz())
        return f"{fft_part} · RBW {rbw}"
    if uses_iq_resolution(params):
        bin_hz = params.effective_rbw_hz()
        return f"{fft_part} · {format_bw_hz(bin_hz)}"
    rbw = format_bw_hz(params.effective_rbw_hz())
    return f"RBW {rbw}"


def format_smoothing_status(params: SpectrumParams) -> str:
    """Texto corto para la franja de estado (suavizado SUAV)."""
    from i18n.json_translation import tr

    if params.trace_smooth_auto:
        return f"{tr('monitor_lcd_smooth')} {tr('monitor_lcd_smooth_off')}"
    bins = trace_smoothing_bins(params)
    if bins <= 1:
        return f"{tr('monitor_lcd_smooth')} {tr('monitor_lcd_smooth_off')}"
    return f"{tr('monitor_lcd_smooth')} ×{bins}"


def smooth_presets_for_params(params: SpectrumParams) -> tuple[int, ...]:
    """Presets de suavizado válidos (≤ bins de traza en pantalla)."""
    from core.rf.display import display_trace_bins

    cap = max(display_trace_bins(params), 64)
    valid = tuple(b for b in TRACE_SMOOTH_BIN_PRESETS if b <= cap)
    return valid or (1,)


def resolution_preset_selected(
    params: SpectrumParams,
    *,
    fft_size: int | None = None,
    rbw_hz: float | None = None,
) -> bool:
    """True si el preset coincide con el valor efectivo (AUTO o manual)."""
    if fft_size is not None:
        return int(params.fft_size) == int(fft_size)
    if rbw_hz is None:
        return False
    current = float(params.effective_rbw_hz() if params.rbw_auto else params.rbw_hz)
    tol = max(float(rbw_hz) * 0.001, 1.0)
    return abs(current - float(rbw_hz)) <= tol


def smooth_preset_selected(params: SpectrumParams, bins: int) -> bool:
    """True si el preset de suavizado coincide con el valor efectivo."""
    if params.trace_smooth_auto:
        return int(bins) <= 1
    return int(params.effective_trace_smooth_bins()) == int(bins)


def sweep_time_preset_selected(params: SpectrumParams, sweep_ms: float) -> bool:
    """True si el preset SWT coincide con el valor efectivo."""
    from core.monitor.monitor_bw_sweep_logic import effective_sweep_time_ms

    current = float(effective_sweep_time_ms(params))
    return abs(current - float(sweep_ms)) <= max(0.5, float(sweep_ms) * 0.02)
