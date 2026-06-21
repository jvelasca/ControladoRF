"""Árbol de estructura del proyecto para el explorador (Herramientas)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from core.project_model import MODULE_IDS, Project
from i18n.json_translation import tr


@dataclass
class ProjectStructureNode:
    label: str
    detail: str = ""
    children: List["ProjectStructureNode"] = field(default_factory=list)


def build_project_structure_tree(
    project: Project,
    *,
    file_path: Optional[str] = None,
    is_dirty: bool = False,
    active_module: str = "inventario_rf",
) -> ProjectStructureNode:
    """Construye el árbol de nodos a partir del modelo de proyecto."""
    dirty_mark = " ●" if is_dirty else ""
    file_label = file_path or tr("project_file_unsaved")

    root = ProjectStructureNode(
        label=f"{project.name}{dirty_mark}",
        detail=file_label,
    )

    meta = ProjectStructureNode(label=tr("structure_metadata"))
    meta.children.append(ProjectStructureNode(label=tr("structure_show_name"), detail=project.name))
    meta.children.append(ProjectStructureNode(label=tr("structure_format"), detail=project.format_version))
    meta.children.append(
        ProjectStructureNode(label=tr("structure_modified"), detail=project.modified_at)
    )
    import_meta = project.modules.get("inventario_rf", {}).get("import_meta") or {}
    if import_meta:
        if customer := import_meta.get("customer"):
            meta.children.append(
                ProjectStructureNode(label=tr("structure_customer"), detail=str(customer))
            )
        if wb_ver := import_meta.get("workbench_version"):
            meta.children.append(
                ProjectStructureNode(label=tr("structure_workbench_version"), detail=str(wb_ver))
            )
        if source := import_meta.get("source_path"):
            meta.children.append(
                ProjectStructureNode(label=tr("structure_import_source"), detail=str(source))
            )
    root.children.append(meta)

    modules_node = ProjectStructureNode(label=tr("structure_modules"))
    for module_id in MODULE_IDS:
        modules_node.children.append(_build_module_node(project, module_id))
    root.children.append(modules_node)

    ui_node = ProjectStructureNode(label=tr("structure_ui"))
    ui_node.children.append(
        ProjectStructureNode(
            label=tr("structure_active_module"),
            detail=tr(_module_label_key(active_module)),
        )
    )
    for module_id in MODULE_IDS:
        ui_state = project.get_module_ui(module_id)
        if ui_state:
            ui_node.children.append(_build_ui_module_node(module_id, ui_state))
    root.children.append(ui_node)

    return root


def _module_label_key(module_id: str) -> str:
    return {
        "inventario_rf": "module_inventario_rf",
        "coordinacion": "module_coordinacion",
        "monitor": "module_monitor",
    }.get(module_id, module_id)


def _build_module_node(project: Project, module_id: str) -> ProjectStructureNode:
    module_data = project.modules.get(module_id) or {}
    title = tr(_module_label_key(module_id))

    if module_id == "inventario_rf":
        equipos = module_data.get("equipos") or []
        node = ProjectStructureNode(
            label=title,
            detail=tr("structure_channel_count", count=len(equipos)),
        )
        by_device: Dict[str, List[Dict[str, Any]]] = {}
        for item in equipos:
            key = _device_group_key(item)
            by_device.setdefault(key, []).append(item)

        for device_key in sorted(by_device.keys()):
            items = by_device[device_key]
            first = items[0]
            device_node = ProjectStructureNode(
                label=device_key,
                detail=tr("structure_device_channels", count=len(items)),
            )
            for item in sorted(items, key=lambda x: x.get("channel_number", 0)):
                ch_name = item.get("channel_name") or tr("structure_unnamed_channel")
                freq = item.get("frequency_mhz")
                freq_text = f"{freq:.3f} MHz" if isinstance(freq, (int, float)) else "—"
                device_node.children.append(
                    ProjectStructureNode(
                        label=f"Ch {item.get('channel_number', '?')}: {ch_name}",
                        detail=freq_text,
                    )
                )
            node.children.append(device_node)
        return node

    if module_id == "coordinacion":
        assignments = module_data.get("assignments") or []
        channel_flags = module_data.get("channel_flags") or []
        scan = module_data.get("scan") or {}
        node = ProjectStructureNode(
            label=title,
            detail=tr("structure_coord_assignments", count=len(assignments)),
        )
        if channel_flags:
            included = sum(1 for item in channel_flags if item.get("coordination_include"))
            active = sum(1 for item in channel_flags if item.get("active_channel"))
            node.children.append(
                ProjectStructureNode(
                    label=tr("structure_coord_channels"),
                    detail=tr(
                        "structure_coord_channels_detail",
                        included=included,
                        active=active,
                        total=len(channel_flags),
                    ),
                )
            )
        if scan.get("file_name") or scan.get("threshold_db") is not None:
            scan_parts = []
            if scan.get("file_name"):
                scan_parts.append(str(scan["file_name"]))
            if scan.get("threshold_db") is not None:
                scan_parts.append(f"{scan['threshold_db']} dBm")
            node.children.append(
                ProjectStructureNode(
                    label=tr("structure_coord_scan"),
                    detail=" · ".join(scan_parts) or "—",
                )
            )
        exclusions = module_data.get("exclusions_summary") or {}
        if exclusions.get("freq_range_count"):
            node.children.append(
                ProjectStructureNode(
                    label=tr("structure_coord_exclusions"),
                    detail=tr(
                        "structure_coord_exclusion_ranges",
                        count=exclusions.get("freq_range_count", 0),
                    ),
                )
            )
        return node

    return ProjectStructureNode(label=title, detail=tr("structure_empty_module"))


def _device_group_key(item: Dict[str, Any]) -> str:
    model = item.get("model") or "?"
    device_name = item.get("device_name") or ""
    series = item.get("series") or ""
    if device_name:
        return f"{model} — {device_name}"
    if series:
        return f"{series} {model}".strip()
    return str(model)


def _build_ui_module_node(module_id: str, ui_state: Dict[str, Any]) -> ProjectStructureNode:
    title = tr(_module_label_key(module_id))
    visibility = ui_state.get("panel_visibility") or {}
    visible = sum(1 for v in visibility.values() if v)
    total = len(visibility) or 3
    maximized = ui_state.get("maximized_panel")
    detail_parts = [tr("structure_panels_visible", visible=visible, total=total)]
    if maximized:
        detail_parts.append(tr("structure_panel_maximized", panel=str(maximized)))
    return ProjectStructureNode(label=title, detail=" · ".join(detail_parts))
