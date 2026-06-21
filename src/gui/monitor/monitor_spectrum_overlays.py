"""Sliders rápidos F / SPAN / AMPT sobre el gráfico de espectro."""
from __future__ import annotations

from typing import Callable, Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QSlider,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from core.monitor.amplitude_units import dbm_to_display, display_to_dbm, ref_level_display_range
from core.monitor.display_scale import (
    REF_RANGE_STEPS_DB,
    REF_SCALE_PRESETS,
    ref_range_from_step_index,
    ref_range_step_index,
    slider_value_to_freq,
    slider_value_to_span,
)
from core.monitor.marker_analysis import REF_LEVEL_STEP_COUNT
from core.monitor.monitor_freq_span_logic import (
    active_marker_freq_hz,
    display_span_hz,
    freq_slider_value,
    patch_center_freq,
    patch_manual_span,
    patch_ref_auto,
    patch_selected_freq,
    ref_level_from_step_index,
    ref_level_step_index,
    span_min_hz,
    selected_freq_from_slider_value,
    span_slider_value,
    span_zoom_viewport,
    ui_span_min_hz,
)
from core.monitor.monitor_mode_guard import ModeRestriction, span_requires_analyzer_mode
from core.monitor.monitor_mode_profile import ui_max_span_hz
from core.monitor.spectrum_params import SpectrumParams
from gui.monitor.monitor_ampt_control import populate_ampt_menu
from gui.monitor.monitor_custom_sliders import MonitorLogFreqSlider, MonitorLogSpanSlider
from gui.monitor.monitor_freq_span_controls import MonitorFreqControl, MonitorSpanControl
from gui.monitor.monitor_freq_readout_labels import freq_readout_mode_abbr
from gui.monitor.monitor_status_format import format_freq_compact
from gui.monitor.monitor_slider_readout import MonitorSliderReadout
from gui.monitor.monitor_status_dialogs import edit_ref_level_dialog, edit_ref_range_dialog
from gui.monitor.monitor_vertical_slider_column import COLUMN_WIDTH, build_vertical_slider_column
from i18n.json_translation import tr


