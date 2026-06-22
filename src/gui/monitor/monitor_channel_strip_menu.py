"""Menú … de la franja de canales bajo el espectro."""
from __future__ import annotations

from typing import Callable, Optional, Sequence

from PyQt6.QtWidgets import QMenu, QWidget

from core.rf.channelization_service import ChannelizationService
from i18n.json_translation import tr


def populate_channel_strip_menu(
    menu: QMenu,
    *,
    service: Optional[ChannelizationService],
    exclusions: Sequence,
    on_open_dialog: Callable[[], None],
    on_clear_exclusions: Callable[[], None],
    parent: Optional[QWidget] = None,
) -> None:
    menu.addAction(tr("channel_strip_menu_open_dialog"), on_open_dialog)

    if exclusions:
        menu.addSeparator()
        clear = menu.addAction(tr("channel_strip_menu_clear_exclusions"), on_clear_exclusions)
        clear.setToolTip(tr("channel_strip_menu_clear_exclusions_tip"))

    if service is not None:
        menu.addSeparator()
        state = service.get_state()
        region = menu.addAction(
            tr("channel_strip_menu_info_region").format(region=state.active_region)
        )
        region.setEnabled(False)
        standards = menu.addAction(
            tr("channel_strip_menu_info_standards").format(
                count=len(state.active_standard_ids)
            )
        )
        standards.setEnabled(False)
        ex_info = menu.addAction(
            tr("channel_strip_menu_info_exclusions").format(count=len(exclusions))
        )
        ex_info.setEnabled(False)
