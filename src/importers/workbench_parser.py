"""Importación de shows Shure Wireless Workbench (.shw)."""
from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional

from importers.workbench_models import (
    WorkbenchChannel,
    WorkbenchContact,
    WorkbenchCoordination,
    WorkbenchCoordinationAssignment,
    WorkbenchCoordinationChannel,
    WorkbenchDevice,
    WorkbenchShow,
    WorkbenchShowInfo,
)

WORKBENCH_FILE_FILTER = "Shure Wireless Workbench (*.shw)"


class WorkbenchImportError(Exception):
    """Error al leer o interpretar un fichero .shw."""


def frequency_khz_to_mhz(value: Optional[int]) -> Optional[float]:
    """Workbench almacena frecuencias como entero en unidades de 1 kHz."""
    if value is None:
        return None
    return round(value / 1000.0, 3)


def _text(element, tag: str, default: str = "") -> str:
    child = element.find(tag)
    if child is None or child.text is None:
        return default
    return child.text.strip()


def _typed_text(element, tag: str, default: str = "") -> str:
    child = element.find(tag)
    if child is None:
        return default
    if child.text is None:
        return default
    return child.text.strip()


def _bool_text(element, tag: str, default: bool = False) -> bool:
    raw = _text(element, tag, "").lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes"}


def _int_text(element, tag: str) -> Optional[int]:
    raw = _text(element, tag, "")
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def _float_text(element, tag: str) -> Optional[float]:
    raw = _text(element, tag, "")
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def parse_workbench_show(path: str | Path) -> WorkbenchShow:
    """
    Parsea un fichero `.shw` de Wireless Workbench.

    Fase 2: inventario + metadatos del show. Coordinación y monitor se añadirán después.
    """
    resolved = Path(path).resolve()
    if resolved.suffix.lower() != ".shw":
        raise WorkbenchImportError("El fichero debe tener extensión .shw")

    try:
        tree = ET.parse(resolved)
    except ET.ParseError as exc:
        raise WorkbenchImportError(f"XML inválido: {exc}") from exc

    root = tree.getroot()
    if root.tag != "show":
        raise WorkbenchImportError("Raíz XML esperada: <show>")

    show = WorkbenchShow(
        source_path=str(resolved),
        workbench_version=root.get("appl_version", ""),
        show_date=root.get("date", ""),
        show_time=root.get("time", ""),
        has_coordination=root.find("coordination_info") is not None,
        has_monitoring=root.find("monitoring_info") is not None,
    )

    show.info = _parse_show_properties(root.find("show_properties"))
    show.devices = _parse_inventory(root.find("inventory"))
    show.coordination = _parse_coordination(root.find("coordination_info"))
    if root.find("coordinated_data_root") is not None:
        _merge_coordinated_assignments(show, root.find("coordinated_data_root"))
    return show


def _parse_show_properties(node: Optional[ET.Element]) -> WorkbenchShowInfo:
    if node is None:
        return WorkbenchShowInfo()

    show_info = node.find("show_info")
    poc = node.find("point_of_contact_info")
    contact = WorkbenchContact()
    if poc is not None:
        contact = WorkbenchContact(
            name=_text(poc, "name"),
            email=_text(poc, "email"),
            phone=_text(poc, "phone"),
            address=_text(poc, "address"),
        )

    return WorkbenchShowInfo(
        name=_text(show_info, "name") if show_info is not None else "",
        customer=_text(show_info, "customer") if show_info is not None else "",
        contact=contact,
        notes=_text(node, "notes"),
    )


def _parse_inventory(node: Optional[ET.Element]) -> list[WorkbenchDevice]:
    if node is None:
        return []

    devices: list[WorkbenchDevice] = []
    for device_el in node.findall("device"):
        id_el = device_el.find("id")
        device = WorkbenchDevice(
            id=id_el.text.strip() if id_el is not None and id_el.text else "",
            dcid=id_el.get("dcid", "") if id_el is not None else "",
            device_name=_typed_text(device_el, "device_name"),
            series=_text(device_el, "series"),
            model=_typed_text(device_el, "model"),
            manufacturer=_typed_text(device_el, "manufacturer"),
            band=_typed_text(device_el, "band"),
            zone=_typed_text(device_el, "zone"),
        )

        for channel_el in device_el.findall("channel"):
            number_raw = channel_el.get("number", "0")
            try:
                number = int(number_raw)
            except ValueError:
                number = 0
            freq_khz = _int_text(channel_el, "frequency")
            device.channels.append(
                WorkbenchChannel(
                    number=number,
                    name=_typed_text(channel_el, "channel_name"),
                    frequency_khz=freq_khz,
                    frequency_mhz=frequency_khz_to_mhz(freq_khz),
                    color=_int_text(channel_el, "color"),
                    audio_gain=_float_text(channel_el, "audio_gain"),
                    audio_mute=_bool_text(channel_el, "audio_mute"),
                )
            )

        devices.append(device)

    return devices


