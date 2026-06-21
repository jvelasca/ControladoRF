"""Exportación de la lista de inventario RF (CSV, JSON)."""
from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Sequence

from core.inventory_channel import equipos_from_project, normalize_equipo
from core.inventory_metadata import get_list_metadata

EXPORT_FORMAT_CSV = "csv"
EXPORT_FORMAT_JSON = "json"
EXPORT_FORMAT_PDF = "pdf"

EXPORT_FORMATS = (EXPORT_FORMAT_CSV, EXPORT_FORMAT_JSON, EXPORT_FORMAT_PDF)

LIST_METADATA_FIELDS = ("notes", "color", "locked")

CHANNEL_EXPORT_FIELDS: Sequence[str] = (
    "channel_number",
    "channel_name",
    "frequency_mhz",
    "band",
    "zone",
    "network",
    "model",
    "series",
    "manufacturer",
    "device_name",
    "device_type",
    "coordination_include",
    "coordination_active",
    "notes",
    "color",
    "locked",
    "channel_key",
    "source",
    "workbench_channel_id",
    "workbench_device_id",
    "db_id",
)


class InventoryExportError(Exception):
    """Error al exportar la lista de inventario."""


def build_inventory_list_export(
    project,
    *,
    project_name: str = "",
    exported_at: datetime | None = None,
) -> Dict[str, Any]:
    """Construye el documento exportable de la lista completa."""
    when = exported_at or datetime.now(timezone.utc)
    channels = [normalize_equipo(item) for item in equipos_from_project(project)]
    list_meta = get_list_metadata(project)
    return {
        "format_version": 1,
        "exported_at": when.replace(microsecond=0).isoformat(),
        "project_name": str(project_name or getattr(project, "name", "") or "").strip(),
        "list": {
            "metadata": {field: list_meta.get(field) for field in LIST_METADATA_FIELDS},
            "channel_count": len(channels),
            "channels": [_channel_record(item) for item in channels],
        },
    }


def export_inventory_json(document: Mapping[str, Any], path: str | Path) -> None:
    """Escribe el documento como JSON indentado."""
    target = Path(path)
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(document, ensure_ascii=False, indent=2)
        target.write_text(payload + "\n", encoding="utf-8")
    except OSError as exc:
        raise InventoryExportError(str(exc)) from exc


def export_inventory_csv(
    document: Mapping[str, Any],
    path: str | Path,
    *,
    field_labels: Mapping[str, str] | None = None,
    bool_labels: Mapping[bool, str] | None = None,
    value_formatters: Mapping[str, Any] | None = None,
) -> None:
    """Exporta canales en CSV plano con cabeceras legibles."""
    target = Path(path)
    labels = dict(field_labels or {})
    bool_map = bool_labels or {True: "true", False: "false"}
    formatters = dict(value_formatters or {})
    channels = _channels(document)
    header = [labels.get(field, field) for field in CHANNEL_EXPORT_FIELDS]
    rows: List[List[str]] = [header]
    for item in channels:
        row: List[str] = []
        for field in CHANNEL_EXPORT_FIELDS:
            value = item.get(field)
            if field in formatters:
                value = formatters[field](value)
            else:
                value = _format_export_value(field, value, bool_map)
            row.append(_csv_cell(value))
        rows.append(row)
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.writer(handle, delimiter=";", lineterminator="\n")
            writer.writerows(rows)
    except OSError as exc:
        raise InventoryExportError(str(exc)) from exc


def default_export_filename(project_name: str, export_format: str) -> str:
    """Nombre de fichero sugerido según proyecto y formato."""
    ext = _format_extension(export_format)
    stem = _safe_filename(project_name)
    if stem:
        return f"{stem}_inventario.{ext}"
    return f"inventario.{ext}"


def _format_extension(export_format: str) -> str:
    if export_format == EXPORT_FORMAT_JSON:
        return "json"
    if export_format == EXPORT_FORMAT_PDF:
        return "pdf"
    return "csv"


def _safe_filename(name: str) -> str:
    cleaned = "".join(char if char.isalnum() or char in "._- " else "_" for char in name)
    return cleaned.strip().replace(" ", "_")


def _channels(document: Mapping[str, Any]) -> List[Dict[str, Any]]:
    lista = document.get("list") or {}
    channels = lista.get("channels") or []
    return [item for item in channels if isinstance(item, dict)]


def _channel_record(item: Dict[str, Any]) -> Dict[str, Any]:
    return {field: item.get(field) for field in CHANNEL_EXPORT_FIELDS}


def _format_export_value(field: str, value: Any, bool_map: Mapping[bool, str]) -> Any:
    if field in ("coordination_include", "coordination_active", "locked"):
        return bool_map.get(bool(value), str(bool(value)))
    if value is None:
        return ""
    if isinstance(value, bool):
        return bool_map.get(value, str(value))
    return value


def _csv_cell(value: Any) -> str:
    if value is None:
        return ""
    return str(value)
