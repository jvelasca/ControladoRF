"""Árbol de inventario supervisado — clic para localizar en espectro."""
from __future__ import annotations

from typing import Dict, List, Optional, Sequence

from PyQt6.QtCore import Qt, QPoint, QSize, QTimer, pyqtSignal
from PyQt6.QtGui import QAction, QActionGroup, QColor
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QMenu,
    QMessageBox,
    QStyle,
    QToolButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.monitor.supervision.supervision_models import (
    AlarmDisplayRow,
    ResolvedSupervisionTarget,
    SupervisionChannelMetrics,
    SupervisionState,
)
from core.monitor.supervision.supervision_tree import (
    GROUP_DEVICE_TYPE,
    GROUP_MANUFACTURER,
    GROUP_MODEL,
    GROUP_ZONE,
    SUPERVISION_TREE_GROUP_MODES,
    SupervisionTreeGroup,
    build_supervision_tree,
    tree_icon_tone_blinks,
)
from gui.monitor.monitor_shortcuts import MONITOR_SHORTCUTS
from gui.monitor.monitor_supervision_tree_icons import supervision_tree_icon
from gui.shortcut_tooltips import tooltip_with_shortcut
from i18n.json_translation import tr

_ROLE_KIND = int(Qt.ItemDataRole.UserRole)
_ROLE_KEY = int(Qt.ItemDataRole.UserRole) + 1
_ROLE_KEYS = int(Qt.ItemDataRole.UserRole) + 2

_KIND_GROUP = "group"
_KIND_CHANNEL = "channel"

_TREE_GROUP_I18N = {
    "zone": "inventory_group_zone",
    "device_type": "inventory_group_type",
    "model": "monitor_supervision_group_model",
    "manufacturer": "monitor_supervision_group_manufacturer",
    "network": "inventory_group_network",
    "series": "inventory_group_series",
    "none": "inventory_group_none",
}

_TOOL_BTN_SIZE = QSize(22, 20)
_TOOL_ICON_SIZE = QSize(14, 14)
_COMMENT_TEXT_COLOR = QColor("#92400E")
_ACK_TEXT_COLOR = QColor("#CA8A04")