_SLIDER_QSS = """
#MonitorOverlayFrame {
    background-color: rgba(8, 12, 18, 210);
    border: 1px solid #3a5060;
    border-radius: 3px;
}
#MonitorOverlayLabel {
    color: #7ec8ff;
    font-size: 9px;
    font-weight: 700;
    min-width: 32px;
}
#MonitorOverlayVLabel {
    color: #7ec8ff;
    font-size: 8px;
    font-weight: 700;
    letter-spacing: 0.5px;
}
#MonitorOverlaySlider::groove:horizontal {
    background: #1a2430;
    height: 8px;
    border-radius: 4px;
}
#MonitorOverlaySlider::handle:horizontal {
    background: #3ecf5a;
    width: 14px;
    height: 18px;
    margin: -6px 0;
    border-radius: 3px;
}
#MonitorOverlaySlider::groove:vertical {
    background: #1a2430;
    width: 10px;
    border-radius: 4px;
}
#MonitorOverlaySlider::handle:vertical {
    background: #ffb347;
    width: 16px;
    height: 12px;
    margin: 0 -4px;
    border-radius: 3px;
}
#MonitorOverlaySlider:disabled::groove:vertical {
    background: #252530;
}
#MonitorOverlaySliderRef::groove:vertical {
    background: #2a2430;
    width: 10px;
    border-radius: 4px;
    border: 1px solid #604830;
}
#MonitorOverlaySliderRef::handle:vertical {
    background: #ffb347;
    width: 16px;
    height: 14px;
    margin: 0 -4px;
    border-radius: 3px;
}
#MonitorOverlaySliderRef[scaleMode="manual"]::handle:vertical {
    background: #ffb347;
}
#MonitorOverlaySliderRef[scaleMode="auto"]::handle:vertical {
    background: #5ec87a;
}
#MonitorOverlaySliderRef[scaleMode="manual"]::groove:vertical {
    background: #2a2430;
    border: 1px solid #604830;
}
#MonitorOverlaySliderRef[scaleMode="auto"]::groove:vertical {
    background: #1a3028;
    border: 1px solid #2a6040;
}
#MonitorOverlaySliderRef[interactive="false"]::handle:vertical {
    background: #5ec87a;
}
#MonitorOverlaySliderRange[scaleMode="auto"]::handle:vertical {
    background: #5a9ec8;
}
#MonitorOverlaySliderRange[scaleMode="manual"]::handle:vertical {
    background: #47c8ff;
}
#MonitorOverlaySliderRange[scaleMode="auto"]::groove:vertical {
    background: #1a2838;
    border: 1px solid #2a5070;
}
#MonitorScaleModeBtn {
    color: #9ec8e8;
    font-size: 7px;
    font-weight: 700;
    border: 1px solid #3a5060;
    border-radius: 2px;
    padding: 0 2px;
    min-height: 14px;
}
#MonitorScaleModeBtn:checked {
    color: #5ec87a;
    border-color: #2a6040;
    background: #1a3028;
}
#MonitorScaleModeBtn:!checked {
    color: #ffb347;
    border-color: #604830;
    background: #2a2430;
}
#MonitorDockPinBtn {
    border: none;
    font-size: 11px;
    padding: 0;
    min-width: 16px;
    max-width: 16px;
}
#MonitorDockPinBtn[pinned="true"] {
    color: #5ec87a;
}
#MonitorDockPinBtn[pinned="false"] {
    color: #8899aa;
}
#MonitorOverlaySliderPreamp::handle:vertical {
    background: #8dff8d;
}
#MonitorOverlaySliderLna::handle:vertical {
    background: #6ec8ff;
}
#MonitorOverlaySliderVga::handle:vertical {
    background: #c8a0ff;
}
#MonitorOverlayReadout {
    color: #7ec8ff;
    font-size: 7px;
    font-weight: 600;
    padding: 0 1px;
}
#MonitorOverlayReadout:hover {
    color: #a8e0ff;
}
#MonitorSpectrumDockPanel {
    background-color: rgba(8, 12, 18, 225);
    border: 1px solid #3a5060;
    border-radius: 4px;
}
#MonitorDockBody {
    background-color: transparent;
    border: none;
}
#MonitorDockTabBtn {
    background-color: #1a2838;
    color: #9ec8e8;
    border: 1px solid #3a5060;
    border-radius: 2px;
    min-width: 22px;
    max-width: 22px;
    font-weight: 700;
    padding: 2px 0;
}
#MonitorDockTabBtn:hover {
    background-color: #243848;
    color: #c8e8ff;
}
#MonitorDockPinBtn {
    background-color: transparent;
    color: #6a8098;
    border: none;
    font-size: 11px;
    padding: 0 4px;
    min-width: 18px;
    max-height: 18px;
}
#MonitorDockPinBtn:checked {
    color: #8dff8d;
}
#MonitorDockModeIndicator {
    border-radius: 5px;
    min-width: 10px;
    max-width: 10px;
    min-height: 10px;
    max-height: 10px;
}
#MonitorDockModeIndicator[dockMode="collapsed"] {
    background-color: #78909c;
    border: 1px solid #a0b0bc;
}
#MonitorDockModeIndicator[dockMode="expanded"] {
    background-color: #4caf50;
    border: 1px solid #7ddf80;
}
#MonitorDockModeIndicator[dockMode="auto"] {
    background-color: #ff9800;
    border: 1px solid #ffcc66;
}
#MonitorSpectrumStatusText {
    color: #7ec8ff;
}
#MonitorSpectrumStatusText[statusTone="auto"] {
    color: #9ec8e8;
    font-style: normal;
}
#MonitorSpectrumStatusText[statusTone="manual"] {
    color: #ffd080;
    font-style: italic;
}
#MonitorSpectrumStatusText[statusTone="special"] {
    color: #ffb890;
    font-weight: 600;
}
#MonitorStatusSeparator {
    background-color: #4a6070;
    min-width: 1px;
    max-width: 1px;
    margin: 3px 2px;
}
#MonitorStatusReadoutBadge {
    color: #dceeff;
    padding: 1px 7px;
    border-radius: 2px;
    font-weight: 700;
    font-size: 8px;
}
#MonitorStatusReadoutBadge[readoutMode="fc"] {
    background-color: #1e4060;
    border: 1px solid #3a7090;
}
#MonitorStatusReadoutBadge[readoutMode="f"] {
    background-color: #503818;
    border: 1px solid #806030;
}
#MonitorOverlaySliderRange::handle:vertical {
    background: #47c8ff;
    width: 16px;
    height: 12px;
    margin: 0 -4px;
    border-radius: 3px;
}
#MonitorOverlaySliderWaterfall::handle:vertical {
    background: #c78dff;
    width: 16px;
    height: 12px;
    margin: 0 -4px;
    border-radius: 3px;
}
#MonitorOverlayMenuBtn {
    background-color: #2a3038;
    color: #c8d0d8;
    border: 1px solid #454d58;
    border-radius: 2px;
    font-weight: 700;
    padding: 0;
    min-width: 20px;
    min-height: 18px;
}
#MonitorOverlayMenuBtn:hover {
    border-color: #0078d4;
}
#MonitorFreqSliderHost {
    border-radius: 4px;
    min-height: 22px;
}
#MonitorFreqSliderHost[readoutMode="fc"] {
    background-color: #1e4060;
    border: 1px solid #3a7090;
}
#MonitorFreqSliderHost[readoutMode="f"] {
    background-color: #503818;
    border: 1px solid #806030;
}
#MonitorSpanSliderHost {
    border-radius: 4px;
    min-height: 22px;
    background-color: #1a2e24;
    border: 1px solid #3a7858;
}
#MonitorSpanSliderHost[sdrMode="false"] #MonitorInlineSliderOverlay {
    color: #c8ffd8;
}
#MonitorSpanSliderHost[sdrMode="true"] {
    background-color: #182040;
    border: 1px solid #4a70b8;
}
#MonitorSpanSliderHost[sdrMode="true"] #MonitorInlineSliderOverlay {
    color: #c8e0ff;
}
#MonitorInlineSliderOverlay {
    color: #eef6ff;
    font-size: 8px;
    font-weight: 700;
    background: transparent;
}
#MonitorOverlaySliderFreq::groove:horizontal {
    background: transparent;
    height: 18px;
    border-radius: 3px;
}
#MonitorOverlaySliderSpan::groove:horizontal {
    background: transparent;
    height: 18px;
    border-radius: 3px;
}
#MonitorOverlaySliderFreq[readoutMode="fc"]::handle:horizontal {
    background: #64b4ff;
    width: 12px;
    height: 16px;
    margin: -4px 0;
    border-radius: 3px;
}
#MonitorOverlaySliderFreq[readoutMode="f"]::handle:horizontal {
    background: #ffc850;
    width: 12px;
    height: 16px;
    margin: -4px 0;
    border-radius: 3px;
}
"""