def _parse_bool_attr(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes"}


def _parse_coordination(node: Optional[ET.Element]) -> Optional[WorkbenchCoordination]:
    if node is None:
        return None

    coordination = WorkbenchCoordination()
    channel_mgmt = node.find("channel_management")
    if channel_mgmt is not None:
        channels_node = channel_mgmt.find("channels")
        if channels_node is not None:
            for id_el in channels_node.findall("id"):
                text = (id_el.text or "").strip()
                if not text:
                    continue
                coordination.channels.append(
                    WorkbenchCoordinationChannel(
                        workbench_id=text,
                        coordination_include=_parse_bool_attr(
                            id_el.get("coordination_include"), True
                        ),
                        active_channel=_parse_bool_attr(id_el.get("active_channel"), False),
                    )
                )

    scan_data = node.find("scan_data")
    if scan_data is not None:
        coordination.scan_threshold_db = _float_text(scan_data, "threshold")
        coordination.scan_higher_threshold_db = _float_text(scan_data, "higher_threshold")
        file_info = scan_data.find("file_info")
        if file_info is not None:
            coordination.scan_file_name = _text(file_info, "name")

    global_exclusions = node.find("global_exclusions")
    if global_exclusions is not None:
        freq_ranges = global_exclusions.find("freq_range_exclusions")
        if freq_ranges is not None:
            coordination.exclusion_range_count = len(freq_ranges.findall("range"))

    band_planning = node.find("band_planning")
    if band_planning is not None:
        coordination.band_plan_country = _text(band_planning, "country")

    return coordination


def _merge_coordinated_assignments(show: WorkbenchShow, node: Optional[ET.Element]) -> None:
    if node is None:
        return
    if show.coordination is None:
        show.coordination = WorkbenchCoordination()

    mic_channels = node.find("mic_channels")
    if mic_channels is None:
        return

    assignments: list[WorkbenchCoordinationAssignment] = []
    for entry in mic_channels.findall("freq_entry"):
        workbench_id = entry.get("id", "").strip()
        if not workbench_id:
            continue
        dev_category = entry.find("dev_category")
        if dev_category is not None:
            dev_types = [
                child.text.strip()
                for child in dev_category.findall("dev_type")
                if child.text and child.text.strip()
            ]
            if dev_types:
                show.channel_dev_types[workbench_id] = dev_types
        freq_khz = _int_text(entry, "value")
        compat = entry.find("compat_key")
        assignments.append(
            WorkbenchCoordinationAssignment(
                workbench_id=workbench_id,
                frequency_khz=freq_khz,
                frequency_mhz=frequency_khz_to_mhz(freq_khz) if freq_khz else None,
                series=_text(compat, "series") if compat is not None else "",
                model=_text(entry, "model"),
                band=_text(compat, "band") if compat is not None else "",
                zone=_text(compat, "zone") if compat is not None else "",
                channel_name=_text(entry, "source_name"),
                channel_number=_int_text(entry, "chann_num") or -1,
            )
        )
    show.coordination.assignments = assignments


def apply_workbench_inventory_to_project(project, show: WorkbenchShow) -> None:
    """Volca el inventario importado en un modelo Project en memoria."""
    if show.info.name:
        project.name = show.info.name
    module = project.modules.setdefault("inventario_rf", {})
    module["equipos"] = show.to_inventory_dicts()
    module["import_meta"] = {
        "source": "workbench",
        "source_path": show.source_path,
        "workbench_version": show.workbench_version,
        "customer": show.info.customer,
    }


def apply_workbench_coordination_to_project(
    project,
    show: WorkbenchShow,
    *,
    merge_inventory_flags: bool = True,
) -> None:
    """Importa datos de coordinación Workbench al módulo coordinacion."""
    if show.coordination is None:
        return

    coord = show.coordination
    module = project.modules.setdefault("coordinacion", {})
    module["import_meta"] = {
        "source": "workbench",
        "source_path": show.source_path,
        "workbench_version": show.workbench_version,
    }
    module["channel_flags"] = [
        {
            "workbench_id": item.workbench_id,
            "coordination_include": item.coordination_include,
            "active_channel": item.active_channel,
        }
        for item in coord.channels
    ]
    module["assignments"] = [
        {
            "workbench_id": item.workbench_id,
            "frequency_khz": item.frequency_khz,
            "frequency_mhz": item.frequency_mhz,
            "series": item.series,
            "model": item.model,
            "band": item.band,
            "zone": item.zone,
            "channel_name": item.channel_name,
            "channel_number": item.channel_number,
        }
        for item in coord.assignments
        if item.frequency_khz
    ]
    module["scan"] = {
        "threshold_db": coord.scan_threshold_db,
        "higher_threshold_db": coord.scan_higher_threshold_db,
        "file_name": coord.scan_file_name,
    }
    module["exclusions_summary"] = {
        "freq_range_count": coord.exclusion_range_count,
        "band_plan_country": coord.band_plan_country,
    }

    if not merge_inventory_flags:
        return

    flags_by_id = {item["workbench_id"]: item for item in module["channel_flags"]}
    equipos = project.modules.get("inventario_rf", {}).get("equipos") or []
    for item in equipos:
        channel_id = item.get("workbench_channel_id") or item.get("workbench_device_id")
        if not channel_id:
            continue
        flag = flags_by_id.get(channel_id)
        if flag:
            item["coordination_include"] = flag["coordination_include"]
            item["coordination_active"] = flag["active_channel"]
