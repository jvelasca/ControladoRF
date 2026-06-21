"""Utilidades seguras para actualizar spins RBW/VBW/SWT."""
from __future__ import annotations

from gui.monitor.monitor_numeric_control import MonitorNumericControl


def safe_spin_update(control: MonitorNumericControl, *, force: bool = False) -> None:
    """Cancela edición y bloquea señales del spin durante refresco programático."""
    if force:
        control.commit_editing()
    spin = control._spin
    spin.blockSignals(True)
    control._block_emit = True


def safe_spin_restore(control: MonitorNumericControl) -> None:
    spin = control._spin
    control._block_emit = False
    spin.blockSignals(False)