def _make_slider(orientation: Qt.Orientation) -> QSlider:
    slider = QSlider(orientation)
    slider.setObjectName("MonitorOverlaySlider")
    slider.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    slider.setTracking(True)
    return slider


def _menu_button(parent: QWidget, on_click) -> QToolButton:
    btn = QToolButton(parent)
    btn.setObjectName("MonitorOverlayMenuBtn")
    btn.setText("…")
    btn.setFixedSize(20, 18)
    btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    btn.clicked.connect(on_click)
    return btn


def _polish_widget_property(widget: QWidget) -> None:
    widget.style().unpolish(widget)
    widget.style().polish(widget)


def _format_inline_slider_text(prefix: str, value: str) -> str:
    return f"{prefix}  {value}"


class _MonitorInlineSliderHost(QFrame):
    """Slider horizontal con fondo temático y lectura integrada en una línea."""

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        *,
        host_name: str,
        slider_name: str,
        style_property: str,
        slider_factory=None,
    ) -> None:
        super().__init__(parent)
        self._style_property = style_property
        self.setObjectName(host_name)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(3, 1, 3, 1)
        layout.setSpacing(0)

        factory = slider_factory or MonitorLogFreqSlider
        self.slider = factory(self)
        self.slider.setObjectName(slider_name)
        self.slider.setMinimumHeight(20)
        layout.addWidget(self.slider, stretch=1)

        self._overlay = QLabel(self)
        self._overlay.setObjectName("MonitorInlineSliderOverlay")
        self._overlay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._overlay.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._overlay.setGeometry(self.slider.geometry())
        self._overlay.raise_()

    def set_style_mode(self, mode: str) -> None:
        self.setProperty(self._style_property, mode)
        self.slider.setProperty(self._style_property, mode)
        _polish_widget_property(self)
        _polish_widget_property(self.slider)

    def set_extra_property(self, name: str, value: str) -> None:
        self.setProperty(name, value)
        self.slider.setProperty(name, value)
        _polish_widget_property(self)
        _polish_widget_property(self.slider)

    def set_overlay_line(self, text: str) -> None:
        self._overlay.setText(text)


class _MonitorFreqSliderHost(_MonitorInlineSliderHost):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(
            parent,
            host_name="MonitorFreqSliderHost",
            slider_name="MonitorOverlaySliderFreq",
            style_property="readoutMode",
        )

    def set_readout_mode(self, mode: str) -> None:
        self.set_style_mode(mode)
        if hasattr(self.slider, "set_readout_mode"):
            self.slider.set_readout_mode(mode)

    def set_overlay_text(self, mode_label: str, freq_hz: float) -> None:
        self.set_overlay_line(
            _format_inline_slider_text(mode_label, format_freq_compact(freq_hz))
        )


