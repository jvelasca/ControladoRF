"""Menús RBW / VBW / barrido / traza compartidos (toolbar y franja de estado)."""

from __future__ import annotations



from typing import Callable, Optional, Union



from PyQt6.QtCore import QTimer

from PyQt6.QtWidgets import QInputDialog, QMenu, QWidget



from core.monitor.monitor_bw_sweep_logic import (

    DETECTORS,

    RBW_PRESETS_HZ,

    SWEEP_TIME_PRESETS_MS,

    SWEEP_TRIGGER_MODES,

    SWEEP_TRIGGER_PERIODS_SEC,

    TRACE_MODES,

    patch_detector,

    patch_rbw_auto,

    patch_rbw_hz,

    patch_rbw_manual,

    patch_fft_size,

    patch_fft_auto,

    patch_fft_manual,

    patch_sweep_auto,

    patch_sweep_time_ms,

    patch_sweep_trigger_mode,

    patch_sweep_trigger_period,

    patch_trace_mode,

    patch_trace_smooth_auto,
    patch_trace_smooth_manual,
    patch_trace_smooth_bins,

)

from core.monitor.monitor_bw_profile import (
    IQ_FFT_PRESETS,
    fft_resolution_auto,
    resolution_preset_selected,
    smooth_preset_selected,
    smooth_presets_for_params,
    sweep_time_preset_selected,
    uses_iq_resolution,
)

from core.monitor.monitor_format import format_bw_hz, format_sweep_ms

from core.monitor.spectrum_params import SpectrumParams

from i18n.json_translation import tr



ParamsSupplier = Union[SpectrumParams, Callable[[], SpectrumParams]]





def _resolve_params(params: ParamsSupplier) -> SpectrumParams:

    current = params() if callable(params) else params

    return current.copy()





def _defer_patch(

    patch: Callable[[SpectrumParams], None],

    updated: SpectrumParams | Callable[[], SpectrumParams],

) -> None:

    def _apply() -> None:

        snapshot = updated() if callable(updated) else updated.copy()

        patch(snapshot)



    QTimer.singleShot(0, _apply)





def _defer_patch_from(

    patch: Callable[[SpectrumParams], None],

    params: ParamsSupplier,

    factory: Callable[..., SpectrumParams],

    **kwargs,

) -> None:

    """Aplica parche con parámetros actuales (no los del momento de abrir el menú)."""

    _defer_patch(patch, lambda: factory(_resolve_params(params), **kwargs))





def populate_fft_menu(
    menu: QMenu,
    params: ParamsSupplier,
    patch: Callable[[SpectrumParams], None],
    *,
    parent: Optional[QWidget] = None,
) -> None:
    base = _resolve_params(params)
    auto_on = fft_resolution_auto(base)
    act_auto = menu.addAction(tr("monitor_tb_bw_auto"))
    act_auto.setCheckable(True)
    act_auto.setChecked(auto_on)
    act_auto.triggered.connect(
        lambda: _defer_patch_from(patch, params, patch_fft_auto, enabled=True)
    )
    act_manual = menu.addAction(tr("monitor_tb_bw_manual"))
    act_manual.setCheckable(True)
    act_manual.setChecked(not auto_on)
    act_manual.triggered.connect(
        lambda: _defer_patch_from(patch, params, patch_fft_manual)
    )
    menu.addSeparator()
    for n in IQ_FFT_PRESETS:
        act = menu.addAction(str(n))
        act.setCheckable(True)
        act.setChecked(resolution_preset_selected(base, fft_size=n))
        act.triggered.connect(
            lambda _c=False, pts=n: _defer_patch_from(patch, params, patch_fft_size, fft_size=pts)
        )


def populate_rbw_iq_menu(
    menu: QMenu,
    params: ParamsSupplier,
    patch: Callable[[SpectrumParams], None],
    *,
    parent: Optional[QWidget] = None,
) -> None:
    """Modo IQ: RBW = SR/FFT (derivado). Solo AUTO/MANUAL de resolución (FFT)."""
    del parent
    base = _resolve_params(params)
    auto_on = fft_resolution_auto(base)
    act_auto = menu.addAction(tr("monitor_tb_bw_auto"))
    act_auto.setCheckable(True)
    act_auto.setChecked(auto_on)
    act_auto.triggered.connect(
        lambda: _defer_patch_from(patch, params, patch_fft_auto, enabled=True)
    )
    act_manual = menu.addAction(tr("monitor_tb_bw_manual"))
    act_manual.setCheckable(True)
    act_manual.setChecked(not auto_on)
    act_manual.triggered.connect(
        lambda: _defer_patch_from(patch, params, patch_fft_manual)
    )


