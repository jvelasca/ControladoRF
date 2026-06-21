"""
icon_utils.py
-------------
Iconografía unificada: glyphs Qt monocromáticos que siguen la paleta claro/oscuro.

Todos los iconos de la app se resuelven aquí para mantener coherencia visual.
"""
from typing import Optional

from PyQt6.QtCore import QSize
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication, QStyle

# Tamaños estándar
ICON_SIZE_MENU = 16
ICON_SIZE_TOOLBAR = 16
ICON_SIZE_BUTTON = 18
ICON_SIZE_DIALOG = 20
ICON_SIZE_HERO = 48

# Mapa único nombre → glyph Qt (monocromático, sin color fijo)
APP_ICONS: dict[str, QStyle.StandardPixmap] = {
    "settings": QStyle.StandardPixmap.SP_FileDialogInfoView,
    "workspaces": QStyle.StandardPixmap.SP_DirIcon,
    "exit": QStyle.StandardPixmap.SP_DialogCloseButton,
    "about": QStyle.StandardPixmap.SP_FileDialogInfoView,
    "close": QStyle.StandardPixmap.SP_DialogCloseButton,
    "language": QStyle.StandardPixmap.SP_FileDialogContentsView,
    "lista": QStyle.StandardPixmap.SP_FileIcon,
    "columns": QStyle.StandardPixmap.SP_FileDialogListView,
    "propiedades": QStyle.StandardPixmap.SP_FileDialogInfoView,
    "acciones": QStyle.StandardPixmap.SP_FileDialogDetailedView,
    "spectrum": QStyle.StandardPixmap.SP_FileDialogListView,
    "waterfall": QStyle.StandardPixmap.SP_FileDialogDetailedView,
    "device": QStyle.StandardPixmap.SP_DriveHDIcon,
    "activate": QStyle.StandardPixmap.SP_DialogApplyButton,
    "delete": QStyle.StandardPixmap.SP_DialogDiscardButton,
    "duplicate": QStyle.StandardPixmap.SP_FileLinkIcon,
    "export": QStyle.StandardPixmap.SP_DialogSaveButton,
    "import": QStyle.StandardPixmap.SP_DialogOpenButton,
    "open": QStyle.StandardPixmap.SP_DialogOpenButton,
    "save": QStyle.StandardPixmap.SP_DialogSaveButton,
    "new": QStyle.StandardPixmap.SP_FileDialogNewFolder,
    "edit": QStyle.StandardPixmap.SP_FileDialogContentsView,
    "refresh": QStyle.StandardPixmap.SP_BrowserReload,
    "reset_panels": QStyle.StandardPixmap.SP_DialogResetButton,
    "lock": QStyle.StandardPixmap.SP_BrowserStop,
    "unlock": QStyle.StandardPixmap.SP_DialogApplyButton,
    "snapshot": QStyle.StandardPixmap.SP_FileDialogDetailedView,
}


def get_standard_pixmap(name: str) -> Optional[QStyle.StandardPixmap]:
    """Devuelve el StandardPixmap registrado o None."""
    return APP_ICONS.get(name)


def get_app_icon(name: str, size: int | None = None) -> QIcon:
    """
    Icono monocromático coherente con el modo claro/oscuro activo.

    Args:
        name: Clave del registro APP_ICONS.
        size: Si se indica, fija el tamaño preferido del icono.
    """
    pixmap = APP_ICONS.get(name)
    if pixmap is None:
        return QIcon()

    app = QApplication.instance()
    if app is None:
        return QIcon()

    icon = app.style().standardIcon(pixmap)
    if size is not None:
        icon = _with_fixed_size(icon, size)
    return icon


def _with_fixed_size(icon: QIcon, size: int) -> QIcon:
    fixed = QIcon()
    px = size
    for mode in (QIcon.Mode.Normal, QIcon.Mode.Disabled, QIcon.Mode.Active, QIcon.Mode.Selected):
        for state in (QIcon.State.On, QIcon.State.Off):
            fixed.addPixmap(icon.pixmap(QSize(px, px), mode, state), mode, state)
    return fixed
