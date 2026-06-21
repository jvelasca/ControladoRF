#!/usr/bin/env python
"""Auditoria cadena RF -> FFT -> escala -> pintado (sin GUI).

Imprime, por etapa, la potencia en FI / centro / FF y el pico global.
Salida: consola + logs/audit_rf_chain_latest.txt

Uso:
  python scripts/audit_rf_chain.py --fc 97.3e6 --rate 10e6
  python scripts/audit_rf_chain.py --mock
"""
from __future__ import annotations

import argparse
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
LOG_DIR = ROOT / "logs"
sys.path.insert(0, str(SRC))

import numpy as np

from core.monitor.hackrf_baseband import default_baseband_filter_for_sample_rate
from core.monitor.hackrf_iq_capture import HackRfIqCapture
from core.monitor.hackrf_rx_gains import (
    HACKRF_ANTENNA_OFFSET_DB,
    calibrate_hackrf_antenna_power_db,
    iq_rx_gain_compensation_db,
)
from core.monitor.iq_fft import (
    HANNING_PEAK_CORRECTION_DB,
    apply_display_band_edge_guard,
    apply_display_dc_notch,
    band_edge_exclude_bins,
    compute_spectrum_frame,
    find_peak_excluding_dc,
    iq_bytes_to_complex,
)
from core.monitor.spectrum_params import SpectrumParams
from core.monitor.display_scale import apply_auto_vertical_scale
from core.monitor.spectrum_params import SpectrumFrame as LegacySpectrumFrame


@dataclass
class StageReport:
    name: str
    fi_db: float
    center_db: float
    ff_db: float
    peak_db: float
    peak_mhz: float
    interior_peak_db: float
    interior_peak_mhz: float
    p50_db: float


def _idx_nearest(freqs: np.ndarray, hz: float) -> int:
    return int(np.argmin(np.abs(freqs - hz)))


def _stage_stats(name: str, freqs: np.ndarray, power: np.ndarray, *, fc: float) -> StageReport:
    freqs = np.asarray(freqs, dtype=float).reshape(-1)
    power = np.asarray(power, dtype=float).reshape(-1)
    n = min(freqs.size, power.size)
    freqs = freqs[:n]
    power = power[:n]
    fi_i = 0
    ff_i = n - 1
    cen_i = _idx_nearest(freqs, fc)
    edge = band_edge_exclude_bins(n)
    interior = power[edge:-edge] if n > edge * 2 + 4 else power
    interior_f = freqs[edge:-edge] if n > edge * 2 + 4 else freqs
    pk_i = int(np.argmax(power))
    ipk_i = int(np.argmax(interior)) if interior.size else pk_i
    return StageReport(
        name=name,
        fi_db=float(power[fi_i]),
        center_db=float(power[cen_i]),
        ff_db=float(power[ff_i]),
        peak_db=float(power[pk_i]),
        peak_mhz=float(freqs[pk_i]) / 1e6,
        interior_peak_db=float(interior[ipk_i]) if interior.size else float(power[pk_i]),
        interior_peak_mhz=float(interior_f[ipk_i]) / 1e6 if interior_f.size else float(freqs[pk_i]) / 1e6,
        p50_db=float(np.median(power)),
    )


def _format_stage(r: StageReport) -> str:
    return (
        f"[{r.name}] FI={r.fi_db:6.1f} dB  FC={r.center_db:6.1f} dB  FF={r.ff_db:6.1f} dB  "
        f"pico={r.peak_db:6.1f} dB @ {r.peak_mhz:.3f} MHz  "
        f"pico_interior={r.interior_peak_db:6.1f} dB @ {r.interior_peak_mhz:.3f} MHz  med={r.p50_db:6.1f} dB"
    )


