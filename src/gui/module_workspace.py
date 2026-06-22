"""Espacio de trabajo de un módulo: 3 paneles dentro de splitters."""
from __future__ import annotations

from typing import Any, Callable, Dict, Optional

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import QHBoxLayout, QSizePolicy, QSplitter, QVBoxLayout, QWidget

from core.project_model import PANEL_IDS
from gui.module_panel_frame import ModulePanelFrame
from gui.placeholder_panel import PlaceholderPanelWidget

DEFAULT_HORIZONTAL = (720, 280)
DEFAULT_VERTICAL = (420, 260)
MONITOR_DEFAULT_HORIZONTAL = (820, 300)
MONITOR_DEFAULT_VERTICAL = (520, 240)
MIN_SPLITTER_TOTAL = 120
SIDE_PANEL_HANDLE_WIDTH = 14
WATERFALL_HANDLE_HEIGHT = 14
MIN_MONITOR_SIDE_WIDTH = 160


def _splitter_sizes_from_ratio(
    total: int,
    *,
    reference: list[int],
    fallback: list[int],
    min_second: int,
) -> list[int]:
    """Reparte ``total`` px entre dos paneles conservando la proporción de referencia."""
    total = max(int(total), MIN_SPLITTER_TOTAL)
    ref = reference if len(reference) == 2 and sum(reference) >= MIN_SPLITTER_TOTAL else fallback
    ref_total = sum(ref) or sum(fallback) or MIN_SPLITTER_TOTAL
    second = max(min_second, int(round(total * ref[1] / ref_total)))
    second = min(second, max(total - MIN_SPLITTER_TOTAL, min_second))
    first = max(total - second, MIN_SPLITTER_TOTAL)
    if first + second != total:
        second = max(min_second, total - first)
    return [first, second]


