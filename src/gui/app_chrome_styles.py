"""
app_chrome_styles.py
--------------------
Estilos globales tipo IDE (Visual Studio / Photoshop): menú, toolbar, status bar, docks y controles.
"""
from PyQt6.QtWidgets import QApplication

from utils.theme_utils import is_dark_mode

# Tokens de color inspirados en Visual Studio 2022
_VS = {
    "dark": {
        "window": "#1E1E1E",
        "chrome": "#2D2D30",
        "chrome_alt": "#252526",
        "chrome_elevated": "#333337",
        "border": "#3F3F46",
        "text": "#CCCCCC",
        "text_primary": "#F1F1F1",
        "text_muted": "#858585",
        "hover": "#3E3E42",
        "pressed": "#007ACC",
        "selection": "#094771",
        "accent": "#0078D4",
        "input_bg": "#1E1E1E",
        "status_bg": "#252526",
        "status_text": "#CCCCCC",
        "status_muted": "#858585",
        "separator": "#3F3F46",
    },
    "light": {
        "window": "#FFFFFF",
        "chrome": "#F3F3F3",
        "chrome_alt": "#ECECEC",
        "chrome_elevated": "#E4E4E4",
        "border": "#CCCEDB",
        "text": "#1E1E1E",
        "text_primary": "#1E1E1E",
        "text_muted": "#6A6A6A",
        "hover": "#E5F3FF",
        "pressed": "#CCE8FF",
        "selection": "#0078D4",
        "accent": "#0078D4",
        "input_bg": "#FFFFFF",
        "status_bg": "#ECECEC",
        "status_text": "#1E1E1E",
        "status_muted": "#6A6A6A",
        "separator": "#CCCEDB",
    },
}


def _tokens(dark: bool) -> dict:
    return _VS["dark" if dark else "light"]


