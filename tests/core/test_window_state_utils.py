"""Tests de serialización del layout de la ventana principal."""
from gui.window_state_utils import capture_main_window_layout


def test_capture_main_window_layout_keys():
    class _Window:
        def saveGeometry(self):
            class _Geo:
                def toBase64(self):
                    class _Data:
                        data = lambda self: b"abc"
                    return _Data()
            return _Geo()

        def isMaximized(self):
            return True

    state = capture_main_window_layout(_Window())
    assert "main_window_geometry" in state
    assert state["main_window_maximized"] is True
