"""
theme_utils.py
--------------
Apariencia adaptativa al SO con renderizado tipo IDE (Visual Studio).

Detecta modo claro/oscuro del sistema y aplica estilo Fusion + paleta + QSS global
para que menús, toolbars y barras de estado no queden con colores nativos incorrectos.
"""
from __future__ import annotations

import sys
from typing import Callable, Optional

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtWidgets import QApplication

_LIGHT_PALETTE = None
_DARK_PALETTE = None


def _build_light_palette() -> QPalette:
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor("#FFFFFF"))
    palette.setColor(QPalette.ColorRole.WindowText, QColor("#1E1E1E"))
    palette.setColor(QPalette.ColorRole.Base, QColor("#FFFFFF"))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#F6F6F6"))
    palette.setColor(QPalette.ColorRole.Text, QColor("#1E1E1E"))
    palette.setColor(QPalette.ColorRole.Button, QColor("#ECECEC"))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor("#1E1E1E"))
    palette.setColor(QPalette.ColorRole.Mid, QColor("#CCCEDB"))
    palette.setColor(QPalette.ColorRole.Dark, QColor("#A0A0A0"))
    palette.setColor(QPalette.ColorRole.Light, QColor("#F3F3F3"))
    palette.setColor(QPalette.ColorRole.Midlight, QColor("#E4E4E4"))
    palette.setColor(QPalette.ColorRole.Highlight, QColor("#0078D4"))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#FFFFFF"))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor("#FFFFFF"))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor("#1E1E1E"))
    palette.setColor(QPalette.ColorRole.Link, QColor("#0066CC"))
    palette.setColor(QPalette.ColorRole.PlaceholderText, QColor("#6A6A6A"))
    return palette


def _build_dark_palette() -> QPalette:
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor("#1E1E1E"))
    palette.setColor(QPalette.ColorRole.WindowText, QColor("#CCCCCC"))
    palette.setColor(QPalette.ColorRole.Base, QColor("#1E1E1E"))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#252526"))
    palette.setColor(QPalette.ColorRole.Text, QColor("#D4D4D4"))
    palette.setColor(QPalette.ColorRole.Button, QColor("#3E3E42"))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor("#F1F1F1"))
    palette.setColor(QPalette.ColorRole.Mid, QColor("#3F3F46"))
    palette.setColor(QPalette.ColorRole.Dark, QColor("#1E1E1E"))
    palette.setColor(QPalette.ColorRole.Light, QColor("#464649"))
    palette.setColor(QPalette.ColorRole.Midlight, QColor("#3E3E42"))
    palette.setColor(QPalette.ColorRole.Highlight, QColor("#094771"))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#FFFFFF"))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor("#252526"))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor("#CCCCCC"))
    palette.setColor(QPalette.ColorRole.Link, QColor("#3794FF"))
    palette.setColor(QPalette.ColorRole.PlaceholderText, QColor("#858585"))
    palette.setColor(QPalette.ColorRole.BrightText, QColor("#FFFFFF"))
    return palette


def _windows_prefers_dark_mode() -> Optional[bool]:
    if sys.platform != "win32":
        return None
    try:
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
        ) as key:
            value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
            return value == 0
    except OSError:
        return None


def is_dark_mode(app=None) -> bool:
    """True si el SO indica modo oscuro."""
    application = app or QApplication.instance()

    windows_dark = _windows_prefers_dark_mode()
    if windows_dark is not None:
        return windows_dark

    if application is not None:
        hints = application.styleHints()
        try:
            scheme = hints.colorScheme()
            if scheme == Qt.ColorScheme.Dark:
                return True
            if scheme == Qt.ColorScheme.Light:
                return False
        except (AttributeError, TypeError):
            pass

        window_color = application.palette().color(QPalette.ColorRole.Window)
        return window_color.lightness() < 128
    return False


def is_dark_theme(app=None) -> bool:
    return is_dark_mode(app)


def icon_mode(app=None) -> str:
    return "dark" if is_dark_mode(app) else "light"


def apply_system_appearance(app=None) -> None:
    """
    Aplica apariencia IDE coherente: Fusion + paleta VS + QSS global.

    Fusion garantiza que menú, toolbar y controles respeten la paleta; el estilo
    nativo windows11 suele dejar barras en tono claro/beige en modo oscuro.
    """
    global _LIGHT_PALETTE, _DARK_PALETTE

    application = app or QApplication.instance()
    if application is None:
        return

    if _LIGHT_PALETTE is None:
        _LIGHT_PALETTE = _build_light_palette()
        _DARK_PALETTE = _build_dark_palette()

    application.setStyle("Fusion")
    dark = is_dark_mode(application)
    application.setPalette(_DARK_PALETTE if dark else _LIGHT_PALETTE)

    from gui.app_chrome_styles import apply_application_chrome

    apply_application_chrome(application)


def connect_system_appearance_changed(callback: Callable) -> bool:
    application = QApplication.instance()
    if application is None:
        return False
    hints = application.styleHints()
    signal = getattr(hints, "colorSchemeChanged", None)
    if signal is None:
        return False
    signal.connect(callback)
    return True


def strip_legacy_theme_keys(config: dict) -> dict:
    if not isinstance(config, dict):
        return config
    cleaned = dict(config)
    cleaned.pop("theme", None)
    return cleaned


LEGACY_THEME_KEYS = ("theme",)