class _MonitorSpanSliderHost(_MonitorInlineSliderHost):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(
            parent,
            host_name="MonitorSpanSliderHost",
            slider_name="MonitorOverlaySliderSpan",
            style_property="spanMode",
            slider_factory=MonitorLogSpanSlider,
        )

    def set_span_overlay(self, params: SpectrumParams) -> None:
        from core.monitor.display_colors import is_sdr_display_mode

        is_sdr = is_sdr_display_mode(params)
        prefix = "BW" if is_sdr else "SPAN"
        sdr_flag = "true" if is_sdr else "false"
        self.setProperty("sdrMode", sdr_flag)
        self.slider.setProperty("sdrMode", sdr_flag)
        _polish_widget_property(self)
        _polish_widget_property(self.slider)
        if hasattr(self.slider, "set_span_range"):
            self.slider.set_span_range(ui_span_min_hz(params), ui_max_span_hz(params))
        self.set_overlay_line(
            _format_inline_slider_text(prefix, format_freq_compact(display_span_hz(params)))
        )
        self._apply_span_viewport(params)

    def _apply_span_viewport(self, params: SpectrumParams) -> None:
        from core.monitor.display_colors import span_slider_colors

        if hasattr(self.slider, "set_display_colors"):
            self.slider.set_display_colors(span_slider_colors(params))
        if not hasattr(self.slider, "set_viewport"):
            return
        fmin, range_hz, center_ratio, width_ratio = span_zoom_viewport(params)
        self.slider.set_viewport(
            fmin_hz=fmin,
            range_hz=range_hz,
            center_ratio=center_ratio,
            width_ratio=width_ratio,
        )


