"""Calibración y auto-test de la cadena analizador (estilo equipos R&S / Keysight).

Módulos:
- ``chain_validator`` — invariantes entrada RF → procesado → visualización
- ``capture_transition`` — perfiles IQ/barrido al cruzar SPAN ~20 MHz
- ``scenario_matrix`` — matriz de escenarios (SPAN, RBW, FFT, AUTO/MANUAL)
- ``harness`` — ejecutor con informe JSON/Markdown
"""
from core.monitor.calibration.capture_transition import apply_capture_mode_transition
from core.monitor.calibration.chain_validator import ChainCheck, validate_analysis_chain
from core.monitor.calibration.harness import CalibrationHarness, CalibrationReport

__all__ = [
    "ChainCheck",
    "validate_analysis_chain",
    "apply_capture_mode_transition",
    "CalibrationHarness",
    "CalibrationReport",
]