def audit_iq(
    *,
    fc: float,
    rate: float,
    fft: int,
    lna: int,
    vga: int,
    amp: bool,
    mock: bool,
) -> list[str]:
    lines: list[str] = []
    bb = default_baseband_filter_for_sample_rate(rate)
    gain_db = iq_rx_gain_compensation_db(lna_gain_db=lna, vga_gain_db=vga, rf_amp_enable=amp)
    lines.append(f"=== Cadena RF {datetime.now().isoformat(timespec='seconds')} ===")
    lines.append(f"FC={fc/1e6:.3f} MHz  SR={rate/1e6:.2f} Msps  FFT={fft}  LNA={lna} VGA={vga} P={'ON' if amp else 'OFF'}")
    lines.append(f"FI={(fc-rate/2)/1e6:.3f} MHz  FF={(fc+rate/2)/1e6:.3f} MHz  BB_filter_auto={bb/1e6:.1f} MHz (75% SR)")
    lines.append(f"Ganancia_nominal={gain_db:.0f} dB  offset_antena=+{HACKRF_ANTENNA_OFFSET_DB:.0f} dB")
    lines.append("")

    params = SpectrumParams(
        center_freq_hz=fc,
        sample_rate_hz=rate,
        fft_size=fft,
        capture_mode="iq",
        lna_gain_db=lna,
        vga_gain_db=vga,
        rf_amp_enable=amp,
        ref_scale_auto=True,
    )
    params.sync_iq_display()

    if mock:
        t = np.arange(fft, dtype=np.float64) / rate
        # Tonos en centro y en emisora FM simulada (no en bordes)
        tone_center = 0.25 * np.exp(2j * np.pi * 0.0 * t)
        tone_fm = 0.35 * np.exp(2j * np.pi * 200_000.0 * t)
        noise = 0.02 * (np.random.randn(fft) + 1j * np.random.randn(fft))
        samples = (tone_center + tone_fm + noise).astype(np.complex64)
        lines.append("Fuente: MOCK (tono en FC + offset +200 kHz)")
        backend = "mock"
    else:
        cap = HackRfIqCapture()
        cap.configure(
            center_freq_hz=fc,
            sample_rate_hz=rate,
            lna_gain=lna,
            vga_gain=vga,
            rf_amp_enable=amp,
            baseband_filter_bw_hz=float(bb),
        )
        ok, msg = cap.start()
        if not ok:
            lines.append(f"ERROR HackRF start: {msg}")
            return lines
        backend = cap.backend or "?"
        lines.append(f"Fuente: HackRF backend={backend}")
        lines.append(f"RX: {msg}")
        time.sleep(0.6)
        block = cap.read_iq_block(fft, wait_sec=3.0)
        cap.stop()
        if block is None:
            lines.append("ERROR: sin muestras IQ")
            return lines
        samples = iq_bytes_to_complex(block, num_samples=fft)
        rms = float(np.sqrt(np.mean(np.abs(samples) ** 2)))
        peak_iq = float(np.max(np.abs(samples)))
        lines.append(f"IQ muestras: RMS={rms:.4f}  pico|IQ|={peak_iq:.4f}  (sat si ~1.0)")
        lines.append("")

    n = len(samples)
    window = np.hanning(n)
    spectrum = np.fft.fftshift(np.fft.fft(samples * window))
    freqs = np.fft.fftshift(np.fft.fftfreq(n, d=1.0 / rate)) + fc
    p0 = 20.0 * np.log10(np.abs(spectrum) + 1e-12)
    p0 = p0 - 20.0 * np.log10(max(n, 1)) + HANNING_PEAK_CORRECTION_DB
    lines.append(_format_stage(_stage_stats("1_raw_fft_dBFS", freqs, p0, fc=fc)))

    p1 = p0 - gain_db
    lines.append(_format_stage(_stage_stats("2_minus_rx_gain", freqs, p1, fc=fc)))

    p2 = calibrate_hackrf_antenna_power_db(
        p0,
        lna_gain_db=lna,
        vga_gain_db=vga,
        rf_amp_enable=amp,
    )
    lines.append(_format_stage(_stage_stats("3_calibrado_dBm", freqs, p2, fc=fc)))

    p3 = apply_display_dc_notch(p2, center_freq_hz=fc, sample_rate_hz=rate)
    lines.append(_format_stage(_stage_stats("4_dc_notch", freqs, p3, fc=fc)))

    p4 = apply_display_band_edge_guard(p3)
    lines.append(_format_stage(_stage_stats("5_edge_guard", freqs, p4, fc=fc)))

    frame = compute_spectrum_frame(samples, params)
    lines.append(_format_stage(_stage_stats("6_compute_spectrum_frame", frame.freqs_hz, frame.power_db, fc=fc)))

    scaled = apply_auto_vertical_scale(
        LegacySpectrumFrame(
            freqs_hz=frame.freqs_hz,
            power_db=frame.power_db,
            center_freq_hz=fc,
            span_hz=rate,
            ref_level_dbm=0.0,
            ref_range_db=100.0,
        ),
        params,
    )
    lines.append(
        f"AUTO escala: ref={scaled.ref_level_dbm:.1f} dBm  rango={scaled.ref_range_db:.0f} dB  "
        f"(piso visible ~ {scaled.ref_level_dbm - scaled.ref_range_db:.1f} dBm)"
    )

    peak = find_peak_excluding_dc(
        frame.freqs_hz,
        frame.power_db,
        center_freq_hz=fc,
        sample_rate_hz=rate,
    )
    s = _stage_stats("diag", frame.freqs_hz, frame.power_db, fc=fc)
    if peak:
        lines.append(f"find_peak_excluding_dc -> {peak[0]/1e6:.3f} MHz @ {peak[1]:.1f} dB")
    lines.append(f"pico_global (argmax) -> {s.peak_mhz:.3f} MHz @ {s.peak_db:.1f} dB")
    lines.append("")

    # Diagnostico heuristico (fc en MHz, no Hz)
    fc_mhz = fc / 1e6
    half_mhz = rate / 2e6
    edge_dom = s.peak_db - s.interior_peak_db
    if s.peak_mhz <= fc_mhz - half_mhz * 0.9 or s.peak_mhz >= fc_mhz + half_mhz * 0.9:
        lines.append("ALERTA FI/FF: el pico global esta en el borde del paso de banda (+/-SR/2).")
    if edge_dom > 15.0:
        lines.append(
            f"ALERTA Borde domina escala: pico_global - pico_interior = {edge_dom:.1f} dB "
            "(AUTO ocultara el centro)."
        )
    if s.interior_peak_db < scaled.ref_level_dbm - scaled.ref_range_db + 6.0:
        lines.append(
            "ALERTA Portadora interior bajo el piso visible con AUTO "
            f"(interior={s.interior_peak_db:.1f} dB, piso~{scaled.ref_level_dbm - scaled.ref_range_db:.1f} dB)."
        )
    if s.interior_peak_db > scaled.ref_level_dbm - scaled.ref_range_db + 6.0:
        lines.append("OK Hay energia interior por encima del piso AUTO -- si no se ve, fallo es de PINTADO/GUI.")

    if mock:
        lines.append("(Mock esperado: pico interior cerca de FC, no en FI/FF)")
    lines.append("")
    lines.append("Ver docs/audit/06_portadoras_fi_ff.md")
    return lines


def main() -> int:
    parser = argparse.ArgumentParser(description="Auditoria cadena RF Monitor")
    parser.add_argument("--fc", type=float, default=97.3e6)
    parser.add_argument("--rate", type=float, default=10e6)
    parser.add_argument("--fft", type=int, default=2048)
    parser.add_argument("--lna", type=int, default=24)
    parser.add_argument("--vga", type=int, default=36)
    parser.add_argument("--amp", action="store_true")
    parser.add_argument("--mock", action="store_true")
    args = parser.parse_args()

    lines = audit_iq(
        fc=args.fc,
        rate=args.rate,
        fft=args.fft,
        lna=args.lna,
        vga=args.vga,
        amp=args.amp,
        mock=args.mock,
    )
    text = "\n".join(lines)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    out = LOG_DIR / "audit_rf_chain_latest.txt"
    out.write_text(text + "\n", encoding="utf-8")
    sys.stdout.buffer.write((text + f"\n\nGuardado: {out}\n").encode("utf-8", errors="replace"))
    return 0 if not any(line.startswith("ERROR") for line in lines) else 1


if __name__ == "__main__":
    raise SystemExit(main())
