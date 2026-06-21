"""Tests del motor y fuentes del Monitor."""
import time

from core.monitor.spectrum_engine import SpectrumEngine
from core.monitor.spectrum_params import SpectrumParams
from core.monitor.spectrum_source import MockSpectrumSource, create_spectrum_source, detect_sources


def test_mock_source_produces_frame():
    source = MockSpectrumSource()
    ok, _ = source.open()
    assert ok
    params = SpectrumParams(fft_size=512, span_hz=10_000_000)
    frame = source.read_frame(params)
    assert len(frame.power_db) == 512
    assert len(frame.freqs_hz) == 512
    source.close()


def test_spectrum_engine_start_stop():
    frames = []
    running_log = []

    def on_frame(frame):
        frames.append(frame)

    engine = SpectrumEngine(
        on_frame=on_frame,
        on_running_changed=lambda r: running_log.append(r),
    )
    t0 = __import__("time").perf_counter()
    ok, msg = engine.start()
    dt_ms = (__import__("time").perf_counter() - t0) * 1000
    assert ok
    assert msg == "Conectando…"
    assert dt_ms < 500, "start() no debe bloquear"
    __import__("time").sleep(0.25)
    engine.stop()
    assert len(frames) >= 1


def test_detect_sources_includes_mock():
    sources = detect_sources(probe_backend=False)
    ids = [item.source_id for item in sources]
    assert "mock" in ids


def test_create_spectrum_source_mock_default():
    source = create_spectrum_source("unknown")
    assert source.source_id == "mock"


def test_set_source_same_id_keeps_running():
    running_log = []
    engine = SpectrumEngine(on_running_changed=lambda r: running_log.append(r))
    ok, _ = engine.start()
    assert ok
    time.sleep(0.3)
    assert engine.is_running
    ok2, _ = engine.set_source("mock")
    assert ok2
    assert engine.is_running
    engine.stop()


def test_set_source_ignored_while_connecting():
    engine = SpectrumEngine()
    engine._connecting = True
    ok, _ = engine.set_source("hackrf")
    assert ok
    assert engine.params.source_id == "mock"
