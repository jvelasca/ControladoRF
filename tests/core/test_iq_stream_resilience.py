"""Recuperación de stream IQ — errores transitorios vs fatales (estilo SDR++/Soapy)."""
from core.monitor.iq_stream_resilience import is_fatal_iq_error, is_transient_iq_error
from core.monitor.spectrum_engine import is_fatal_capture_error


def test_transient_iq_errors():
    for msg in (
        "",
        "Sin muestras IQ al iniciar",
        "Reiniciando captura IQ…",
        "Stream IQ detenido",
        "hackrf_transfer terminó al iniciar",
        "Esperando datos del equipo…",
    ):
        assert is_transient_iq_error(msg)
        assert not is_fatal_iq_error(msg)
        assert not is_fatal_capture_error(msg)


def test_fatal_only_when_device_unavailable():
    assert is_fatal_iq_error("HackRF no detectado por USB")
    assert is_fatal_iq_error("could not open device")
    assert is_fatal_iq_error("device not found")
    assert is_fatal_capture_error("Captura interrumpida — compruebe la conexión USB del equipo")


def test_stream_glitch_not_fatal():
    assert not is_fatal_iq_error("HackRF desconectado (USB)")
    assert not is_fatal_iq_error("Resource busy")
    assert not is_fatal_iq_error("Sin muestras IQ (¿PLAY activo?)")