def populate_rbw_sweep_menu(
    menu: QMenu,
    params: ParamsSupplier,
    patch: Callable[[SpectrumParams], None],
    *,
    parent: Optional[QWidget] = None,
) -> None:
    base = _resolve_params(params)
    act_auto = menu.addAction(tr("monitor_tb_bw_auto"))
    act_auto.setCheckable(True)
    act_auto.setChecked(base.rbw_auto)
    act_auto.triggered.connect(
        lambda: _defer_patch_from(patch, params, patch_rbw_auto, enabled=True)
    )
    act_manual = menu.addAction(tr("monitor_tb_bw_manual"))
    act_manual.setCheckable(True)
    act_manual.setChecked(not base.rbw_auto)
    act_manual.triggered.connect(
        lambda: _defer_patch_from(patch, params, patch_rbw_manual)
    )
    menu.addSeparator()
    for hz in RBW_PRESETS_HZ:
        act = menu.addAction(format_bw_hz(hz))
        act.setCheckable(True)
        act.setChecked(resolution_preset_selected(base, rbw_hz=hz))
        act.triggered.connect(
            lambda _c=False, v=hz: _defer_patch_from(patch, params, patch_rbw_hz, rbw_hz=v)
        )


def populate_rbw_menu(

    menu: QMenu,

    params: ParamsSupplier,

    patch: Callable[[SpectrumParams], None],

    *,

    parent: Optional[QWidget] = None,

) -> None:

    base = _resolve_params(params)
    if uses_iq_resolution(base):
        populate_rbw_iq_menu(menu, params, patch, parent=parent)
    else:
        populate_rbw_sweep_menu(menu, params, patch, parent=parent)


def populate_vbw_menu(

    menu: QMenu,

    params: ParamsSupplier,

    patch: Callable[[SpectrumParams], None],

) -> None:

    base = _resolve_params(params)

    act_auto = menu.addAction(tr("monitor_lcd_smooth_off"))

    act_auto.setCheckable(True)

    act_auto.setChecked(base.trace_smooth_auto)

    act_auto.triggered.connect(

        lambda: _defer_patch_from(patch, params, patch_trace_smooth_auto, enabled=True)

    )



    act_manual = menu.addAction(tr("monitor_tb_bw_manual"))

    act_manual.setCheckable(True)

    act_manual.setChecked(not base.trace_smooth_auto)

    act_manual.triggered.connect(

        lambda: _defer_patch_from(patch, params, patch_trace_smooth_manual)

    )



    menu.addSeparator()



    for bins in smooth_presets_for_params(base):

        if bins <= 1:

            continue

        act = menu.addAction(f"×{bins}")

        act.setCheckable(True)

        act.setChecked(smooth_preset_selected(base, bins))

        act.triggered.connect(

            lambda _c=False, b=bins: _defer_patch_from(patch, params, patch_trace_smooth_bins, bins=b)

        )





def populate_sweep_menu(

    menu: QMenu,

    params: ParamsSupplier,

    patch: Callable[[SpectrumParams], None],

) -> None:

    base = _resolve_params(params)

    act_auto = menu.addAction(tr("monitor_tb_sweep_auto"))

    act_auto.setCheckable(True)

    act_auto.setChecked(base.sweep_auto)

    act_auto.triggered.connect(

        lambda: _defer_patch_from(patch, params, patch_sweep_auto, enabled=True)

    )



    act_manual = menu.addAction(tr("monitor_tb_sweep_manual"))

    act_manual.setCheckable(True)

    act_manual.setChecked(not base.sweep_auto)

    act_manual.triggered.connect(

        lambda: _defer_patch_from(patch, params, patch_sweep_auto, enabled=False)

    )



    preset_menu = menu.addMenu(tr("monitor_tb_sweep_manual"))

    for ms in SWEEP_TIME_PRESETS_MS:

        act = preset_menu.addAction(format_sweep_ms(ms))

        act.setCheckable(True)

        act.setChecked(sweep_time_preset_selected(base, ms))

        act.triggered.connect(

            lambda _c=False, v=ms: _defer_patch_from(patch, params, patch_sweep_time_ms, sweep_ms=v)

        )



    menu.addSeparator()

    trigger_menu = menu.addMenu(tr("monitor_tb_sweep_trigger_mode"))

    for mode in SWEEP_TRIGGER_MODES:

        act = trigger_menu.addAction(tr(f"monitor_sweep_trigger_{mode}"))

        act.setCheckable(True)

        act.setChecked(base.sweep_trigger_mode == mode)

        act.triggered.connect(

            lambda _c=False, m=mode: _defer_patch_from(patch, params, patch_sweep_trigger_mode, mode=m)

        )



    period_menu = menu.addMenu(tr("monitor_tb_sweep_trigger_period"))

    for sec in SWEEP_TRIGGER_PERIODS_SEC:

        label = tr("monitor_sweep_trigger_period_sec", sec=sec)

        act = period_menu.addAction(label)

        act.setCheckable(True)

        act.setChecked(abs(base.sweep_trigger_period_sec - sec) < 0.01)

        act.triggered.connect(

            lambda _c=False, s=sec: _defer_patch_from(

                patch, params, patch_sweep_trigger_period, period_sec=s

            )

        )





