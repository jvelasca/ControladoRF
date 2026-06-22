"""Menú contextual compartido de SPAN / BW (toolbar, overlay, franja estado)."""
from __future__ import annotations

from typing import Callable, Optional

from PyQt6.QtWidgets import QMenu, QWidget

from core.monitor.monitor_freq_span_logic import patch_span_mode
from core.monitor.monitor_mode_guard import ModeRestriction, span_mode_requires_analyzer_mode
from core.monitor.spectrum_params import SpectrumParams
from i18n.json_translation import tr

SPAN_MODES = ("manual", "full", "zero", "last")


def populate_span_menu(
    menu: QMenu,
    params: SpectrumParams,
    *,
    patch: Callable[[SpectrumParams], None],
    parent: Optional[QWidget] = None,
    mode_warning: Optional[Callable[[ModeRestriction | None], None]] = None,
) -> None:
    """Menú … SPAN — modos de lapso y edición manual."""

    def apply(updated: SpectrumParams) -> None:
        patch(updated)

    def warn(restriction: ModeRestriction | None) -> None:
        if mode_warning is not None:
            mode_warning(restriction)

    for mode in SPAN_MODES:
        act = menu.addAction(tr(f"monitor_span_mode_{mode}"))
        act.setCheckable(True)
        act.setChecked(params.span_mode == mode)

        def _set_mode(_checked: bool = False, m: str = mode) -> None:
            warn(span_mode_requires_analyzer_mode(params, m))
            apply(patch_span_mode(params, m))

        act.triggered.connect(_set_mode)

    menu.addSeparator()
    menu.addAction(
        tr("monitor_status_dialog_span_title"),
        lambda: _edit_span(params, patch, parent, mode_warning),
    )


def _edit_span(
    params: SpectrumParams,
    patch: Callable[[SpectrumParams], None],
    parent: Optional[QWidget],
    mode_warning: Optional[Callable[[ModeRestriction | None], None]],
) -> None:
    from gui.monitor.monitor_status_dialogs import edit_span_dialog

    updated = edit_span_dialog(params, parent=parent)
    if updated is None:
        return
    from core.monitor.monitor_mode_guard import span_requires_analyzer_mode

    requested = float(updated.manual_span_hz if updated.span_mode == "manual" else updated.span_hz)
    if mode_warning is not None:
        mode_warning(span_requires_analyzer_mode(params, requested))
    patch(updated)