class ModuleWorkspaceWidget(QWidget):
    """
    Layout profesional dentro de una pestaña:

    ┌───────────────┬──────────┐
    │ Lista      [□×]│          │
    ├───────────────┤ Propied. │
    │ Acciones      │          │
    └───────────────┴──────────┘
    """

    def __init__(
        self,
        module_id: str,
        *,
        on_layout_changed: Optional[Callable[[], None]] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.module_id = module_id
        self._on_layout_changed = on_layout_changed
        self._panels: Dict[str, ModulePanelFrame] = {}
        default_main = (
            MONITOR_DEFAULT_HORIZONTAL if module_id == "monitor" else DEFAULT_HORIZONTAL
        )
        default_left = (
            MONITOR_DEFAULT_VERTICAL if module_id == "monitor" else DEFAULT_VERTICAL
        )
        self._last_good_main_sizes = list(default_main)
        self._last_good_left_sizes = list(default_left)
        self._monitor_controller = None
        self._maximized_panel: Optional[str] = None
        self._properties_collapsed = False
        self._waterfall_collapsed = False
        self._pre_collapse_main_sizes: Optional[list[int]] = None
        self._pre_collapse_left_sizes: Optional[list[int]] = None
        self._pre_collapse_prop_min_width = 160
        self._pre_collapse_wf_min_height = 100
        self._pre_view_hide_main_sizes: Optional[list[int]] = None
        self._pre_view_hide_left_sizes: Optional[list[int]] = None
        self._side_column: Optional[QWidget] = None
        self._side_handle = None
        self._waterfall_stack: Optional[QWidget] = None
        self._wf_handle = None
        self._pre_maximize_state: Optional[Dict[str, Any]] = None
        self._inventory_resolver: Optional[
            Callable[[Optional[Dict[str, Any]]], Optional[Dict[str, Any]]]
        ] = None

        root = QHBoxLayout(self)
        root.setContentsMargins(4, 4, 4, 4)
        root.setSpacing(0)

        self._main_splitter = QSplitter(Qt.Orientation.Horizontal)
        self._left_splitter = QSplitter(Qt.Orientation.Vertical)

        for panel_id in PANEL_IDS:
            content = self._create_panel_content(
                module_id,
                panel_id,
                on_state_changed=self._emit_layout_changed,
            )
            frame = ModulePanelFrame(
                module_id, panel_id, content_widget=content, parent=self
            )
            frame.close_requested.connect(
                lambda pid=panel_id: self._on_panel_close_requested(pid)
            )
            frame.maximize_toggled.connect(
                lambda pid=panel_id: self.toggle_maximize_panel(pid)
            )
            self._panels[panel_id] = frame

        self._left_splitter.addWidget(self._panels["lista"])
        if module_id == "monitor":
            from gui.monitor.monitor_panel_collapse_handle import MonitorPanelCollapseHandle

            self._wf_handle = MonitorPanelCollapseHandle(axis="vertical", parent=self)
            self._wf_handle.collapse_requested.connect(self._on_waterfall_collapse_requested)
            self._waterfall_stack = QWidget(self)
            wf_layout = QVBoxLayout(self._waterfall_stack)
            wf_layout.setContentsMargins(0, 0, 0, 0)
            wf_layout.setSpacing(0)
            wf_layout.addWidget(self._wf_handle)
            wf_layout.addWidget(self._panels["acciones"], stretch=1)
            self._left_splitter.addWidget(self._waterfall_stack)
        else:
            self._left_splitter.addWidget(self._panels["acciones"])
        if module_id == "monitor":
            self._side_handle = MonitorPanelCollapseHandle(axis="horizontal", parent=self)
            self._side_handle.collapse_requested.connect(self._on_side_panel_collapse_requested)
            self._side_column = QWidget(self)
            side_layout = QHBoxLayout(self._side_column)
            side_layout.setContentsMargins(0, 0, 0, 0)
            side_layout.setSpacing(0)
            side_layout.addWidget(self._side_handle)
            side_layout.addWidget(self._panels["propiedades"], stretch=1)
            self._main_splitter.addWidget(self._left_splitter)
            self._main_splitter.addWidget(self._side_column)
        else:
            self._main_splitter.addWidget(self._left_splitter)
            self._main_splitter.addWidget(self._panels["propiedades"])

        if module_id == "monitor":
            self._main_splitter.setStretchFactor(0, 4)
            self._main_splitter.setStretchFactor(1, 1)
            self._left_splitter.setStretchFactor(0, 3)
            self._left_splitter.setStretchFactor(1, 2)
            self._init_monitor_controller()
        else:
            self._main_splitter.setStretchFactor(0, 3)
            self._main_splitter.setStretchFactor(1, 1)
            self._left_splitter.setStretchFactor(0, 3)
            self._left_splitter.setStretchFactor(1, 2)

        self._main_splitter.setChildrenCollapsible(False)
        self._left_splitter.setChildrenCollapsible(False)

        root.addWidget(self._main_splitter)
        self._main_splitter.splitterMoved.connect(self._emit_layout_changed)
        self._left_splitter.splitterMoved.connect(self._emit_layout_changed)
        if module_id == "inventario_rf":
            pass
        self.reset_layout()

    def _init_monitor_controller(self) -> None:
        from gui.monitor.monitor_config_panel import MonitorConfigPanel
        from gui.monitor.monitor_controller import MonitorController
        from gui.monitor.monitor_spectrum_widget import MonitorSpectrumWidget
        from gui.monitor.monitor_waterfall_widget import MonitorWaterfallWidget

        spectrum = self._panels["lista"].content
        waterfall = self._panels["acciones"].content
        config = self._panels["propiedades"].content
        if not isinstance(spectrum, MonitorSpectrumWidget):
            return
        if not isinstance(waterfall, MonitorWaterfallWidget):
            return
        if not isinstance(config, MonitorConfigPanel):
            return
        self._monitor_controller = MonitorController(
            spectrum=spectrum,
            waterfall=waterfall,
            config=config,
            parent=self,
        )
        config.bind_table_layout_persist(self._monitor_controller._schedule_layout_persist)
        self._monitor_controller.set_layout_persist_callback(self._emit_layout_changed)

    def get_monitor_controller(self):
        return self._monitor_controller

    def _is_side_column_view_hidden(self) -> bool:
        return self._side_column is not None and not self._side_column.isVisible()

    def _is_waterfall_stack_view_hidden(self) -> bool:
        return self._waterfall_stack is not None and not self._waterfall_stack.isVisible()

    def _set_device_panel_view_visible(self, visible: bool) -> None:
        prop = self._panels["propiedades"]
        if not visible:
            main_sizes = self._main_splitter.sizes()
            if (
                not self._properties_collapsed
                and sum(main_sizes) >= MIN_SPLITTER_TOTAL
                and main_sizes[1] > SIDE_PANEL_HANDLE_WIDTH + 8
            ):
                self._pre_view_hide_main_sizes = list(main_sizes)
            prop.setVisible(False)
            if self._side_handle is not None:
                self._side_handle.setVisible(False)
            if self._side_column is not None:
                self._side_column.setVisible(False)
            total = sum(main_sizes) if sum(main_sizes) >= MIN_SPLITTER_TOTAL else sum(MONITOR_DEFAULT_HORIZONTAL)
            self._main_splitter.setSizes([max(total, MIN_SPLITTER_TOTAL), 0])
            return

        if self._side_column is not None:
            self._side_column.setVisible(True)
        if self._side_handle is not None:
            self._side_handle.setVisible(True)
        if self._properties_collapsed:
            self.set_properties_panel_collapsed(False, notify_controller=True)
            return
        self._restore_properties_panel_constraints(prop)
        total = sum(self._main_splitter.sizes())
        if total < MIN_SPLITTER_TOTAL:
            total = sum(MONITOR_DEFAULT_HORIZONTAL)
        ref = (
            self._pre_view_hide_main_sizes
            or self._pre_collapse_main_sizes
            or list(MONITOR_DEFAULT_HORIZONTAL)
        )
        self._main_splitter.setSizes(
            _splitter_sizes_from_ratio(
                total,
                reference=ref,
                fallback=list(MONITOR_DEFAULT_HORIZONTAL),
                min_second=MIN_MONITOR_SIDE_WIDTH + SIDE_PANEL_HANDLE_WIDTH,
            )
        )
        self._schedule_monitor_config_layout_refresh()

    def _set_waterfall_panel_view_visible(self, visible: bool) -> None:
        wf_panel = self._panels["acciones"]
        if not visible:
            left_sizes = self._left_splitter.sizes()
            if (
                not self._waterfall_collapsed
                and sum(left_sizes) >= MIN_SPLITTER_TOTAL
                and left_sizes[1] > WATERFALL_HANDLE_HEIGHT + 8
            ):
                self._pre_view_hide_left_sizes = list(left_sizes)
            wf_panel.setVisible(False)
            if self._wf_handle is not None:
                self._wf_handle.setVisible(False)
            if self._waterfall_stack is not None:
                self._waterfall_stack.setVisible(False)
            total = sum(left_sizes) if sum(left_sizes) >= MIN_SPLITTER_TOTAL else sum(MONITOR_DEFAULT_VERTICAL)
            self._left_splitter.setSizes([max(total, MIN_SPLITTER_TOTAL), 0])
            return

        if self._waterfall_stack is not None:
            self._waterfall_stack.setVisible(True)
        if self._wf_handle is not None:
            self._wf_handle.setVisible(True)
        if self._waterfall_collapsed:
            self.set_waterfall_panel_collapsed(False, notify_controller=True)
            return
        min_h = max(int(self._pre_collapse_wf_min_height or 0), 100)
        wf_panel.setMinimumHeight(min_h)
        wf_panel.setMaximumHeight(16777215)
        wf_panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        wf_panel.setVisible(True)
        total = sum(self._left_splitter.sizes())
        if total < MIN_SPLITTER_TOTAL:
            total = sum(MONITOR_DEFAULT_VERTICAL)
        ref = (
            self._pre_view_hide_left_sizes
            or self._pre_collapse_left_sizes
            or list(MONITOR_DEFAULT_VERTICAL)
        )
        self._left_splitter.setSizes(
            _splitter_sizes_from_ratio(
                total,
                reference=ref,
                fallback=list(MONITOR_DEFAULT_VERTICAL),
                min_second=MIN_MONITOR_SIDE_WIDTH,
            )
        )

    def _set_spectrum_panel_view_visible(self, visible: bool) -> None:
        lista = self._panels["lista"]
        if not visible:
            left_sizes = self._left_splitter.sizes()
            if sum(left_sizes) >= MIN_SPLITTER_TOTAL and left_sizes[0] > MIN_SPLITTER_TOTAL:
                self._pre_view_hide_left_sizes = list(left_sizes)
            lista.setVisible(False)
            total = sum(left_sizes) if sum(left_sizes) >= MIN_SPLITTER_TOTAL else sum(MONITOR_DEFAULT_VERTICAL)
            self._left_splitter.setSizes([0, max(total, MIN_SPLITTER_TOTAL)])
            return

        lista.setVisible(True)
        if not self._is_waterfall_stack_view_hidden():
            total = sum(self._left_splitter.sizes())
            if total < MIN_SPLITTER_TOTAL:
                total = sum(MONITOR_DEFAULT_VERTICAL)
            ref = self._pre_view_hide_left_sizes or list(MONITOR_DEFAULT_VERTICAL)
            self._left_splitter.setSizes(
                _splitter_sizes_from_ratio(
                    total,
                    reference=ref,
                    fallback=list(MONITOR_DEFAULT_VERTICAL),
                    min_second=MIN_MONITOR_SIDE_WIDTH,
                )
            )

    def _set_monitor_panel_view_visible(self, panel_id: str, visible: bool) -> None:
        if panel_id == "propiedades":
            self._set_device_panel_view_visible(visible)
        elif panel_id == "acciones":
            self._set_waterfall_panel_view_visible(visible)
        elif panel_id == "lista":
            self._set_spectrum_panel_view_visible(visible)

    def set_properties_panel_collapsed(self, collapsed: bool, *, notify_controller: bool = True) -> None:
        if self.module_id != "monitor":
            return
        if self._is_side_column_view_hidden():
            self._properties_collapsed = collapsed
            if self._side_handle is not None:
                self._side_handle.set_collapsed(collapsed)
            if notify_controller and self._monitor_controller is not None:
                self._monitor_controller.persist_config_panel_collapsed(collapsed)
            return
        if collapsed == self._properties_collapsed:
            return
        self._properties_collapsed = collapsed
        prop = self._panels.get("propiedades")
        handle_w = SIDE_PANEL_HANDLE_WIDTH
        if self._side_handle is not None:
            self._side_handle.set_collapsed(collapsed)
        if prop is not None:
            if collapsed:
                self._pre_collapse_prop_min_width = max(prop.minimumWidth(), MIN_MONITOR_SIDE_WIDTH)
                prop.setVisible(False)
                prop.setMinimumWidth(0)
                prop.setMaximumWidth(0)
                prop.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Expanding)
            else:
                self._restore_properties_panel_constraints(prop)
        if collapsed:
            main_sizes = self._main_splitter.sizes()
            total = sum(main_sizes) if sum(main_sizes) >= MIN_SPLITTER_TOTAL else sum(MONITOR_DEFAULT_HORIZONTAL)
            if sum(main_sizes) >= MIN_SPLITTER_TOTAL and main_sizes[1] > handle_w + 8:
                self._pre_collapse_main_sizes = list(main_sizes)
            self._main_splitter.setSizes([max(total - handle_w, MIN_SPLITTER_TOTAL), handle_w])
        else:
            self._restore_main_splitter_sizes()
            self._schedule_monitor_config_layout_refresh()
        self._emit_layout_changed()
        if notify_controller and self._monitor_controller is not None:
            self._monitor_controller.persist_config_panel_collapsed(collapsed)

    def _restore_properties_panel_constraints(self, prop: ModulePanelFrame) -> None:
        min_w = max(int(self._pre_collapse_prop_min_width or 0), MIN_MONITOR_SIDE_WIDTH)
        prop.setMinimumWidth(min_w)
        prop.setMaximumWidth(16777215)
        prop.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        prop.setVisible(True)

    def _restore_main_splitter_sizes(self) -> None:
        total = sum(self._main_splitter.sizes())
        if total < MIN_SPLITTER_TOTAL:
            total = sum(MONITOR_DEFAULT_HORIZONTAL)
        sizes = _splitter_sizes_from_ratio(
            total,
            reference=self._pre_collapse_main_sizes or list(MONITOR_DEFAULT_HORIZONTAL),
            fallback=list(MONITOR_DEFAULT_HORIZONTAL),
            min_second=MIN_MONITOR_SIDE_WIDTH + SIDE_PANEL_HANDLE_WIDTH,
        )
        self._main_splitter.setSizes(sizes)

    def _restore_left_splitter_sizes(self) -> None:
        total = sum(self._left_splitter.sizes())
        if total < MIN_SPLITTER_TOTAL:
            total = sum(MONITOR_DEFAULT_VERTICAL)
        sizes = _splitter_sizes_from_ratio(
            total,
            reference=self._pre_collapse_left_sizes or list(MONITOR_DEFAULT_VERTICAL),
            fallback=list(MONITOR_DEFAULT_VERTICAL),
            min_second=MIN_MONITOR_SIDE_WIDTH,
        )
        self._left_splitter.setSizes(sizes)

    def _schedule_monitor_config_layout_refresh(self) -> None:
        if self.module_id != "monitor":
            return
        prop = self._panels.get("propiedades")
        if prop is None:
            return
        content = prop.content
        refresh = getattr(content, "refresh_layout_geometry", None)
        if callable(refresh):
            QTimer.singleShot(0, refresh)

    def _on_side_panel_collapse_requested(self, collapsed: bool) -> None:
        self.set_properties_panel_collapsed(collapsed, notify_controller=True)

    def set_waterfall_panel_collapsed(self, collapsed: bool, *, notify_controller: bool = True) -> None:
        if self.module_id != "monitor":
            return
        if self._is_waterfall_stack_view_hidden():
            self._waterfall_collapsed = collapsed
            if self._wf_handle is not None:
                self._wf_handle.set_collapsed(collapsed)
            if notify_controller and self._monitor_controller is not None:
                self._monitor_controller.persist_waterfall_panel_collapsed(collapsed)
            return
        if collapsed == self._waterfall_collapsed:
            return
        self._waterfall_collapsed = collapsed
        wf_panel = self._panels.get("acciones")
        handle_h = WATERFALL_HANDLE_HEIGHT
        if self._wf_handle is not None:
            self._wf_handle.set_collapsed(collapsed)
        if wf_panel is not None:
            if collapsed:
                self._pre_collapse_wf_min_height = max(wf_panel.minimumHeight(), 100)
                wf_panel.setVisible(False)
                wf_panel.setMinimumHeight(0)
                wf_panel.setMaximumHeight(0)
                wf_panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Ignored)
            else:
                min_h = max(int(self._pre_collapse_wf_min_height or 0), 100)
                wf_panel.setMinimumHeight(min_h)
                wf_panel.setMaximumHeight(16777215)
                wf_panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
                wf_panel.setVisible(True)
        left_sizes = self._left_splitter.sizes()
        total = (
            sum(left_sizes)
            if sum(left_sizes) >= MIN_SPLITTER_TOTAL
            else sum(MONITOR_DEFAULT_VERTICAL)
        )
        if collapsed:
            if sum(left_sizes) >= MIN_SPLITTER_TOTAL and left_sizes[1] > handle_h + 8:
                self._pre_collapse_left_sizes = list(left_sizes)
            self._left_splitter.setSizes([max(total - handle_h, MIN_SPLITTER_TOTAL), handle_h])
        else:
            self._restore_left_splitter_sizes()
        self._emit_layout_changed()
        if notify_controller and self._monitor_controller is not None:
            self._monitor_controller.persist_waterfall_panel_collapsed(collapsed)

    def _on_waterfall_collapse_requested(self, collapsed: bool) -> None:
        self.set_waterfall_panel_collapsed(collapsed, notify_controller=True)

    @staticmethod
    def _create_panel_content(module_id: str, panel_id: str, on_state_changed=None):
        if module_id == "monitor":
            if panel_id == "lista":
                from gui.monitor.monitor_spectrum_widget import MonitorSpectrumWidget

                return MonitorSpectrumWidget(module_id, panel_id)
            if panel_id == "acciones":
                from gui.monitor.monitor_waterfall_widget import MonitorWaterfallWidget

                return MonitorWaterfallWidget(module_id, panel_id)
            if panel_id == "propiedades":
                from gui.monitor.monitor_config_panel import MonitorConfigPanel

                return MonitorConfigPanel(module_id, panel_id)
        if module_id == "inventario_rf":
            if panel_id == "lista":
                from gui.inventory_list_panel import InventoryListPanel

                return InventoryListPanel(
                    module_id, panel_id, on_state_changed=on_state_changed
                )
            if panel_id == "propiedades":
                from gui.inventory_properties_panel import InventoryPropertiesPanel

                return InventoryPropertiesPanel(module_id, panel_id)
            if panel_id == "acciones":
                from gui.inventory_actions_panel import InventoryActionsPanel

                return InventoryActionsPanel(module_id, panel_id)
        return PlaceholderPanelWidget(module_id, panel_id)

    def get_inventory_panel_contents(self):
        """Devuelve (lista, propiedades, acciones) del módulo inventario."""
        from gui.inventory_actions_panel import InventoryActionsPanel
        from gui.inventory_list_panel import InventoryListPanel
        from gui.inventory_properties_panel import InventoryPropertiesPanel

        if self.module_id != "inventario_rf":
            return None, None, None
        lista = self._panels["lista"].content
        propiedades = self._panels["propiedades"].content
        acciones = self._panels["acciones"].content
        if not isinstance(lista, InventoryListPanel):
            return None, None, None
        if not isinstance(propiedades, InventoryPropertiesPanel):
            return None, None, None
        if not isinstance(acciones, InventoryActionsPanel):
            return None, None, None
        return lista, propiedades, acciones

    def focus_properties_panel(self) -> None:
        if self.module_id != "inventario_rf":
            return
        panel = self._panels["propiedades"]
        if not panel.isVisible():
            panel.setVisible(True)
        panel.content.setFocus(Qt.FocusReason.ShortcutFocusReason)

    def set_inventory_resolver(
        self,
        resolver: Optional[Callable[[Optional[Dict[str, Any]]], Optional[Dict[str, Any]]]],
    ) -> None:
        if self.module_id != "inventario_rf":
            return
        self._inventory_resolver = resolver

    def set_channelization_service(self, service) -> None:
        if self.module_id != "inventario_rf":
            return
        _, prop, _ = self.get_inventory_panel_contents()
        if prop is not None and hasattr(prop, "set_channelization_service"):
            prop.set_channelization_service(service)

    def _emit_layout_changed(self, *_args) -> None:
        self._cache_splitter_sizes()
        if self._on_layout_changed:
            self._on_layout_changed()

    def _cache_splitter_sizes(self) -> None:
        if self._maximized_panel:
            return
        main_sizes = self._main_splitter.sizes()
        left_sizes = self._left_splitter.sizes()
        if sum(main_sizes) >= MIN_SPLITTER_TOTAL:
            if self.module_id == "monitor":
                if (
                    not self._properties_collapsed
                    and not self._is_side_column_view_hidden()
                    and main_sizes[1] > SIDE_PANEL_HANDLE_WIDTH + 8
                ):
                    self._last_good_main_sizes = main_sizes
            else:
                self._last_good_main_sizes = main_sizes
        if sum(left_sizes) >= MIN_SPLITTER_TOTAL:
            if self.module_id == "monitor":
                if (
                    not self._waterfall_collapsed
                    and not self._is_waterfall_stack_view_hidden()
                    and left_sizes[1] > WATERFALL_HANDLE_HEIGHT + 8
                ):
                    self._last_good_left_sizes = left_sizes
            else:
                self._last_good_left_sizes = left_sizes

    def _valid_sizes(self, sizes: list[int], fallback: list[int]) -> list[int]:
        if isinstance(sizes, list) and len(sizes) == 2 and sum(sizes) >= MIN_SPLITTER_TOTAL:
            return sizes
        return list(fallback)

    def _capture_panel_content_state(self) -> Dict[str, Any]:
        if self.module_id == "monitor" and self._monitor_controller is not None:
            self._monitor_controller.flush_persisted_state()
            return {"monitor": self._monitor_controller.get_persisted_params()}
        if self.module_id != "inventario_rf":
            return {}
        from gui.inventory_list_panel import InventoryListPanel

        lista = self._panels["lista"].content
        if isinstance(lista, InventoryListPanel):
            return {"lista": lista.save_content_state()}
        return {}

    def _apply_panel_content_state(self, panel_content: Dict[str, Any]) -> None:
        if not panel_content:
            return
        if self.module_id == "monitor" and self._monitor_controller is not None:
            monitor = panel_content.get("monitor")
            if isinstance(monitor, dict):
                self._monitor_controller.load_persisted_params(monitor)
            return
        from gui.inventory_list_panel import InventoryListPanel

        lista_state = panel_content.get("lista")
        if not isinstance(lista_state, dict):
            return
        lista = self._panels["lista"].content
        if isinstance(lista, InventoryListPanel):
            lista.restore_content_state(lista_state)

    def _capture_layout_state(self) -> Dict[str, Any]:
        state = {
            "panel_visibility": {
                panel_id: not panel.isHidden() for panel_id, panel in self._panels.items()
            },
            "splitter_main": self._valid_sizes(
                self._main_splitter.sizes(), self._last_good_main_sizes
            ),
            "splitter_left": self._valid_sizes(
                self._left_splitter.sizes(), self._last_good_left_sizes
            ),
            "left_column_visible": self._left_splitter.isVisible(),
        }
        panel_content = self._capture_panel_content_state()
        if panel_content:
            state["panel_content"] = panel_content
        return state

    def _apply_layout_state(self, state: Dict[str, Any]) -> None:
        visibility = state.get("panel_visibility") or {}
        for panel_id, panel in self._panels.items():
            if panel_id not in visibility:
                continue
            want_visible = bool(visibility[panel_id])
            if self.module_id == "monitor":
                self._set_monitor_panel_view_visible(panel_id, want_visible)
            else:
                panel.setVisible(want_visible)

        left_visible = state.get("left_column_visible")
        if isinstance(left_visible, bool):
            self._left_splitter.setVisible(left_visible)
        else:
            self._left_splitter.setVisible(True)

        main_sizes = state.get("splitter_main")
        if isinstance(main_sizes, list) and len(main_sizes) == 2:
            self._main_splitter.setSizes(
                self._valid_sizes(main_sizes, self._last_good_main_sizes)
            )

        left_sizes = state.get("splitter_left")
        if isinstance(left_sizes, list) and len(left_sizes) == 2:
            self._left_splitter.setSizes(
                self._valid_sizes(left_sizes, self._last_good_left_sizes)
            )

        self._cache_splitter_sizes()
        self._apply_panel_content_state(state.get("panel_content") or {})

    def _update_panel_header_states(self) -> None:
        for panel_id, panel in self._panels.items():
            panel.set_header_maximized(self._maximized_panel == panel_id)

    def _apply_maximize_layout(self, panel_id: str) -> None:
        for pid, panel in self._panels.items():
            panel.setVisible(pid == panel_id)
        self._left_splitter.setVisible(panel_id != "propiedades")

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.ensure_layout_visible()

    def get_panel(self, panel_id: str) -> ModulePanelFrame:
        return self._panels[panel_id]

    def get_panels(self) -> Dict[str, ModulePanelFrame]:
        return dict(self._panels)

    def is_panel_maximized(self, panel_id: str) -> bool:
        return self._maximized_panel == panel_id

    def get_maximized_panel(self) -> Optional[str]:
        return self._maximized_panel

    def _on_panel_close_requested(self, panel_id: str) -> None:
        if self._maximized_panel == panel_id:
            self.restore_from_maximize()
        self.set_panel_visible(panel_id, False)

    def toggle_maximize_panel(self, panel_id: str) -> None:
        if panel_id not in PANEL_IDS:
            return
        if self._maximized_panel == panel_id:
            self.restore_from_maximize()
            return
        self.maximize_panel(panel_id)

    def maximize_panel(self, panel_id: str) -> None:
        if panel_id not in PANEL_IDS:
            return
        if not self._panels[panel_id].isVisible():
            self.set_panel_visible(panel_id, True)
        if self._maximized_panel is None:
            self._pre_maximize_state = self._capture_layout_state()
        self._maximized_panel = panel_id
        self._apply_maximize_layout(panel_id)
        self._update_panel_header_states()
        self._emit_layout_changed()

    def restore_from_maximize(self) -> None:
        if self._maximized_panel is None:
            return
        state = self._pre_maximize_state or {}
        self._maximized_panel = None
        self._pre_maximize_state = None
        self._apply_layout_state(state)
        self._update_panel_header_states()
        self.ensure_layout_visible()
        self._emit_layout_changed()

    def set_panel_visible(self, panel_id: str, visible: bool) -> None:
        if panel_id not in self._panels:
            return
        if visible and self._maximized_panel and self._maximized_panel != panel_id:
            self.restore_from_maximize()
        elif not visible and self._maximized_panel == panel_id:
            self.restore_from_maximize()

        if self.module_id == "monitor":
            self._set_monitor_panel_view_visible(panel_id, visible)
        else:
            self._panels[panel_id].setVisible(visible)
            if visible and panel_id != "propiedades":
                self._left_splitter.setVisible(True)

        self._update_panel_header_states()
        self.ensure_layout_visible()
        self._emit_layout_changed()

    def reset_layout(self) -> None:
        self._maximized_panel = None
        self._pre_maximize_state = None
        for panel in self._panels.values():
            panel.setVisible(True)
        self._left_splitter.setVisible(True)
        if self.module_id == "monitor":
            self._properties_collapsed = False
            self._waterfall_collapsed = False
            if self._side_column is not None:
                self._side_column.setVisible(True)
            if self._side_handle is not None:
                self._side_handle.setVisible(True)
                self._side_handle.set_collapsed(False)
            if self._waterfall_stack is not None:
                self._waterfall_stack.setVisible(True)
            if self._wf_handle is not None:
                self._wf_handle.setVisible(True)
                self._wf_handle.set_collapsed(False)
            self._restore_properties_panel_constraints(self._panels["propiedades"])
            wf = self._panels["acciones"]
            wf.setMinimumHeight(max(int(self._pre_collapse_wf_min_height or 0), 100))
            wf.setMaximumHeight(16777215)
            wf.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            self._main_splitter.setSizes(list(MONITOR_DEFAULT_HORIZONTAL))
            self._left_splitter.setSizes(list(MONITOR_DEFAULT_VERTICAL))
        else:
            self._main_splitter.setSizes(list(DEFAULT_HORIZONTAL))
            self._left_splitter.setSizes(list(DEFAULT_VERTICAL))
        self._update_panel_header_states()
        self._cache_splitter_sizes()

    def ensure_layout_visible(self) -> None:
        """Evita paneles colapsados al volver a una pestaña oculta."""
        if self._maximized_panel:
            self._apply_maximize_layout(self._maximized_panel)
            self._update_panel_header_states()
            return

        main_sizes = self._main_splitter.sizes()
        left_sizes = self._left_splitter.sizes()
        if sum(main_sizes) < MIN_SPLITTER_TOTAL:
            self._main_splitter.setSizes(list(self._last_good_main_sizes))
        if sum(left_sizes) < MIN_SPLITTER_TOTAL:
            self._left_splitter.setSizes(list(self._last_good_left_sizes))
        if sum(self._main_splitter.sizes()) < MIN_SPLITTER_TOTAL:
            self.reset_layout()
            return
        if self.module_id == "monitor":
            prop = self._panels.get("propiedades")
            if (
                not self._is_side_column_view_hidden()
                and prop is not None
                and prop.isVisible()
                and not self._properties_collapsed
            ):
                side_w = self._main_splitter.sizes()[1]
                min_side = MIN_MONITOR_SIDE_WIDTH + SIDE_PANEL_HANDLE_WIDTH
                if side_w < min_side:
                    self._restore_main_splitter_sizes()
                    self._schedule_monitor_config_layout_refresh()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self.module_id != "monitor" or self._properties_collapsed:
            return
        if self._is_side_column_view_hidden():
            return
        prop = self._panels.get("propiedades")
        if prop is None or not prop.isVisible():
            return
        main_sizes = self._main_splitter.sizes()
        if len(main_sizes) == 2 and main_sizes[1] < MIN_MONITOR_SIDE_WIDTH + SIDE_PANEL_HANDLE_WIDTH:
            QTimer.singleShot(0, self._restore_main_splitter_sizes)

    def save_state(self) -> Dict[str, Any]:
        self._cache_splitter_sizes()
        state = {
            "panel_visibility": {
                panel_id: not panel.isHidden() for panel_id, panel in self._panels.items()
            },
            "splitter_main": self._valid_sizes(
                self._main_splitter.sizes(), self._last_good_main_sizes
            ),
            "splitter_left": self._valid_sizes(
                self._left_splitter.sizes(), self._last_good_left_sizes
            ),
            "maximized_panel": self._maximized_panel,
        }
        if self._maximized_panel and self._pre_maximize_state:
            state["pre_maximize"] = dict(self._pre_maximize_state)
        panel_content = self._capture_panel_content_state()
        if panel_content:
            state["panel_content"] = panel_content
        return state

    def restore_state(self, config: Dict[str, Any]) -> None:
        if not config:
            return

        self._maximized_panel = None
        self._pre_maximize_state = None

        visibility = config.get("panel_visibility") or {}
        for panel_id, panel in self._panels.items():
            if panel_id not in visibility:
                continue
            want_visible = bool(visibility[panel_id])
            if self.module_id == "monitor":
                self._set_monitor_panel_view_visible(panel_id, want_visible)
            else:
                panel.setVisible(want_visible)

        self._left_splitter.setVisible(True)
        main_sizes = config.get("splitter_main")
        if isinstance(main_sizes, list) and len(main_sizes) == 2:
            self._main_splitter.setSizes(
                self._valid_sizes(main_sizes, self._last_good_main_sizes)
            )

        left_sizes = config.get("splitter_left")
        if isinstance(left_sizes, list) and len(left_sizes) == 2:
            self._left_splitter.setSizes(
                self._valid_sizes(left_sizes, self._last_good_left_sizes)
            )

        pre_maximize = config.get("pre_maximize")
        if isinstance(pre_maximize, dict):
            self._pre_maximize_state = pre_maximize

        maximized = config.get("maximized_panel")
        if isinstance(maximized, str) and maximized in PANEL_IDS:
            if self._pre_maximize_state is None:
                self._pre_maximize_state = self._capture_layout_state()
            self._maximized_panel = maximized
            self._apply_maximize_layout(maximized)
        else:
            self._cache_splitter_sizes()

        self._update_panel_header_states()
        self.ensure_layout_visible()
        self._apply_panel_content_state(config.get("panel_content") or {})

    def apply_panel_themes(self) -> None:
        for panel in self._panels.values():
            panel.apply_visual_theme()

    def recargar_textos(self) -> None:
        for panel in self._panels.values():
            panel.recargar_textos()
