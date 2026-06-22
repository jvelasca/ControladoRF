"""Parámetros del analizador de espectro (compartidos GUI ↔ motor).

Campos clave de análisis (ver ``docs/monitor_bw_trace.md``):

- **Resolución** — ``rbw_hz`` + ``rbw_auto`` + ``fft_size`` (IQ: puntos FFT; barrido: RBW
  de ``hackrf_sweep``).
- **Suavizado de traza** — ``trace_smooth_auto`` + ``trace_smooth_bins`` (UI: SUAV).
  Independiente de la resolución; 1 bin = sin suavizado extra.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from core.monitor.monitor_operating_mode import MonitorOperatingMode


@dataclass
class SpectrumParams:
    """Estado del analizador — toolbar LCD, persistencia y motor FFT/barrido."""

    center_freq_hz: float = 100_000_000.0
    span_hz: float = 2_000_000.0
    manual_span_hz: float = 2_000_000.0
    last_span_hz: float = 2_000_000.0
    analyzer_span_hz: float = 0.0
    analyzer_span_mode: str = ""
    max_span_hz: float = 20_000_000.0
    span_mode: str = "manual"
    ref_level_dbm: float = 0.0
    ref_offset_db: float = 0.0
    ref_range_db: float = 100.0
    amplitude_unit: str = "dBm"
    rf_attenuation_db: float = 0.0
    lna_gain_db: int = 32
    vga_gain_db: int = 40
    rf_amp_enable: bool = False
    rf_bias_tee_enable: bool = False
    ref_scale_auto: bool = True
    ampt_mode: str = "ref_level"
    rbw_hz: float = 9_765.625
    rbw_auto: bool = True
    # Barrido: rejilla de pantalla (FFT) independiente de RBW hardware.
    fft_auto: bool = True
    # Suavizado espacial de la traza (UI «SUAV»). Auto = OFF (1 bin).
    trace_smooth_auto: bool = True
    trace_smooth_bins: int = 1
    sweep_time_ms: float = 100.0
    sweep_auto: bool = True
    sweep_mode: str = "continuous"  # continuous | single
    sweep_trigger_mode: str = "continuous"  # continuous | manual | periodic
    sweep_trigger_period_sec: float = 2.0
    single_sweep_pending: bool = False
    trace_mode: str = "clear_write"
    detector: str = "rms"
    # IQ/SDR: traza fina (FFT mayor, pico por columna, sin SUAV espacial).
    iq_trace_sharp: bool = False
    display_trace_fill: bool = False
    fft_size: int = 2048
    sample_rate_hz: float = 2_000_000.0
    baseband_filter_bw_hz: float = 1_750_000.0
    baseband_filter_auto: bool = True
    vertical_divisions: int = 10
    horizontal_divisions: int = 10
    running: bool = False
    source_id: str = "mock"
    capture_mode: str = "iq"  # iq = SDR nativo (SDR++); sweep = analizador barrido
    operating_mode: str = MonitorOperatingMode.SPECTRUM.value
    vfo_freq_hz: float = 100_000_000.0
    demod_mode: str = "wfm"
    demod_bandwidth_hz: float = 200_000.0
    demod_snap_interval: float = 100_000.0
    demod_deemphasis: str = "50us"
    demod_noise_blanker_db: float = 8.0
    demod_wfm_stereo: bool = True
    demod_wfm_rds: bool = False
    demod_wfm_lowpass: bool = True
    demod_iq_correction: bool = False
    demod_iq_invert: bool = False
    demod_agc_attack: float = 50.0
    demod_agc_decay: float = 5.0
    squelch_db: float = -81.0
    squelch_enabled: bool = True
    squelch_rf_level_dbm: float = -120.0
    show_demod_bandwidth: bool = True
    recorder_mode: str = "baseband"
    recorder_directory: str = ""
    recorder_filename: str = ""
    config_panel_collapsed: bool = False
    waterfall_panel_collapsed: bool = False
    audio_volume: float = 0.8
    audio_muted: bool = False
    audio_enabled: bool = False
    digital_analysis_enabled: bool = False
    digital_profile: str = "custom"
    digital_symbol_rate_hz: float = 500_000.0
    digital_mod_order: int = 4
    supervision_dwell_active: bool = False
    supervision_enabled: bool = True
    freq_readout: str = "fc"
    freq_pan_mode: str = "pan_spectrum"
    freq_step_hz: float = 100_000.0
    freq_offset_hz: float = 0.0
    freq_input_mode: str = "frequency"
    selected_freq_hz: float = 100_000_000.0
    marker_start_hz: float = 0.0
    marker_stop_hz: float = 0.0
    status_show_start: bool = True
    status_show_center: bool = True
    status_show_stop: bool = True
    status_show_step: bool = False
    status_show_readout: bool = True
    status_show_span: bool = True
    status_show_rbw: bool = False
    status_show_vbw: bool = False
    status_show_sweep: bool = False
    status_show_trace: bool = True
    status_show_detector: bool = True
    status_show_ref: bool = False
    status_show_ref_range: bool = False
    status_show_lna: bool = True
    status_show_preamp: bool = True
    status_show_vga: bool = True
    status_show_att: bool = False  # legacy alias → vga
    status_show_capture: bool = False
    status_show_fps: bool = False
    waterfall_min_db: float = -100.0
    waterfall_max_db: float = 0.0
    waterfall_auto_levels: bool = False
    waterfall_contrast_auto: bool = False
    waterfall_colormap: str = "jet"
    display_span_viewport_color: str = "#186038"
    display_span_viewport_hi_color: str = "#30B068"
    display_span_track_color: str = "#10161E"
    display_span_handle_color: str = "#5ADC8C"
    display_trace_color: str = "#00DC78"
    display_sdr_span_viewport_color: str = "#1A58A0"
    display_sdr_span_viewport_hi_color: str = "#2A78C8"
    display_sdr_span_track_color: str = "#121C2C"
    display_sdr_span_handle_color: str = "#48C8FF"
    display_sdr_trace_color: str = "#00C8FF"
    dock_collapse_mode: str = "auto"  # auto | collapsed | expanded
    dock_auto_collapse_sec: float = 2.0
    marker_show_line: bool = True
    marker_show_freq: bool = True
    marker_show_level: bool = True
    marker_show_snr: bool = True
    marker_auto_pan: bool = True
    active_marker_id: int = 1
    markers: list = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.markers:
            from core.monitor.marker_bank import default_marker_bank

            self.markers = default_marker_bank(self.center_freq_hz)

    def operating_mode_enum(self) -> MonitorOperatingMode:
        from core.monitor.monitor_operating_mode import normalize_operating_mode

        return normalize_operating_mode(self.operating_mode)

    def demod_enabled(self) -> bool:
        if (self.demod_mode or "wfm").lower() == "dig":
            return False
        return self.operating_mode_enum().demod_enabled() and self.audio_enabled

    def digital_analysis_active(self) -> bool:
        if self.capture_mode != "iq":
            return False
        if not self.operating_mode_enum().demod_enabled():
            return False
        return (self.demod_mode or "wfm").lower() == "dig"

    def apply_operating_mode(self) -> None:
        mode = self.operating_mode_enum()
        self.operating_mode = mode.value
        self.audio_enabled = mode.demod_enabled()
        self.supervision_enabled = mode is MonitorOperatingMode.SPECTRUM
        if mode is MonitorOperatingMode.SDR:
            if self.vfo_freq_hz <= 0:
                self.vfo_freq_hz = self.center_freq_hz
            if abs(self.selected_freq_hz) < 1.0:
                self.selected_freq_hz = self.center_freq_hz
            self.sync_receive_mode_effects()
        else:
            self.audio_enabled = False

    def sync_receive_mode_effects(self) -> None:
        """Audio vs análisis digital según FM/AM/DIG."""
        if not self.operating_mode_enum().demod_enabled():
            return
        rx = (self.demod_mode or "wfm").lower()
        if rx == "fm":
            rx = "wfm"
        if rx == "dig":
            self.audio_enabled = False
            self.digital_analysis_enabled = True
            self.capture_mode = "iq"
        elif rx in ("am", "nfm", "wfm", "dsb"):
            self.audio_enabled = True
            self.digital_analysis_enabled = False

    def instant_span_hz(self) -> float:
        from core.monitor.monitor_mode_profile import instant_span_hz_for_source

        return instant_span_hz_for_source(self.source_id)

    def has_freq_window(self) -> bool:
        return self.marker_stop_hz > self.marker_start_hz >= 1.0

    def uses_start_stop_window(self) -> bool:
        """True si FI/FF gobiernan el barrido (coherentes con el SPAN manual)."""
        if not self.has_freq_window() or self.capture_mode == "iq":
            return False
        window_span = max(0.0, float(self.marker_stop_hz - self.marker_start_hz))
        if self.span_mode == "manual" and self.manual_span_hz > 0.0:
            return abs(float(self.manual_span_hz) - window_span) <= 1.0
        return True

    def _computed_freq_start_hz(self) -> float:
        if self.capture_mode == "iq":
            return self.center_freq_hz - self.iq_plot_span_hz() / 2.0
        return self.center_freq_hz - self.span_hz / 2.0

    def _computed_freq_stop_hz(self) -> float:
        if self.capture_mode == "iq":
            return self.center_freq_hz + self.iq_plot_span_hz() / 2.0
        return self.center_freq_hz + self.span_hz / 2.0

    def freq_start_hz(self) -> float:
        if self.capture_mode == "iq":
            return self._computed_freq_start_hz() + self.freq_offset_hz
        if self.uses_start_stop_window():
            return float(self.marker_start_hz) + self.freq_offset_hz
        return self._computed_freq_start_hz() + self.freq_offset_hz

    def freq_stop_hz(self) -> float:
        if self.capture_mode == "iq":
            return self._computed_freq_stop_hz() + self.freq_offset_hz
        if self.uses_start_stop_window():
            return float(self.marker_stop_hz) + self.freq_offset_hz
        return self._computed_freq_stop_hz() + self.freq_offset_hz

    def sync_marker_window_from_span(self) -> None:
        self.marker_start_hz = self._computed_freq_start_hz()
        self.marker_stop_hz = self._computed_freq_stop_hz()

    def clear_freq_window(self) -> None:
        self.marker_start_hz = 0.0
        self.marker_stop_hz = 0.0

    def display_span_hz(self) -> float:
        if self.span_mode == "zero":
            return 0.0
        if self.span_mode == "manual" and self.manual_span_hz > 0.0:
            return max(0.0, float(self.manual_span_hz))
        if self.has_freq_window():
            return max(0.0, self.marker_stop_hz - self.marker_start_hz)
        if self.capture_mode == "iq":
            return self.sample_rate_hz
        return self.span_hz

    def iq_plot_span_hz(self) -> float:
        """Ancho visible en eje IQ (>= sample rate; 21 MHz con SR 20 MHz = IQ compuesto)."""
        if self.span_mode == "manual" and self.manual_span_hz > 0.0:
            return max(float(self.manual_span_hz), float(self.sample_rate_hz or 0.0))
        if self.span_hz > 0.0:
            return float(self.span_hz)
        return max(2_000_000.0, float(self.sample_rate_hz or 2_000_000.0))

    def _apply_iq_span_hw(self, display_hz: float) -> None:
        """Fija SR hardware (<= BW instantaneo) sin perder el lapso visible pedido."""
        from core.monitor.display_scale import snap_iq_sample_rate_hz

        display_hz = max(2_000_000.0, float(display_hz))
        cap = self.instant_span_hz()
        rate = snap_iq_sample_rate_hz(max(2_000_000.0, min(cap, display_hz)))
        self.sample_rate_hz = rate
        self.span_hz = display_hz
        if self.span_mode == "manual":
            self.manual_span_hz = display_hz
        self.sync_baseband_filter_bw()

    def apply_span_mode(self) -> None:
        """Aplica lapso manual / completo / cero / último."""
        if self.span_mode == "manual":
            hz = max(0.0, float(self.manual_span_hz))
        elif self.span_mode == "full":
            from core.monitor.monitor_mode_profile import device_full_span_hz

            hz = device_full_span_hz(self.source_id)
        elif self.span_mode == "zero":
            hz = 0.0
        elif self.span_mode == "last":
            hz = float(self.last_span_hz) if self.last_span_hz > 0 else float(self.manual_span_hz)
        else:
            self.span_mode = "manual"
            hz = max(0.0, float(self.manual_span_hz))

        if self.capture_mode == "iq":
            if hz <= 0.0:
                self.span_hz = 0.0
                self.sample_rate_hz = 2_000_000.0
            else:
                self._apply_iq_span_hw(hz)
        else:
            cap = float(self.max_span_hz)
            if self.span_mode == "full":
                cap = max(cap, hz)
            self.span_hz = max(0.0, min(cap, hz)) if self.span_mode != "full" else hz
            if self.span_mode == "manual" and hz > 0:
                self.manual_span_hz = self.span_hz

    def remember_span_before_mode_change(self) -> None:
        if self.span_mode == "manual" and self.manual_span_hz > 0:
            self.last_span_hz = self.manual_span_hz
        elif self.display_span_hz() > 0:
            self.last_span_hz = self.display_span_hz()

    def sync_baseband_filter_bw(self) -> None:
        """Filtro FI HackRF (~75 % SR en auto — como SDR++ / libhackrf)."""
        if not self.baseband_filter_auto:
            return
        from core.monitor.hackrf_baseband import default_baseband_filter_for_sample_rate

        self.baseband_filter_bw_hz = float(
            default_baseband_filter_for_sample_rate(self.sample_rate_hz)
        )

    def rf_passband_hz(self) -> float:
        """Ancho RF útil tras filtro FI (SDR++ «Bandwidth» en auto)."""
        if self.capture_mode == "iq":
            return self.baseband_filter_bw_hz
        return self.display_span_hz()

    def sync_iq_display(self) -> None:
        """Alinea span visible; el sample rate sigue acotado al BW instantaneo del SDR."""
        if self.capture_mode == "iq":
            self.span_hz = self.iq_plot_span_hz()
            self.sync_baseband_filter_bw()

    def apply_span_as_sample_rate(self) -> None:
        """En modo IQ, el SPAN seleccionado fija el sample rate del SDR (<= BW instantaneo)."""
        if self.capture_mode == "iq":
            if self.span_mode == "manual" and self.manual_span_hz > 0.0:
                source_hz = float(self.manual_span_hz)
            else:
                source_hz = float(self.span_hz)
            self._apply_iq_span_hw(source_hz)

    def effective_rbw_hz(self) -> float:
        if self.capture_mode == "iq":
            # SDR++: RBW de pantalla = sample rate / puntos FFT (no ancho RF).
            return self.sample_rate_hz / max(self.fft_size, 1)
        if self.capture_mode == "sweep":
            from core.monitor.monitor_bw_sweep_logic import resolved_sweep_rbw_hz

            return float(resolved_sweep_rbw_hz(self))
        if self.rbw_auto:
            span = max(self.display_span_hz(), self.span_hz, 1.0)
            rbw = span / max(self.fft_size, 1)
            return rbw
        return self.rbw_hz

    def effective_trace_smooth_bins(self) -> int:
        """Ancho del kernel de suavizado en bins FFT (1 = traza sin suavizar)."""
        if self.trace_smooth_auto:
            return 1
        from core.monitor.monitor_bw_sweep_logic import clamp_trace_smooth_bins

        return clamp_trace_smooth_bins(self, self.trace_smooth_bins)

    def db_per_division(self) -> float:
        return self.ref_range_db / max(self.vertical_divisions, 1)

    def freq_per_division_hz(self) -> float:
        return self.span_hz / max(self.horizontal_divisions, 1)

    def copy(self) -> "SpectrumParams":
        return SpectrumParams(
            center_freq_hz=self.center_freq_hz,
            span_hz=self.span_hz,
            manual_span_hz=self.manual_span_hz,
            last_span_hz=self.last_span_hz,
            analyzer_span_hz=self.analyzer_span_hz,
            analyzer_span_mode=self.analyzer_span_mode,
            max_span_hz=self.max_span_hz,
            span_mode=self.span_mode,
            ref_level_dbm=self.ref_level_dbm,
            ref_offset_db=self.ref_offset_db,
            ref_range_db=self.ref_range_db,
            amplitude_unit=self.amplitude_unit,
            rf_attenuation_db=self.rf_attenuation_db,
            lna_gain_db=self.lna_gain_db,
            vga_gain_db=self.vga_gain_db,
            rf_amp_enable=self.rf_amp_enable,
            rf_bias_tee_enable=self.rf_bias_tee_enable,
            ref_scale_auto=self.ref_scale_auto,
            ampt_mode=self.ampt_mode,
            rbw_hz=self.rbw_hz,
            rbw_auto=self.rbw_auto,
            fft_auto=self.fft_auto,
            trace_smooth_auto=self.trace_smooth_auto,
            trace_smooth_bins=self.trace_smooth_bins,
            sweep_time_ms=self.sweep_time_ms,
            sweep_auto=self.sweep_auto,
            sweep_mode=self.sweep_mode,
            sweep_trigger_mode=self.sweep_trigger_mode,
            sweep_trigger_period_sec=self.sweep_trigger_period_sec,
            single_sweep_pending=self.single_sweep_pending,
            trace_mode=self.trace_mode,
            detector=self.detector,
            iq_trace_sharp=self.iq_trace_sharp,
            display_trace_fill=self.display_trace_fill,
            fft_size=self.fft_size,
            sample_rate_hz=self.sample_rate_hz,
            baseband_filter_bw_hz=self.baseband_filter_bw_hz,
            baseband_filter_auto=self.baseband_filter_auto,
            vertical_divisions=self.vertical_divisions,
            horizontal_divisions=self.horizontal_divisions,
            running=self.running,
            source_id=self.source_id,
            capture_mode=self.capture_mode,
            operating_mode=self.operating_mode,
            vfo_freq_hz=self.vfo_freq_hz,
            demod_mode=self.demod_mode,
            demod_bandwidth_hz=self.demod_bandwidth_hz,
            demod_snap_interval=self.demod_snap_interval,
            demod_deemphasis=self.demod_deemphasis,
            demod_noise_blanker_db=self.demod_noise_blanker_db,
            demod_wfm_stereo=self.demod_wfm_stereo,
            demod_wfm_rds=self.demod_wfm_rds,
            demod_wfm_lowpass=self.demod_wfm_lowpass,
            demod_iq_correction=self.demod_iq_correction,
            demod_iq_invert=self.demod_iq_invert,
            demod_agc_attack=self.demod_agc_attack,
            demod_agc_decay=self.demod_agc_decay,
            squelch_db=self.squelch_db,
            squelch_enabled=self.squelch_enabled,
            squelch_rf_level_dbm=self.squelch_rf_level_dbm,
            show_demod_bandwidth=self.show_demod_bandwidth,
            recorder_mode=self.recorder_mode,
            recorder_directory=self.recorder_directory,
            recorder_filename=self.recorder_filename,
            config_panel_collapsed=self.config_panel_collapsed,
            waterfall_panel_collapsed=self.waterfall_panel_collapsed,
            audio_volume=self.audio_volume,
            audio_muted=self.audio_muted,
            audio_enabled=self.audio_enabled,
            digital_analysis_enabled=self.digital_analysis_enabled,
            digital_profile=self.digital_profile,
            digital_symbol_rate_hz=self.digital_symbol_rate_hz,
            digital_mod_order=self.digital_mod_order,
            supervision_dwell_active=self.supervision_dwell_active,
            supervision_enabled=self.supervision_enabled,
            freq_readout=self.freq_readout,
            freq_pan_mode=self.freq_pan_mode,
            freq_step_hz=self.freq_step_hz,
            freq_offset_hz=self.freq_offset_hz,
            freq_input_mode=self.freq_input_mode,
            selected_freq_hz=self.selected_freq_hz,
            marker_start_hz=self.marker_start_hz,
            marker_stop_hz=self.marker_stop_hz,
            status_show_start=self.status_show_start,
            status_show_center=self.status_show_center,
            status_show_stop=self.status_show_stop,
            status_show_step=self.status_show_step,
            status_show_readout=self.status_show_readout,
            status_show_span=self.status_show_span,
            status_show_rbw=self.status_show_rbw,
            status_show_vbw=self.status_show_vbw,
            status_show_sweep=self.status_show_sweep,
            status_show_trace=self.status_show_trace,
            status_show_detector=self.status_show_detector,
            status_show_ref=self.status_show_ref,
            status_show_ref_range=self.status_show_ref_range,
            status_show_lna=self.status_show_lna,
            status_show_preamp=self.status_show_preamp,
            status_show_vga=self.status_show_vga,
            status_show_att=self.status_show_att,
            status_show_capture=self.status_show_capture,
            status_show_fps=self.status_show_fps,
            waterfall_min_db=self.waterfall_min_db,
            waterfall_max_db=self.waterfall_max_db,
            waterfall_auto_levels=self.waterfall_auto_levels,
            waterfall_contrast_auto=self.waterfall_contrast_auto,
            waterfall_colormap=self.waterfall_colormap,
            display_span_viewport_color=self.display_span_viewport_color,
            display_span_viewport_hi_color=self.display_span_viewport_hi_color,
            display_span_track_color=self.display_span_track_color,
            display_span_handle_color=self.display_span_handle_color,
            display_trace_color=self.display_trace_color,
            display_sdr_span_viewport_color=self.display_sdr_span_viewport_color,
            display_sdr_span_viewport_hi_color=self.display_sdr_span_viewport_hi_color,
            display_sdr_span_track_color=self.display_sdr_span_track_color,
            display_sdr_span_handle_color=self.display_sdr_span_handle_color,
            display_sdr_trace_color=self.display_sdr_trace_color,
            dock_collapse_mode=self.dock_collapse_mode,
            dock_auto_collapse_sec=self.dock_auto_collapse_sec,
            marker_show_line=self.marker_show_line,
            marker_show_freq=self.marker_show_freq,
            marker_show_level=self.marker_show_level,
            marker_show_snr=self.marker_show_snr,
            marker_auto_pan=self.marker_auto_pan,
            active_marker_id=self.active_marker_id,
            markers=[marker.copy() for marker in self.markers],
        )


@dataclass
class SpectrumFrame:
    """Un trazo FFT listo para pintar."""

    freqs_hz: object = field(default_factory=list)
    power_db: object = field(default_factory=list)
    center_freq_hz: float = 0.0
    span_hz: float = 0.0
    ref_level_dbm: float = 0.0
    ref_range_db: float = 100.0