def build_ide_stylesheet(dark: bool | None = None) -> str:
    """Genera QSS global para toda la aplicación."""
    is_dark = dark if dark is not None else is_dark_mode()
    c = _tokens(is_dark)
    sel_fg = "#FFFFFF"

    return f"""
/* ---- Ventana principal ---- */
QMainWindow, QWidget {{
    background-color: {c['window']};
    color: {c['text']};
}}

/* ---- Barra de menús ---- */
QMenuBar {{
    background-color: {c['chrome']};
    color: {c['text_primary']};
    border-bottom: 1px solid {c['border']};
    padding: 2px 0;
    spacing: 0;
}}
QMenuBar::item {{
    background: transparent;
    color: {c['text_primary']};
    padding: 6px 12px;
    margin: 0;
    border-radius: 0;
}}
QMenuBar::item:selected, QMenuBar::item:pressed {{
    background-color: {c['hover']};
    color: {c['text_primary']};
}}
QMenu {{
    background-color: {c['chrome_alt']};
    color: {c['text_primary']};
    border: 1px solid {c['border']};
    padding: 4px 0;
}}
QMenu::item {{
    padding: 6px 28px 6px 20px;
    color: {c['text_primary']};
}}
QMenu::item:selected {{
    background-color: {c['selection']};
    color: {sel_fg};
}}
QMenu::separator {{
    height: 1px;
    background: {c['separator']};
    margin: 4px 8px;
}}

/* ---- Barra de herramientas ---- */
QToolBar {{
    background-color: {c['chrome_elevated']};
    border: none;
    border-bottom: 1px solid {c['border']};
    spacing: 4px;
    padding: 3px 6px;
}}
QToolBar::separator {{
    background: {c['separator']};
    width: 1px;
    margin: 4px 6px;
}}
QToolButton {{
    background: transparent;
    border: 1px solid transparent;
    border-radius: 3px;
    padding: 4px 6px;
    color: {c['text_primary']};
}}
QToolButton:hover {{
    background-color: {c['hover']};
    border-color: {c['border']};
}}
QToolButton:pressed, QToolButton:checked {{
    background-color: {c['selection'] if is_dark else c['pressed']};
    border-color: {c['accent']};
}}

/* ---- Barra de estado (integrada al cromo, sin azul) ---- */
QStatusBar {{
    background-color: {c['status_bg']};
    color: {c['status_text']};
    border-top: 1px solid {c['border']};
    padding: 2px 8px;
    min-height: 24px;
    font-size: 12px;
}}
QStatusBar QLabel {{
    color: {c['status_text']};
    background: transparent;
    padding: 0 8px;
}}
QStatusBar::item {{
    border: none;
}}
QFrame#StatusBarSeparator {{
    color: {c['border']};
    background: {c['border']};
    margin: 0 4px;
}}
QLabel#StatusBarWorkspaceLabel {{
    color: {c['status_muted']};
    font-size: 11px;
    padding: 0 4px;
}}
QWidget#SupervisionStatusBarWidget {{
    background: transparent;
}}
QWidget#SupervisionStatusAlarmsGroup,
QWidget#SupervisionStatusLogGroup {{
    background: transparent;
}}
QLabel#SupervisionStatusRecClock {{
    font-size: 11px;
    padding: 0 2px;
}}

/* ---- Pie de diálogos (workspace manager, etc.) ---- */
QLabel#DialogStatusLabel {{
    background-color: {c['status_bg']};
    color: {c['status_text']};
    border-top: 1px solid {c['border']};
    padding: 8px 12px;
    font-size: 12px;
}}

/* ---- Paneles acoplables ---- */
QDockWidget {{
    titlebar-close-icon: url(none);
    titlebar-normal-icon: url(none);
    color: {c['text']};
}}
QDockWidget::title {{
    background-color: {c['chrome']};
    color: {c['text_primary']};
    padding: 6px 8px;
    border-bottom: 1px solid {c['border']};
    text-align: left;
}}

/* ---- Diálogos y grupos ---- */
QDialog {{
    background-color: {c['chrome']};
    color: {c['text']};
}}
QGroupBox {{
    border: 1px solid {c['border']};
    border-radius: 4px;
    margin-top: 12px;
    padding-top: 8px;
    color: {c['text_primary']};
    font-weight: 600;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 8px;
    padding: 0 4px;
    color: {c['text_primary']};
}}

/* ---- Controles ---- */
QLabel {{
    color: {c['text']};
    background: transparent;
}}
QLineEdit, QSpinBox, QPlainTextEdit, QTextEdit {{
    background-color: {c['input_bg']};
    color: {c['text_primary']};
    border: 1px solid {c['border']};
    border-radius: 3px;
    padding: 4px 8px;
    selection-background-color: {c['selection']};
    selection-color: {sel_fg};
}}
QComboBox {{
    background-color: {c['input_bg']};
    color: {c['text_primary']};
    border: 1px solid {c['border']};
    border-radius: 3px;
    padding: 4px 8px;
    min-height: 24px;
}}
QComboBox:hover, QLineEdit:hover {{
    border-color: {c['accent']};
}}
QComboBox::drop-down {{
    border: none;
    width: 20px;
}}
QComboBox QAbstractItemView {{
    background-color: {c['chrome_alt']};
    color: {c['text_primary']};
    border: 1px solid {c['border']};
    selection-background-color: {c['selection']};
    selection-color: {sel_fg};
}}

QPushButton {{
    background-color: {c['chrome_elevated']};
    color: {c['text_primary']};
    border: 1px solid {c['border']};
    border-radius: 3px;
    padding: 6px 16px;
    min-height: 24px;
}}
QPushButton:hover {{
    background-color: {c['hover']};
    border-color: {c['accent']};
}}
QPushButton:pressed {{
    background-color: {c['selection']};
    color: {sel_fg};
}}
QPushButton:flat {{
    background: transparent;
    border: none;
    padding: 4px;
    min-width: 28px;
    min-height: 28px;
}}
QPushButton:flat:hover {{
    background-color: {c['hover']};
    border-radius: 3px;
}}
QPushButton:flat:pressed {{
    background-color: {c['selection'] if is_dark else c['pressed']};
}}

/* ---- Tablas ---- */
QTableWidget, QTableView {{
    background-color: {c['window']};
    alternate-background-color: {c['chrome_alt']};
    color: {c['text']};
    gridline-color: {c['border']};
    border: 1px solid {c['border']};
    selection-background-color: {c['selection']};
    selection-color: {sel_fg};
}}
QHeaderView::section {{
    background-color: {c['chrome_elevated']};
    color: {c['text_primary']};
    padding: 6px 8px;
    border: none;
    border-right: 1px solid {c['border']};
    border-bottom: 1px solid {c['border']};
}}

QScrollBar:vertical {{
    background: {c['chrome']};
    width: 12px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {c['hover']};
    min-height: 24px;
    border-radius: 4px;
    margin: 2px;
}}
QScrollBar::handle:vertical:hover {{
    background: {c['text_muted']};
}}
QScrollBar:horizontal {{
    background: {c['chrome']};
    height: 12px;
}}
QScrollBar::handle:horizontal {{
    background: {c['hover']};
    min-width: 24px;
    border-radius: 4px;
    margin: 2px;
}}

QSplitter::handle {{
    background-color: {c['border']};
}}
QFrame[frameShape="4"], QFrame[frameShape="5"] {{
    color: {c['border']};
    background: {c['border']};
    max-height: 1px;
}}

QToolTip {{
    background-color: {c['chrome_alt']};
    color: {c['text_primary']};
    border: 1px solid {c['border']};
    padding: 4px 8px;
}}

/* ---- Indicador de documento (esquina menú) ---- */
QWidget#ProjectTitleWidget {{
    background: transparent;
}}
QLabel#ProjectShowNameLabel {{
    color: {c['text_primary']};
    font-size: 12px;
    font-weight: 600;
    background: transparent;
    padding: 0;
}}
QLabel#ProjectFilePathLabel {{
    color: {c['text_muted']};
    font-size: 11px;
    font-weight: 400;
    background: transparent;
    padding: 0;
}}
QLabel#ProjectDirtyDot {{
    color: {c['accent']};
    font-size: 10px;
    background: transparent;
}}
QLabel#ProjectDocumentPathLabel {{
    color: {c['status_muted']};
    font-size: 11px;
    padding: 0 8px;
    background: transparent;
}}
""" + build_module_main_tab_stylesheet(is_dark)