class MonitorSpectrumSliders(QFrame):
    """Sliders horizontales FC/F y SPAN con menú … (valores en toolbar)."""

    params_changed = pyqtSignal(object)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("MonitorOverlayFrame")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(_SLIDER_QSS)
        self._params = SpectrumParams()
        self._syncing_freq = False
        self._syncing_span = False
        self._cached_span_mode = ""
        self._cached_span_hz = -1.0
        self._mode_warning_callback = None

        self._freq_menu_host = MonitorFreqControl(compact=True, parent=self)
        self._freq_menu_host.hide()
        self._freq_menu_host.bind_patch(self._patch)

        self._span_menu_host = MonitorSpanControl(compact=True, parent=self)
        self._span_menu_host.hide()
        self._span_menu_host.bind_patch(self._patch)

        root = QHBoxLayout(self)
        root.setContentsMargins(6, 4, 6, 4)
        root.setSpacing(8)

        self._freq_host = _MonitorFreqSliderHost(self)
        self._freq_host.setMinimumWidth(180)
        self._freq_host.slider.setRange(0, 10_000)
        self._freq_host.slider.valueChanged.connect(self._on_freq_slider)
        self._freq_host.slider.sliderPressed.connect(self._release_toolbar_editing)
        self._freq_menu_btn = _menu_button(self, self._popup_freq_menu)

        self._span_host = _MonitorSpanSliderHost(self)
        self._span_host.setMinimumWidth(180)
        self._span_host.slider.setRange(0, 10_000)
        self._span_host.slider.valueChanged.connect(self._on_span_slider)
        self._span_host.slider.span_wheel.connect(self._on_span_wheel)
        self._span_host.slider.sliderPressed.connect(self._release_toolbar_editing)
        self._span_menu_btn = _menu_button(self, self._popup_span_menu)

        root.addWidget(self._freq_host, stretch=2)
        root.addWidget(self._freq_menu_btn)
        root.addWidget(self._span_host, stretch=2)
        root.addWidget(self._span_menu_btn)
        self._apply_tooltips()

    def recargar_textos(self) -> None:
        self.set_params(self._params)
        self._apply_tooltips()

    def _apply_tooltips(self) -> None:
        freq_tip = tr("monitor_tip_overlay_f") if self._params.freq_readout == "f" else tr("monitor_tip_overlay_fc")
        self._freq_host.setToolTip(freq_tip)
        self._freq_host.slider.setToolTip(freq_tip)
        self._freq_menu_btn.setToolTip(tr("monitor_tip_fc_menu"))
        from core.monitor.display_colors import is_sdr_display_mode

        span_tip = (
            tr("monitor_tip_overlay_span_sdr")
            if is_sdr_display_mode(self._params)
            else tr("monitor_tip_overlay_span")
        )
        self._span_host.setToolTip(span_tip)
        self._span_host.slider.setToolTip(span_tip)
        self._span_menu_btn.setToolTip(tr("monitor_tip_span_menu"))

    def bind_toolbar(self, toolbar) -> None:
        self._toolbar = toolbar
        span = getattr(toolbar, "_span", None)
        if span is not None and hasattr(span, "bind_mode_warning"):
            span.bind_mode_warning(self._emit_mode_warning)

    def bind_mode_warning(self, callback) -> None:
        self._mode_warning_callback = callback
        self._span_menu_host.bind_mode_warning(callback)

    def _emit_mode_warning(self, restriction: ModeRestriction | None) -> None:
        if restriction is not None and self._mode_warning_callback is not None:
            self._mode_warning_callback(restriction)

    def _release_toolbar_editing(self) -> None:
        toolbar = getattr(self, "_toolbar", None)
        if toolbar is None:
            return
        toolbar.commit_numeric_editing()

    def _update_span_slider(self, params: SpectrumParams) -> None:
        self._span_host._apply_span_viewport(params)
        target = span_slider_value(params)
        if self._span_host.slider.value() == target:
            return
        self._syncing_span = True
        try:
            self._span_host.slider.blockSignals(True)
            self._span_host.slider.setValue(target)
        finally:
            self._span_host.slider.blockSignals(False)
            self._syncing_span = False

    def _on_span_slider(self, value: int) -> None:
        if self._syncing_span:
            return
        hz = slider_value_to_span(
            value,
            max_span_hz=ui_max_span_hz(self._params),
            min_span_hz=ui_span_min_hz(self._params),
        )
        self._emit_mode_warning(span_requires_analyzer_mode(self._params, hz))
        updated = patch_manual_span(self._params, hz)
        self._params = updated
        self._cached_span_mode = updated.span_mode
        self._cached_span_hz = display_span_hz(updated)
        self.params_changed.emit(updated)

    def _on_span_wheel(self, direction: int) -> None:
        if self._syncing_span:
            return
        from core.monitor.display_scale import step_span_hz

        current_hz = display_span_hz(self._params)
        requested_hz = step_span_hz(max(current_hz, ui_span_min_hz(self._params)), direction)
        self._emit_mode_warning(span_requires_analyzer_mode(self._params, requested_hz))
        updated = patch_manual_span(self._params, requested_hz)
        self._params = updated
        self._cached_span_mode = updated.span_mode
        self._cached_span_hz = display_span_hz(updated)
        self.params_changed.emit(updated)

    def _update_freq_slider(self, params: SpectrumParams) -> None:
        target = freq_slider_value(params)
        if self._freq_host.slider.value() == target:
            return
        self._syncing_freq = True
        try:
            self._freq_host.slider.blockSignals(True)
            self._freq_host.slider.setValue(target)
        finally:
            self._freq_host.slider.blockSignals(False)
            self._syncing_freq = False

    def _patch(self, updated: SpectrumParams) -> None:
        self._params = updated
        self.set_params(updated)
        self.params_changed.emit(updated)

    def _popup_freq_menu(self) -> None:
        self._freq_menu_host.set_params(self._params)
        self._freq_menu_host.show_popup_menu(
            self._freq_menu_btn.mapToGlobal(self._freq_menu_btn.rect().bottomLeft())
        )

    def _popup_span_menu(self) -> None:
        self._span_menu_host.set_params(self._params)
        self._span_menu_host.show_popup_menu(
            self._span_menu_btn.mapToGlobal(self._span_menu_btn.rect().bottomLeft())
        )

    def set_params(self, params: SpectrumParams) -> None:
        prev = self._params
        self._params = params.copy()
        self._freq_host.set_readout_mode(params.freq_readout)
        self._freq_host.set_overlay_text(
            freq_readout_mode_abbr(params),
            active_marker_freq_hz(params),
        )
        self._span_host.set_span_overlay(params)

        readout_changed = prev.freq_readout != params.freq_readout
        span_hz = display_span_hz(params)
        center_moved = abs(params.center_freq_hz - prev.center_freq_hz) > 0.5
        capture_changed = prev.capture_mode != params.capture_mode
        if params.freq_readout == "f":
            if (
                readout_changed
                or abs(params.selected_freq_hz - prev.selected_freq_hz) > 0.5
                or abs(span_hz - display_span_hz(prev)) > 0.5
                or center_moved
                or capture_changed
            ):
                self._update_freq_slider(params)
        elif readout_changed or center_moved:
            self._update_freq_slider(params)

        mode_changed = prev.operating_mode != params.operating_mode
        display_colors_changed = any(
            getattr(prev, key, "") != getattr(params, key, "")
            for key in (
                "display_span_viewport_color",
                "display_span_viewport_hi_color",
                "display_span_track_color",
                "display_span_handle_color",
                "display_trace_color",
                "display_sdr_span_viewport_color",
                "display_sdr_span_viewport_hi_color",
                "display_sdr_span_track_color",
                "display_sdr_span_handle_color",
                "display_sdr_trace_color",
            )
        )
        if (
            mode_changed
            or capture_changed
            or center_moved
            or display_colors_changed
            or params.span_mode != self._cached_span_mode
            or abs(span_hz - self._cached_span_hz) > 1.0
        ):
            self._cached_span_mode = params.span_mode
            self._cached_span_hz = span_hz
            self._update_span_slider(params)

        self._apply_tooltips()

    def _on_freq_slider(self, value: int) -> None:
        if self._syncing_freq:
            return
        if self._params.freq_readout == "f":
            hz = selected_freq_from_slider_value(self._params, value)
            updated = patch_selected_freq(self._params, hz, clamp_visible=True)
        else:
            updated = patch_center_freq(self._params, slider_value_to_freq(value))
        self._params = updated
        self.params_changed.emit(updated)


