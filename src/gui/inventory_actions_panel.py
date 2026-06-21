"""Panel Acciones del inventario RF (coordinación / monitor)."""
from __future__ import annotations

from typing import Any, Dict, Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget

from core.inventory_selection import FOCUS_CHANNEL, FOCUS_GROUP, FOCUS_LIST, focus_kind
from gui.panel_styles import apply_panel_style, get_panel_colors
from i18n.json_translation import tr


class InventoryActionsPanel(QWidget):
    """Acciones externas vinculadas a Coordinación y Monitor (no CRUD de inventario)."""

    def __init__(
        self,
        module_id: str,
        panel_id: str,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._module_id = module_id
        self._panel_id = panel_id
        self._style_key = f"{module_id}_{panel_id}"
        self._focus: Optional[Dict[str, Any]] = None

        self._hint = QLabel()
        self._hint.setWordWrap(True)
        self._hint.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

        self._context = QLabel()
        self._context.setWordWrap(True)
        self._context.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        layout.addWidget(self._hint)
        layout.addWidget(self._context)
        layout.addStretch(1)

        self.set_focus(None)
        self.recargar_textos()
        self.apply_visual_theme()

    def set_focus(self, focus: Optional[Dict[str, Any]]) -> None:
        self._focus = dict(focus) if focus else None
        self._refresh_text()

    def _refresh_text(self) -> None:
        kind = focus_kind(self._focus)
        if kind == "none":
            self._context.setVisible(False)
            return
        self._context.setVisible(True)
        if kind == FOCUS_LIST:
            self._context.setText(tr("inventory_actions_context_list"))
        elif kind == FOCUS_GROUP and self._focus:
            label = self._focus.get("label") or "—"
            count = len(self._focus.get("items") or [])
            self._context.setText(
                tr("inventory_actions_context_group", label=label, count=count)
            )
        elif kind == FOCUS_CHANNEL and self._focus:
            item = self._focus.get("item") or {}
            name = item.get("channel_name") or item.get("channel_number") or "—"
            self._context.setText(tr("inventory_actions_context_channel", name=name))
        else:
            self._context.setVisible(False)

    def apply_visual_theme(self, panel_id: str | None = None) -> None:
        key = panel_id or self._style_key
        apply_panel_style(self, key)
        colors = get_panel_colors(key)
        muted = f"color: {colors['text_muted']};"
        self._hint.setStyleSheet(muted)
        self._context.setStyleSheet(f"color: {colors['fg']}; font-size: 11px;")

    def recargar_textos(self) -> None:
        self._hint.setText(tr("inventory_actions_future_hint"))
        self._refresh_text()