def build_module_main_tab_stylesheet(dark: bool | None = None) -> str:
    """QSS solo para QTabWidget#ModuleMainTabs."""
    is_dark = dark if dark is not None else is_dark_mode()
    c = _tokens(is_dark)
    return f"""
QTabWidget#ModuleMainTabs::pane {{
    border: none;
    border-top: 1px solid {c['border']};
    background-color: {c['window']};
    top: -1px;
}}
QTabWidget#ModuleMainTabs > QTabBar {{
    background-color: {c['chrome']};
    border-bottom: 1px solid {c['border']};
}}
QTabWidget#ModuleMainTabs > QTabBar::tab {{
    background-color: {c['chrome']};
    color: {c['text_muted']};
    padding: 10px 22px;
    margin: 0 1px 0 0;
    min-width: 120px;
    font-size: 13px;
    font-weight: 500;
    border: none;
    border-bottom: 3px solid transparent;
}}
QTabWidget#ModuleMainTabs > QTabBar::tab:selected {{
    background-color: {c['window']};
    color: {c['text_primary']};
    font-size: 13px;
    font-weight: 700;
    border-bottom: 3px solid {c['accent']};
}}
QTabWidget#ModuleMainTabs > QTabBar::tab:hover:!selected {{
    background-color: {c['hover']};
    color: {c['text_primary']};
}}
QTabWidget#ModuleMainTabs > QTabBar::tab:first {{
    margin-left: 4px;
}}
"""


def apply_module_main_tab_styles(tab_widget) -> None:
    """Reaplica estilos de las pestañas centrales de módulo."""
    tab_widget.setStyleSheet(build_module_main_tab_stylesheet())


def apply_project_title_styles(widget) -> None:
    """Reaplica estilos del indicador de documento (p. ej. tras cambio de tema)."""
    from PyQt6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        return
    dark = is_dark_mode(app)
    c = _tokens(dark)
    widget.setStyleSheet(
        f"""
        QWidget#ProjectTitleWidget {{ background: transparent; }}
        QLabel#ProjectShowNameLabel {{
            color: {c['text_primary']};
            font-size: 12px;
            font-weight: 600;
            background: transparent;
        }}
        QLabel#ProjectFilePathLabel {{
            color: {c['text_muted']};
            font-size: 11px;
            background: transparent;
        }}
        QLabel#ProjectDirtyDot {{
            color: {c['accent']};
            font-size: 10px;
            background: transparent;
        }}
        """
    )