class MonitorAmptSlider(QFrame):
    """Slider vertical nivel de referencia (REF) + lectura clicable."""

    params_changed = pyqtSignal(object)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("MonitorOverlayFrame")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(_SLIDER_QSS)
        self._params = SpectrumParams()
        self._syncing = False
        self.setMinimumWidth(COLUMN_WIDTH)

        self._label = QLabel(tr("monitor_overlay_ref"), self)
        self._label.setObjectName("MonitorOverlayVLabel")
        self._label.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._label.customContextMenuRequested.connect(self._show_ampt_menu_at_label)

        self._slider = _make_slider(Qt.Orientation.Vertical)
        self._slider.setObjectName("MonitorOverlaySliderRef")
        self._slider.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._slider.setMinimumHeight(100)
        self._slider.setRange(0, REF_LEVEL_STEP_COUNT - 1)
        self._slider.setSingleStep(1)
        self._slider.setPageStep(5)
        self._slider.setTickPosition(QSlider.TickPosition.TicksBothSides)
        self._slider.setTickInterval(10)
        self._slider.setInvertedAppearance(True)
        self._slider.valueChanged.connect(self._on_slider)

        self._readout = MonitorSliderReadout(parent=self)
        self._readout.clicked.connect(self._edit_ref)
        self._readout.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._readout.customContextMenuRequested.connect(self._show_ampt_menu_at_readout)

        col_layout = build_vertical_slider_column(
            self, label=self._label, slider=self._slider, readout=self._readout
        )
        self._mode_btn = QToolButton(self)
        self._mode_btn.setObjectName("MonitorScaleModeBtn")
        self._mode_btn.setCheckable(True)
        self._mode_btn.setFixedHeight(14)
        self._mode_btn.setMinimumWidth(COLUMN_WIDTH - 6)
        self._mode_btn.clicked.connect(self._toggle_scale_mode)
        col_layout.addWidget(self._mode_btn, 0, Qt.AlignmentFlag.AlignHCenter)
        self._apply_tooltips()

    def recargar_textos(self) -> None:
        self._label.setText(tr("monitor_overlay_ref"))
        self.set_params(self._params)
        self._apply_tooltips()

    def _scale_mode_label(self) -> str:
        return tr("monitor_scale_mode_auto") if self._params.ref_scale_auto else tr("monitor_scale_mode_manual")

    def _readout_text(self) -> str:
        if self._params.ref_scale_auto:
            return tr("monitor_ampt_auto")
        unit = self._params.amplitude_unit
        from core.monitor.amplitude_units import amplitude_axis_label, format_amplitude_value

        display = dbm_to_display(
            self._params.ref_level_dbm, unit, ref_offset_db=self._params.ref_offset_db
        )
        return format_amplitude_value(display, unit)

    def _apply_tooltips(self) -> None:
        tip = tr("monitor_tip_overlay_ref_mode").format(mode=self._scale_mode_label())
        self._label.setToolTip(tip + " · " + tr("monitor_tip_ampt_menu_rclick"))
        self._slider.setToolTip(tip)
        self._readout.setToolTip(tr("monitor_tip_status_edit_ref"))

    def _apply_scale_mode_style(self) -> None:
        auto = self._params.ref_scale_auto
        mode = "auto" if auto else "manual"
        self._slider.setProperty("scaleMode", mode)
        self._slider.setProperty("interactive", "false" if auto else "true")
        self._slider.setEnabled(not auto)
        self._slider.style().unpolish(self._slider)
        self._slider.style().polish(self._slider)
        self._mode_btn.blockSignals(True)
        self._mode_btn.setChecked(auto)
        self._mode_btn.setText(tr("monitor_ampt_auto") if auto else tr("monitor_scale_mode_manual"))
        self._mode_btn.blockSignals(False)
        self._mode_btn.setToolTip(tr("monitor_tip_scale_mode_btn"))

    def _toggle_scale_mode(self) -> None:
        self._patch(patch_ref_auto(self._params, enabled=self._mode_btn.isChecked()))

    def set_params(self, params: SpectrumParams) -> None:
        self._syncing = True
        self._params = params.copy()
        unit = params.amplitude_unit
        idx = ref_level_step_index(
            params.ref_level_dbm,
            unit=unit,
            ref_offset_db=params.ref_offset_db,
        )
        self._slider.blockSignals(True)
        self._slider.setValue(idx)
        self._slider.blockSignals(False)
        self._readout.setText(self._readout_text())
        self._apply_scale_mode_style()
        self._apply_tooltips()
        self._syncing = False

    def _patch(self, updated: SpectrumParams) -> None:
        self._params = updated
        self.set_params(updated)
        self.params_changed.emit(updated)

    def _on_slider(self, value: int) -> None:
        if self._syncing or self._params.ref_scale_auto:
            return
        updated = self._params.copy()
        updated.ref_scale_auto = False
        updated.ampt_mode = "ref_level"
        unit = updated.amplitude_unit
        updated.ref_level_dbm = ref_level_from_step_index(
            value,
            unit=unit,
            ref_offset_db=updated.ref_offset_db,
        )
        self._params = updated
        self._readout.setText(self._readout_text())
        self.params_changed.emit(updated)

    def _edit_ref(self) -> None:
        updated = edit_ref_level_dialog(self._params, parent=self.window())
        if updated is not None:
            self._patch(updated)

    def _show_ampt_menu_at_label(self, pos) -> None:
        menu = QMenu(self)
        populate_ampt_menu(menu, self._params, patch=self._patch, parent=self)
        menu.exec(self._label.mapToGlobal(pos))

    def _show_ampt_menu_at_readout(self, pos) -> None:
        menu = QMenu(self)
        populate_ampt_menu(menu, self._params, patch=self._patch, parent=self)
        menu.exec(self._readout.mapToGlobal(pos))


