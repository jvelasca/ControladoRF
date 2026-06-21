"""Tests de detección de errores fatales en captura."""
from core.monitor.spectrum_engine import is_fatal_capture_error


def test_usb_unavailable_is_fatal():
    assert is_fatal_capture_error("HackRF no detectado por USB")
    assert is_fatal_capture_error("could not open device")
    assert is_fatal_capture_error("device not found")
    assert is_fatal_capture_error("Captura interrumpida — compruebe la conexión USB del equipo")


def test_transient_errors_not_fatal():
    assert not is_fatal_capture_error("")
    assert not is_fatal_capture_error("Sin muestras IQ (¿PLAY activo?)")
    assert not is_fatal_capture_error("Reiniciando captura IQ…")
    assert not is_fatal_capture_error("Stream IQ detenido")
    assert not is_fatal_capture_error("HackRF desconectado (USB)")
    assert not is_fatal_capture_error("Resource busy")