class MonitorSupervisionTreeWidget(QWidget):
    """Árbol agrupado del inventario con localización en espectro al pulsar."""

    ack_all_requested = pyqtSignal()
    ack_channel_requested = pyqtSignal(str)
    highlight_channels_requested = pyqtSignal(list)
    locate_channels_requested = pyqtSignal(list)
    group_mode_changed = pyqtSignal(str)
    supervision_enabled_changed = pyqtSignal(list, bool)
    history_requested = pyqtSignal()
    export_requested = pyqtSignal()
    thresholds_requested = pyqtSignal(object)
    log_export_requested = pyqtSignal(list)
    log_view_requested = pyqtSignal(object)
    scope_thresholds_requested = pyqtSignal(object)
    help_requested = pyqtSignal()
    digital_mode_changed = pyqtSignal(str, bool)

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        *,
        compact: bool = False,
        embed_toolbar: bool = True,
    ) -> None:
        super().__init__(parent)
        self._compact = compact
        self._embed_toolbar = embed_toolbar
        self._groups: List[SupervisionTreeGroup] = []
        self._group_mode = "zone"
        self._pending_attention = 0
        self._log_path = ""
        self._tree_signature: tuple = ()
        self._resolved: List[ResolvedSupervisionTarget] = []
        self._equipos: list = []
        self._alarm_states: dict[str, str] = {}
        self._alarm_rows: List[AlarmDisplayRow] = []
        self._channel_metrics: Dict[str, SupervisionChannelMetrics] = {}
        self._supervision_state: SupervisionState | None = None
        self._icon_blink_dim = False
        self._icon_blink_timer = QTimer(self)
        self._icon_blink_timer.setInterval(500)
        self._icon_blink_timer.timeout.connect(self._on_icon_blink_tick)
        self._group_btn: QToolButton | None = None
        self._locate_btn: QToolButton | None = None
        self._ack_btn: QToolButton | None = None
        self._thresholds_btn: QToolButton | None = None
        self._history_btn: QToolButton | None = None
        self._export_btn: QToolButton | None = None
        self._build_ui()
        self._apply_tool_tips()
        self._apply_styles()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(3)

        if self._embed_toolbar:
            toolbar = QHBoxLayout()
            toolbar.setSpacing(2)

            self._group_btn = self._make_tool_button(
                QStyle.StandardPixmap.SP_FileDialogListView,
                "monitor_supervision_tool_group",
            )
            self._group_btn.clicked.connect(lambda: self.show_group_menu())

            self._locate_btn = self._make_tool_button(
                QStyle.StandardPixmap.SP_ArrowRight,
                "monitor_supervision_tool_locate",
            )
            self._locate_btn.clicked.connect(self._on_locate_clicked)

            self._ack_btn = self._make_tool_button(
                QStyle.StandardPixmap.SP_DialogApplyButton,
                "monitor_supervision_tool_ack_all",
            )
            self._ack_btn.clicked.connect(self.ack_all_requested.emit)

            self._thresholds_btn = self._make_tool_button(
                QStyle.StandardPixmap.SP_FileDialogDetailedView,
                "monitor_supervision_tool_thresholds",
            )
            self._thresholds_btn.clicked.connect(self._on_thresholds_clicked)

            self._history_btn = self._make_tool_button(
                QStyle.StandardPixmap.SP_FileDialogInfoView,
                "monitor_supervision_tool_history",
            )
            self._history_btn.clicked.connect(self.history_requested.emit)

            self._export_btn = self._make_tool_button(
                QStyle.StandardPixmap.SP_DialogSaveButton,
                "monitor_supervision_tool_export",
            )
            self._export_btn.clicked.connect(self.export_requested.emit)

            toolbar_buttons = [self._group_btn, self._locate_btn]
            if not self._compact:
                toolbar_buttons.extend(
                    [
                        self._ack_btn,
                        self._thresholds_btn,
                        self._history_btn,
                        self._export_btn,
                    ]
                )
            for btn in toolbar_buttons:
                toolbar.addWidget(btn, alignment=Qt.AlignmentFlag.AlignVCenter)
            toolbar.addStretch(1)
            layout.addLayout(toolbar)

        self._tree = QTreeWidget()
        self._tree.setObjectName("MonitorSupervisionTree")
        self.setObjectName("MonitorSupervisionTreePanel")
        self._tree.setHeaderHidden(True)
        self._tree.setRootIsDecorated(True)
        self._tree.setIndentation(12)
        self._tree.setUniformRowHeights(True)
        self._tree.itemClicked.connect(self._on_tree_item_clicked)
        self._tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._tree.customContextMenuRequested.connect(self._on_tree_context_menu)
        layout.addWidget(self._tree, stretch=1)

    def _make_tool_button(
        self,
        icon: QStyle.StandardPixmap,
        tip_key: str,
        *,
        text_fallback: str = "",
    ) -> QToolButton:
        btn = QToolButton(self)
        btn.setObjectName("MonitorSupervisionToolBtn")
        style = self.style()
        if style is not None:
            btn.setIcon(style.standardIcon(icon))
        elif text_fallback:
            btn.setText(text_fallback)
        btn.setIconSize(_TOOL_ICON_SIZE)
        btn.setFixedSize(_TOOL_BTN_SIZE)
        btn.setToolTip(tr(tip_key))
        btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn.setAutoRaise(True)
        return btn

    def _apply_tool_tips(self) -> None:
        tips = (
            (self._group_btn, "monitor_supervision_tool_group", ""),
            (self._locate_btn, "monitor_supervision_tool_locate", MONITOR_SHORTCUTS["locate"]),
            (self._ack_btn, "monitor_supervision_tool_ack_all", MONITOR_SHORTCUTS["ack_all"]),
            (self._thresholds_btn, "monitor_supervision_tool_thresholds", MONITOR_SHORTCUTS["thresholds"]),
            (self._history_btn, "monitor_supervision_tool_history", MONITOR_SHORTCUTS["history"]),
            (self._export_btn, "monitor_supervision_tool_export", MONITOR_SHORTCUTS["export_report"]),
        )
        for btn, key, shortcut in tips:
            if btn is not None:
                btn.setToolTip(tooltip_with_shortcut(tr(key), shortcut))

    def _apply_styles(self) -> None:
        from gui.app_chrome_styles import apply_monitor_supervision_tree_styles

        apply_monitor_supervision_tree_styles(self)

    def set_group_mode(self, mode: str) -> None:
        if mode not in SUPERVISION_TREE_GROUP_MODES:
            mode = "zone"
        if mode == self._group_mode:
            return
        self._group_mode = mode
        self._tree_signature = ()
        self._rebuild_tree()

    def update_supervision(
        self,
        *,
        resolved: Sequence[ResolvedSupervisionTarget],
        equipos: list,
        alarm_states: dict[str, str],
        alarm_rows: Sequence[AlarmDisplayRow],
        channel_metrics: Optional[Dict[str, SupervisionChannelMetrics]] = None,
        supervision_state: SupervisionState | None = None,
        group_mode: str,
        pending_attention: int,
        log_path: str = "",
    ) -> None:
        signature = self._compute_signature(
            resolved, alarm_states, alarm_rows, channel_metrics or {}, group_mode
        )
        self._resolved = list(resolved)
        self._equipos = list(equipos)
        self._alarm_states = dict(alarm_states)
        self._alarm_rows = list(alarm_rows)
        self._channel_metrics = dict(channel_metrics or {})
        self._supervision_state = supervision_state
        self._pending_attention = pending_attention
        self._log_path = log_path
        if group_mode != self._group_mode:
            self._group_mode = group_mode
        if not self._compact and self._ack_btn is not None:
            self._ack_btn.setEnabled(pending_attention > 0)
        if signature == self._tree_signature:
            return
        self._tree_signature = signature
        self._rebuild_tree()
        self._sync_icon_blink_timer()

    def _any_blinking_channels(self) -> bool:
        for group in self._groups:
            for channel in group.channels:
                if channel.enabled and tree_icon_tone_blinks(channel.icon_tone):
                    return True
        return False

    def _sync_icon_blink_timer(self) -> None:
        if self._any_blinking_channels():
            if not self._icon_blink_timer.isActive():
                self._icon_blink_dim = False
                self._icon_blink_timer.start()
        else:
            self._icon_blink_dim = False
            self._icon_blink_timer.stop()
            self._refresh_tree_icons()

    def _on_icon_blink_tick(self) -> None:
        if not self._any_blinking_channels():
            self._icon_blink_dim = False
            self._icon_blink_timer.stop()
            self._refresh_tree_icons()
            return
        self._icon_blink_dim = not self._icon_blink_dim
        self._refresh_tree_icons()

    def _refresh_tree_icons(self) -> None:
        blink_dim = self._icon_blink_dim
        for index in range(self._tree.topLevelItemCount()):
            group_item = self._tree.topLevelItem(index)
            if group_item is None:
                continue
            kind = str(group_item.data(0, _ROLE_KIND) or "")
            if kind != _KIND_GROUP:
                continue
            group_key = str(group_item.data(0, _ROLE_KEY) or "")
            group = self._find_group(group_key)
            if group is not None:
                group_item.setIcon(
                    0,
                    self._group_icon(group),
                )
            for child_index in range(group_item.childCount()):
                child = group_item.child(child_index)
                if child is None:
                    continue
                channel_key = str(child.data(0, _ROLE_KEY) or "")
                channel = self._find_channel(channel_key)
                if channel is not None:
                    child.setIcon(
                        0,
                        self._channel_icon(channel, blink_dim=blink_dim),
                    )

    def _compute_signature(
        self,
        resolved: Sequence[ResolvedSupervisionTarget],
        alarm_states: dict[str, str],
        alarm_rows: Sequence[AlarmDisplayRow],
        channel_metrics: Dict[str, SupervisionChannelMetrics],
        group_mode: str,
    ) -> tuple:
        rows_sig = tuple(
            (row.channel_key, row.severity, row.phase, row.can_ack, row.acknowledged)
            for row in alarm_rows
        )
        metrics_sig = tuple(
            sorted(
                (
                    key,
                    metrics.snr_db,
                    metrics.mer_db,
                    metrics.sync_ok,
                    metrics.digital_mode,
                )
                for key, metrics in channel_metrics.items()
            )
        )
        resolved_sig = tuple(
            (target.channel_key, target.label, target.frequency_hz, target.enabled)
            for target in resolved
        )
        states_sig = tuple(sorted(alarm_states.items()))
        return (group_mode, resolved_sig, states_sig, rows_sig, metrics_sig)

    def _rebuild_tree(self) -> None:
        scroll = self._tree.verticalScrollBar().value()
        self._tree.clear()
        self._groups = build_supervision_tree(
            self._resolved,
            self._equipos,
            self._alarm_states,
            group_mode=self._group_mode,
            alarm_rows=self._alarm_rows,
            channel_metrics=self._channel_metrics,
            supervision_state=self._supervision_state,
            tr=tr,
        )
        if not self._groups or not any(group.channels for group in self._groups):
            empty = QTreeWidgetItem([tr("monitor_supervision_tree_empty")])
            empty.setFlags(Qt.ItemFlag.NoItemFlags)
            self._tree.addTopLevelItem(empty)
            return

        for group in self._groups:
            if not group.channels:
                continue
            group_item = self._make_group_item(group)
            self._tree.addTopLevelItem(group_item)
            for channel in group.channels:
                child = self._make_channel_item(channel)
                group_item.addChild(child)
            group_item.setExpanded(True)
        self._tree.verticalScrollBar().setValue(scroll)

    def _make_group_item(self, group: SupervisionTreeGroup) -> QTreeWidgetItem:
        text = tr("monitor_supervision_tree_group_label").format(
            label=group.label,
            count=group.channel_count,
        )
        item = QTreeWidgetItem([text])
        item.setData(0, _ROLE_KIND, _KIND_GROUP)
        item.setData(0, _ROLE_KEY, group.group_key)
        item.setData(0, _ROLE_KEYS, [channel.channel_key for channel in group.channels])
        group_unsupervised = not any(channel.enabled for channel in group.channels)
        item.setIcon(0, self._group_icon(group))
        self._apply_item_unsupervised(item, group_unsupervised)
        return item

    def _group_icon(self, group: SupervisionTreeGroup):
        group_device = group.group_key if self._group_mode == GROUP_DEVICE_TYPE else None
        group_enabled = any(channel.enabled for channel in group.channels)
        return supervision_tree_icon(
            group_device,
            group.rollup,
            is_group=group_device is None,
            enabled=group_enabled,
        )

    def _channel_icon(self, channel, *, blink_dim: bool = False):
        dim = blink_dim and tree_icon_tone_blinks(channel.icon_tone)
        return supervision_tree_icon(
            channel.device_type,
            channel.icon_tone,
            is_group=False,
            enabled=channel.enabled,
            blink_dim=dim,
        )

    def _make_channel_item(self, channel) -> QTreeWidgetItem:
        freq_text = f"{channel.frequency_mhz:.3f} MHz"
        metrics_text = self._format_channel_metrics(channel)
        text = tr("monitor_supervision_tree_channel_label").format(
            label=channel.label,
            freq=freq_text,
        )
        if metrics_text:
            text = f"{text} · {metrics_text}"
        item = QTreeWidgetItem([text])
        item.setData(0, _ROLE_KIND, _KIND_CHANNEL)
        item.setData(0, _ROLE_KEY, channel.channel_key)
        item.setData(0, _ROLE_KEYS, [channel.channel_key])
        item.setIcon(0, self._channel_icon(channel))
        self._apply_item_unsupervised(item, not channel.enabled)
        self._apply_channel_tone_style(item, channel)
        tooltip_parts = []
        if channel.is_digital:
            mode_key = (
                "monitor_thresholds_digital_mode_snr_mer"
                if channel.digital_mode == "snr_and_mer"
                else "monitor_thresholds_digital_mode_snr_only"
            )
            tooltip_parts.append(tr("monitor_supervision_tree_mode_tip").format(mode=tr(mode_key)))
        if channel.can_ack:
            tooltip_parts.append(tr("monitor_supervision_tree_ack_tip"))
        elif channel.icon_tone == "acknowledged":
            tooltip_parts.append(tr("monitor_supervision_tree_acknowledged_tip"))
        if tooltip_parts:
            item.setToolTip(0, "\n".join(tooltip_parts))
        return item

    @staticmethod
    def _apply_channel_tone_style(item: QTreeWidgetItem, channel) -> None:
        if not channel.enabled:
            return
        if channel.icon_tone == "comentario":
            item.setForeground(0, _COMMENT_TEXT_COLOR)
        elif channel.icon_tone == "acknowledged":
            item.setForeground(0, _ACK_TEXT_COLOR)

    @staticmethod
    def _format_channel_metrics(channel) -> str:
        parts: list[str] = []
        if channel.snr_db is not None:
            parts.append(f"S/R {channel.snr_db:.1f} dB")
        if channel.digital_mode == "snr_and_mer":
            if channel.mer_db is not None:
                parts.append(f"MER {channel.mer_db:.1f} dB")
            if channel.sync_ok is False:
                parts.append(tr("monitor_supervision_tree_sync_lost"))
            elif channel.sync_ok is True and channel.mer_db is None:
                parts.append(tr("monitor_supervision_tree_sync_ok"))
        return " · ".join(parts)

    @staticmethod
    def _apply_item_unsupervised(item: QTreeWidgetItem, unsupervised: bool) -> None:
        if not unsupervised:
            return
        font = item.font(0)
        font.setStrikeOut(True)
        item.setFont(0, font)

    def _context_from_item(self, item: QTreeWidgetItem | None) -> tuple[str, str, list[str]]:
        if item is None:
            return "", "", []
        kind = str(item.data(0, _ROLE_KIND) or "")
        channel_key = str(item.data(0, _ROLE_KEY) or "")
        keys = [str(key) for key in (item.data(0, _ROLE_KEYS) or []) if key]
        return kind, channel_key, keys

    def _show_group_menu(self) -> None:
        self.show_group_menu()

    def show_group_menu(self, anchor: QWidget | None = None) -> None:
        if anchor is None:
            anchor = self._group_btn if self._group_btn is not None else self
        menu = QMenu(self)
        action_group = QActionGroup(menu)
        action_group.setExclusive(True)
        for mode in SUPERVISION_TREE_GROUP_MODES:
            label_key = _TREE_GROUP_I18N.get(mode, mode)
            action = menu.addAction(tr(label_key))
            action.setCheckable(True)
            action.setChecked(mode == self._group_mode)
            action.setData(mode)
            action_group.addAction(action)
        chosen = menu.exec(anchor.mapToGlobal(QPoint(0, anchor.height())))
        if chosen is None:
            return
        mode = chosen.data()
        if mode in SUPERVISION_TREE_GROUP_MODES and mode != self._group_mode:
            self._group_mode = mode
            self._tree_signature = ()
            self._rebuild_tree()
            self.group_mode_changed.emit(mode)

    def _on_locate_clicked(self) -> None:
        self.trigger_locate_selected()

    def _on_thresholds_clicked(self) -> None:
        self.thresholds_requested.emit({"scope": "global"})

    def _thresholds_context_for_item(
        self,
        kind: str,
        channel_key: str,
        group_key: str,
    ) -> dict:
        if kind == _KIND_CHANNEL and channel_key:
            return {"scope": "channel", "key": channel_key}
        if kind == _KIND_GROUP and self._group_mode == GROUP_MANUFACTURER and group_key:
            return {"scope": "manufacturer", "key": group_key}
        if kind == _KIND_GROUP and self._group_mode == GROUP_MODEL and group_key:
            return {"scope": "model", "key": group_key}
        if kind == _KIND_GROUP and self._group_mode == GROUP_ZONE and group_key:
            return {"scope": "zone", "key": group_key}
        if kind == _KIND_GROUP and self._group_mode == GROUP_DEVICE_TYPE and group_key:
            return {"scope": "device_type", "key": group_key}
        return {"scope": "global"}

    def trigger_locate_selected(self) -> bool:
        item = self._tree.currentItem()
        _kind, _key, keys = self._context_from_item(item)
        if not keys:
            return False
        channel_keys = [str(key) for key in keys if key]
        if not channel_keys:
            return False
        self.locate_channels_requested.emit(channel_keys)
        return True

    def trigger_ack_selected(self) -> bool:
        item = self._tree.currentItem()
        kind, channel_key, _keys = self._context_from_item(item)
        if kind != _KIND_CHANNEL or not channel_key:
            return False
        channel = self._find_channel(channel_key)
        if channel is None or not channel.can_ack:
            return False
        self.ack_channel_requested.emit(channel_key)
        return True

    def _scope_channel_keys(self, kind: str, channel_key: str, keys: list[str]) -> list[str]:
        from core.monitor.supervision.supervision_scope import channel_keys_for_same_device

        if kind == _KIND_GROUP:
            return list(keys)
        if kind == _KIND_CHANNEL and channel_key:
            return channel_keys_for_same_device(channel_key, self._equipos)
        return list(keys)

    def _scope_title(self, kind: str, channel_key: str) -> str:
        if kind == _KIND_CHANNEL:
            channel = self._find_channel(channel_key)
            if channel is not None:
                return channel.label
            return channel_key
        if kind == _KIND_GROUP:
            for group in self._groups:
                if group.group_key == channel_key:
                    return group.label
        return channel_key

    def _show_context_menu(
        self,
        *,
        kind: str,
        channel_key: str,
        keys: list[str],
        global_pos: QPoint,
    ) -> None:
        if not keys or kind not in (_KIND_CHANNEL, _KIND_GROUP):
            return

        menu = QMenu(self)
        if kind == _KIND_CHANNEL:
            channel = self._find_channel(channel_key)
            supervise_action = menu.addAction(tr("monitor_supervision_ctx_supervise"))
            supervise_action.setCheckable(True)
            supervise_action.setChecked(bool(channel is not None and channel.enabled))
        else:
            supervise_action = menu.addAction(tr("monitor_supervision_ctx_supervise_group"))
            supervise_action.setCheckable(True)
            supervise_action.setChecked(self._group_all_enabled(keys))

        ack_action = None
        if kind == _KIND_CHANNEL:
            channel = self._find_channel(channel_key)
            if channel is not None and channel.can_ack:
                ack_action = menu.addAction(tr("monitor_supervision_ctx_ack"))

        menu.addSeparator()

        log_available = bool(self._log_path)
        export_log_action = menu.addAction(tr("monitor_supervision_ctx_export_log"))
        export_log_action.setEnabled(log_available)
        view_log_action = menu.addAction(tr("monitor_supervision_ctx_view_log"))
        view_log_action.setEnabled(log_available)

        menu.addSeparator()

        thresholds_action = menu.addAction(tr("monitor_supervision_ctx_thresholds"))

        scope_keys = self._scope_channel_keys(kind, channel_key, keys)
        chosen = menu.exec(global_pos)
        if chosen is None:
            return
        if chosen == supervise_action:
            enabled = supervise_action.isChecked()
            toggle_keys = keys if kind == _KIND_GROUP else [channel_key]
            self.supervision_enabled_changed.emit(toggle_keys, enabled)
        elif ack_action is not None and chosen == ack_action:
            self.ack_channel_requested.emit(channel_key)
        elif chosen == export_log_action:
            self.log_export_requested.emit(scope_keys)
        elif chosen == view_log_action:
            self.log_view_requested.emit(
                {
                    "channel_keys": scope_keys,
                    "title": self._scope_title(kind, channel_key),
                }
            )
        elif chosen == thresholds_action:
            self.scope_thresholds_requested.emit(
                {
                    "channel_keys": scope_keys,
                    "title": self._scope_title(kind, channel_key),
                }
            )

    def _group_all_enabled(self, channel_keys: list[str]) -> bool:
        key_set = set(channel_keys)
        matched = False
        for group in self._groups:
            for channel in group.channels:
                if channel.channel_key in key_set:
                    matched = True
                    if not channel.enabled:
                        return False
        return matched

    def _on_tree_item_clicked(self, item: QTreeWidgetItem, _column: int) -> None:
        kind = str(item.data(0, _ROLE_KIND) or "")
        if kind not in (_KIND_CHANNEL, _KIND_GROUP):
            return
        keys = item.data(0, _ROLE_KEYS) or []
        channel_keys = [str(key) for key in keys if key]
        if channel_keys:
            self.highlight_channels_requested.emit(channel_keys)

    def _on_tree_context_menu(self, pos) -> None:
        item = self._tree.itemAt(pos)
        if item is not None:
            self._tree.setCurrentItem(item)
            kind, channel_key, keys = self._context_from_item(item)
        else:
            kind, channel_key, keys = "", "", []
        self._show_context_menu(
            kind=kind,
            channel_key=channel_key,
            keys=keys,
            global_pos=self._tree.viewport().mapToGlobal(pos),
        )

    def _find_group(self, group_key: str) -> SupervisionTreeGroup | None:
        for group in self._groups:
            if group.group_key == group_key:
                return group
        return None

    def _find_channel(self, channel_key: str):
        for group in self._groups:
            for channel in group.channels:
                if channel.channel_key == channel_key:
                    return channel
        return None

    def recargar_textos(self) -> None:
        self._apply_tool_tips()
        self._tree_signature = ()
        self._rebuild_tree()