class MonitorVRangeSlider(QFrame):
    """Slider vertical resolución (RES) con marcas discretas + lectura clicable."""

    params_changed = pyqtSignal(object)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("MonitorOverlayFrame")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(_SLIDER_QSS)
        self._params = SpectrumParams()
        self._syncing = False
        self.setMinimumWidth(COLUMN_WIDTH)

        self._label = QLabel(tr("monitor_overlay_res"), self)
        self._label.setObjectName("MonitorOverlayVLabel")
        self._label.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._label.customContextMenuRequested.connect(self._show_range_menu_at_label)

        self._slider = _make_slider(Qt.Orientation.Vertical)
        self._slider.setObjectName("MonitorOverlaySliderRange")
        self._slider.setMinimumHeight(100)
        self._slider.setRange(0, max(0, len(REF_RANGE_STEPS_DB) - 1))
        self._slider.setSingleStep(1)
        self._slider.setPageStep(1)
        self._slider.setTickPosition(QSlider.TickPosition.TicksBothSides)
        self._slider.setTickInterval(1)
        self._slider.setInvertedAppearance(False)
        self._slider.valueChanged.connect(self._on_slider)

        self._readout = MonitorSliderReadout(parent=self)
        self._readout.clicked.connect(self._edit_range)
        self._readout.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._readout.customContextMenuRequested.connect(self._show_range_menu_at_readout)

        col_layout = build_vertical_slider_column(
            self, label=self._label, slider=self._slider, readout=self._readout
        )
        self._mode_btn = QToolButton(self)
        self._mode_btn.setObjectName("MonitorScaleModeBtn")
        self._mode_btn.setCheckable(True)
        self._mode_btn.setFixedHeight(14)
        self._mode_btn.setMinimumWidth(COLUMN_WIDTH - 6)
        self._mode_btn.clicked.connect(self._toggle_scale_mode)
        col_layout.addWidget(self._mode_btn, 0, Qt.AlignmentFlag.AlignHCenter)
        self._apply_tooltips()

    def recargar_textos(self) -> None:
        self._label.setText(tr("monitor_overlay_res"))
        self.set_params(self._params)
        self._apply_tooltips()

    def _scale_mode_label(self) -> str:
        return tr("monitor_scale_mode_auto") if self._params.ref_scale_auto else tr("monitor_scale_mode_manual")

    def _readout_text(self) -> str:
        if self._params.ref_scale_auto:
            return tr("monitor_ampt_auto")
        db_div = self._params.ref_range_db / max(self._params.vertical_divisions, 1)
        return tr("monitor_readout_res_compact").format(
            range_db=f"{self._params.ref_range_db:.0f}",
            db_div=f"{db_div:.0f}",
        )

    def _apply_tooltips(self) -> None:
        tip = tr("monitor_tip_overlay_res_mode").format(mode=self._scale_mode_label())
        self._label.setToolTip(tip + " · " + tr("monitor_tip_range_menu_rclick"))
        self._slider.setToolTip(tip)
        self._readout.setToolTip(tr("monitor_tip_status_edit_res"))

    def _apply_scale_mode_style(self) -> None:
        mode = "auto" if self._params.ref_scale_auto else "manual"
        auto = self._params.ref_scale_auto
        self._slider.setProperty("scaleMode", mode)
        self._slider.setProperty("interactive", "false" if auto else "true")
        self._slider.setEnabled(True)
        self._slider.style().unpolish(self._slider)
        self._slider.style().polish(self._slider)
        self._mode_btn.blockSignals(True)
        self._mode_btn.setChecked(auto)
        self._mode_btn.setText(tr("monitor_ampt_auto") if auto else tr("monitor_scale_mode_manual"))
        self._mode_btn.blockSignals(False)
        self._mode_btn.setToolTip(tr("monitor_tip_scale_mode_btn"))

    def _toggle_scale_mode(self) -> None:
        self._patch(patch_ref_auto(self._params, enabled=self._mode_btn.isChecked()))

    def set_params(self, params: SpectrumParams) -> None:
        self._syncing = True
        self._params = params.copy()
        self._slider.blockSignals(True)
        self._slider.setValue(ref_range_step_index(params.ref_range_db))
        self._slider.blockSignals(False)
        self._readout.setText(self._readout_text())
        self._apply_scale_mode_style()
        self._apply_tooltips()
        self._syncing = False

    def _patch(self, updated: SpectrumParams) -> None:
        self._params = updated
        self.set_params(updated)
        self.params_changed.emit(updated)

    def _on_slider(self, value: int) -> None:
        if self._syncing or self._params.ref_scale_auto:
            return
        range_db = ref_range_from_step_index(value)
        preset = min(REF_SCALE_PRESETS, key=lambda p: abs(p[0] - range_db))
        updated = self._params.copy()
        updated.ref_scale_auto = False
        updated.ampt_mode = "ref_range"
        updated.ref_range_db = range_db
        updated.vertical_divisions = max(1, int(round(range_db / max(preset[1], 0.1))))
        self._patch(updated)

    def _edit_range(self) -> None:
        updated = edit_ref_range_dialog(self._params, parent=self.window())
        if updated is not None:
            self._patch(updated)

    def _enable_auto(self) -> None:
        updated = self._params.copy()
        updated.ref_scale_auto = True
        updated.ampt_mode = "ref_level"
        self._patch(updated)

    def _apply_range_preset(self, range_db: float, db_div: float) -> None:
        updated = self._params.copy()
        updated.ref_scale_auto = False
        updated.ampt_mode = "ref_range"
        updated.ref_range_db = range_db
        updated.vertical_divisions = max(1, int(round(range_db / max(db_div, 0.1))))
        self._patch(updated)

    def _build_range_menu(self) -> QMenu:
        menu = QMenu(self)
        act_auto = menu.addAction(tr("monitor_ampt_auto"))
        act_auto.setCheckable(True)
        act_auto.setChecked(self._params.ref_scale_auto)
        act_auto.triggered.connect(lambda: self._enable_auto())
        range_menu = menu.addMenu(tr("monitor_tb_ampt_ref_range"))
        for range_db, db_div in REF_SCALE_PRESETS:
            label = tr("monitor_ref_range_preset").format(
                range=f"{range_db:.0f}",
                db_div=f"{db_div:.0f}",
            )
            act = range_menu.addAction(label)
            act.setCheckable(True)
            act.setChecked(abs(self._params.ref_range_db - range_db) < 0.5)
            act.triggered.connect(
                lambda _c=False, r=range_db, d=db_div: self._apply_range_preset(r, d)
            )
        return menu

    def _show_range_menu_at_label(self, pos) -> None:
        self._build_range_menu().exec(self._label.mapToGlobal(pos))

    def _show_range_menu_at_readout(self, pos) -> None:
        self._build_range_menu().exec(self._readout.mapToGlobal(pos))
