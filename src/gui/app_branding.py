"""Marca, icono y versión de la aplicación."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap

from app_paths import bundle_root

_SRC_DIR = bundle_root()
_ICONS_DIR = _SRC_DIR / "resources" / "icons"
_ICON_PATH = _ICONS_DIR / "ico.ico"
_BRAND_PNG_CANDIDATES = (
    _ICONS_DIR / "brand.png",
    _ICONS_DIR / "logo.png",
    _ICONS_DIR / "app.png",
)
_VERSION_PATH = _SRC_DIR / "VERSION"
_ABOUT_HERO_SIZE = 112


def get_app_icon_path() -> Path:
    for candidate in _BRAND_PNG_CANDIDATES:
        if candidate.is_file():
            return candidate
    return _ICON_PATH


def get_app_version(fallback: str = "0.1.0") -> str:
    try:
        return _VERSION_PATH.read_text(encoding="utf-8").strip() or fallback
    except OSError:
        return fallback


@lru_cache(maxsize=1)
def get_app_window_icon() -> QIcon:
    path = get_app_icon_path()
    if path.is_file():
        return QIcon(str(path))
    return _build_brand_icon(256)


def get_app_brand_pixmap(size: int = 64) -> QPixmap:
    path = get_app_icon_path()
    if path.suffix.lower() == ".png" and path.is_file():
        pixmap = QPixmap(str(path))
        if not pixmap.isNull():
            return pixmap.scaled(
                size,
                size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
    icon = get_app_window_icon()
    pixmap = icon.pixmap(size, size)
    if pixmap.isNull():
        return _build_brand_icon(size).pixmap(size, size)
    return pixmap


def get_about_hero_pixmap() -> QPixmap:
    """Icono grande centrado en «Acerca de…» (sustituible por PNG en resources/icons/)."""
    return get_app_brand_pixmap(_ABOUT_HERO_SIZE)


def apply_app_window_icon(widget) -> None:
    widget.setWindowIcon(get_app_window_icon())


def _build_brand_icon(size: int) -> QIcon:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    margin = max(2, size // 16)
    painter.setBrush(QColor("#0078D4"))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawRoundedRect(margin, margin, size - 2 * margin, size - 2 * margin, size // 6, size // 6)
    painter.setPen(QColor("#FFFFFF"))
    font = QFont("Segoe UI", max(8, size // 3), QFont.Weight.Bold)
    painter.setFont(font)
    painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "RF")
    painter.end()
    return QIcon(pixmap)