def apply_application_chrome(app=None) -> None:
    """Aplica la hoja de estilo IDE a toda la aplicación."""
    application = app or QApplication.instance()
    if application is None:
        return
    dark = is_dark_mode(application)
    application.setStyleSheet(build_ide_stylesheet(dark))


def apply_monitor_config_toolbox_styles(widget) -> None:
    """Cabeceras con apariencia QToolBox nativa (estilo sistema) — acordeón del panel."""
    widget.setStyleSheet("")


def apply_monitor_device_panel_hints(panel) -> None:
    """Textos secundarios del panel Dispositivo (combo + estado)."""
    dark = is_dark_mode()
    c = _tokens(dark)
    panel.setStyleSheet(
        f"""
        QLabel#MonitorDevicePlayHint {{
            color: {c['text_muted']};
            font-size: 11px;
        }}
        QLabel#MonitorDeviceStatusLabel {{
            color: {c['text_muted']};
            font-size: 11px;
        }}
        """
    )


def apply_monitor_info_button_styles(button) -> None:
    """Botón ℹ compacto en paneles Monitor."""
    dark = is_dark_mode()
    c = _tokens(dark)
    button.setStyleSheet(
        f"""
        QToolButton#MonitorInfoButton {{
            border: 1px solid {c['border']};
            border-radius: 11px;
            background-color: {c['chrome_elevated']};
            color: {c['text_muted']};
            font-size: 11px;
            font-weight: bold;
            padding: 0;
        }}
        QToolButton#MonitorInfoButton:hover {{
            background-color: {c['hover']};
            color: {c['text_primary']};
            border-color: {c['text_muted']};
        }}
        QToolButton#MonitorInfoButton:pressed {{
            background-color: {c['selection'] if dark else c['pressed']};
        }}
        """
    )


def apply_monitor_supervision_tree_styles(widget) -> None:
    """Estilos del árbol de supervisión (panel o ventana flotante)."""
    dark = is_dark_mode()
    c = _tokens(dark)
    sel_fg = "#ffffff" if dark else "#000000"
    widget.setStyleSheet(
        f"""
        #MonitorSupervisionToolBtn {{
            background: transparent;
            border: 1px solid transparent;
            border-radius: 3px;
            padding: 0;
        }}
        #MonitorSupervisionToolBtn:hover {{
            background-color: {c['hover']};
            border-color: {c['border']};
        }}
        #MonitorSupervisionToolBtn:disabled {{
            opacity: 0.45;
        }}
        #MonitorSupervisionTree {{
            background-color: {c['window']};
            color: {c['text']};
            border: 1px solid {c['border']};
            border-radius: 4px;
            padding: 2px;
            selection-background-color: {c['selection']};
            selection-color: {sel_fg};
            icon-size: 16px;
        }}
        #MonitorSupervisionTree::item {{
            padding: 1px 2px;
            border-radius: 2px;
        }}
        """
    )


def apply_monitor_freq_manager_styles(widget) -> None:
    """Estilos del gestor de frecuencias (solo barra de iconos)."""
    dark = is_dark_mode()
    c = _tokens(dark)
    widget.setStyleSheet(
        f"""
        #MonitorSupervisionToolBtn {{
            background: transparent;
            border: 1px solid transparent;
            border-radius: 3px;
            padding: 0;
        }}
        #MonitorSupervisionToolBtn:hover {{
            background-color: {c['hover']};
            border-color: {c['border']};
        }}
        """
    )


def apply_monitor_supervision_alarm_window_styles(window) -> None:
    """Estilos ventana flotante de alarmas de supervisión."""
    dark = is_dark_mode()
    c = _tokens(dark)
    window.setStyleSheet(
        f"""
        #MonitorAlarmWindowTitle {{
            color: {c['text_primary']};
            font-size: 12px;
        }}
        """
    )