def populate_trace_menu(

    menu: QMenu,

    params: ParamsSupplier,

    patch: Callable[[SpectrumParams], None],

) -> None:

    base = _resolve_params(params)

    for mode in TRACE_MODES:

        act = menu.addAction(tr(f"monitor_trace_{mode}"))

        act.setCheckable(True)

        act.setChecked(base.trace_mode == mode)

        act.triggered.connect(

            lambda _c=False, m=mode: _defer_patch_from(patch, params, patch_trace_mode, mode=m)

        )





def populate_detector_menu(

    menu: QMenu,

    params: ParamsSupplier,

    patch: Callable[[SpectrumParams], None],

) -> None:

    base = _resolve_params(params)

    for detector in DETECTORS:

        act = menu.addAction(tr(f"monitor_detector_{detector}"))

        act.setCheckable(True)

        act.setChecked(base.detector == detector)

        act.triggered.connect(

            lambda _c=False, d=detector: _defer_patch_from(patch, params, patch_detector, detector=d)

        )





def _pick_trace_mode(

    parent: Optional[QWidget],

    params: ParamsSupplier,

    patch: Callable[[SpectrumParams], None],

) -> None:

    base = _resolve_params(params)

    keys = list(TRACE_MODES)

    items = [tr(f"monitor_trace_{k}") for k in keys]

    current = keys.index(base.trace_mode) if base.trace_mode in keys else 0

    choice, ok = QInputDialog.getItem(

        parent,

        tr("monitor_tb_trace_mode"),

        tr("monitor_tb_trace_mode"),

        items,

        current,

        False,

    )

    if ok and choice in items:

        mode = keys[items.index(choice)]

        _defer_patch_from(patch, params, patch_trace_mode, mode=mode)





def _pick_detector(

    parent: Optional[QWidget],

    params: ParamsSupplier,

    patch: Callable[[SpectrumParams], None],

) -> None:

    base = _resolve_params(params)

    keys = list(DETECTORS)

    items = [tr(f"monitor_detector_{k}") for k in keys]

    current = keys.index(base.detector) if base.detector in keys else 0

    choice, ok = QInputDialog.getItem(

        parent,

        tr("monitor_tb_trace_detector"),

        tr("monitor_tb_trace_detector"),

        items,

        current,

        False,

    )

    if ok and choice in items:

        detector = keys[items.index(choice)]

        _defer_patch_from(patch, params, patch_detector, detector=detector)


def populate_bb_filter_menu(
    menu: QMenu,
    get_params: Callable[[], SpectrumParams],
    patch: Callable[[SpectrumParams], None],
    *,
    parent: Optional[QWidget] = None,
) -> None:
    from core.monitor.hackrf_baseband import (
        baseband_filter_choices_for_sample_rate,
        format_baseband_filter_mhz,
    )
    from core.monitor.monitor_iq_rf_logic import (
        patch_baseband_filter_auto,
        patch_baseband_filter_hz,
    )

    params = get_params()
    auto_act = menu.addAction(tr("monitor_bb_filter_auto"))
    auto_act.setCheckable(True)
    auto_act.setChecked(params.baseband_filter_auto)
    auto_act.triggered.connect(
        lambda: _defer_patch_from(patch, get_params(), patch_baseband_filter_auto, enabled=True)
    )
    menu.addSeparator()
    for bw_hz in baseband_filter_choices_for_sample_rate(params.sample_rate_hz):
        label = f"{format_baseband_filter_mhz(bw_hz)} MHz"
        act = menu.addAction(label)
        act.setCheckable(True)
        act.setChecked(
            not params.baseband_filter_auto
            and int(params.baseband_filter_bw_hz) == int(bw_hz)
        )
        act.triggered.connect(
            lambda _c=False, hz=bw_hz: _defer_patch_from(
                patch, get_params(), patch_baseband_filter_hz, bandwidth_hz=float(hz)
            )
        )

