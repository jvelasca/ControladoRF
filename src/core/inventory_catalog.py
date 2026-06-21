"""Catálogo y agrupación del inventario RF (estilo Workbench)."""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Tuple

GROUP_NONE = "none"
GROUP_DEVICE_TYPE = "device_type"
GROUP_ZONE = "zone"
GROUP_NETWORK = "network"
GROUP_SERIES = "series"

GROUP_MODES = (
    GROUP_NONE,
    GROUP_DEVICE_TYPE,
    GROUP_ZONE,
    GROUP_NETWORK,
    GROUP_SERIES,
)

DEVICE_TYPE_MICROPHONE = "microphone"
DEVICE_TYPE_IEM = "iem"
DEVICE_TYPE_SPECTRUM = "spectrum_manager"
DEVICE_TYPE_ANTENNA = "antenna_accessory"
DEVICE_TYPE_CHARGER = "charger"
DEVICE_TYPE_INTERCOM = "intercom"
DEVICE_TYPE_OTHER = "other"

DEVICE_TYPE_ORDER = (
    DEVICE_TYPE_MICROPHONE,
    DEVICE_TYPE_IEM,
    DEVICE_TYPE_SPECTRUM,
    DEVICE_TYPE_ANTENNA,
    DEVICE_TYPE_CHARGER,
    DEVICE_TYPE_INTERCOM,
    DEVICE_TYPE_OTHER,
)

_TYPE_I18N = {
    DEVICE_TYPE_MICROPHONE: "inventory_type_microphone",
    DEVICE_TYPE_IEM: "inventory_type_iem",
    DEVICE_TYPE_SPECTRUM: "inventory_type_spectrum_manager",
    DEVICE_TYPE_ANTENNA: "inventory_type_antenna_accessory",
    DEVICE_TYPE_CHARGER: "inventory_type_charger",
    DEVICE_TYPE_INTERCOM: "inventory_type_intercom",
    DEVICE_TYPE_OTHER: "inventory_type_other",
}

_GROUP_I18N = {
    GROUP_NONE: "inventory_group_none",
    GROUP_DEVICE_TYPE: "inventory_group_type",
    GROUP_ZONE: "inventory_group_zone",
    GROUP_NETWORK: "inventory_group_network",
    GROUP_SERIES: "inventory_group_series",
}


def infer_device_type(
    model: str = "",
    series: str = "",
    *,
    channel_name: str = "",
) -> str:
    """Clasifica un equipo RF según modelo/serie (heurística alineada con Workbench)."""
    text = f"{series} {model}".upper()
    name = channel_name.upper()

    if any(token in text for token in ("PSM", "P10T", "P10R", "EP1", "EP2", "SR 2050", "SR2050")):
        return DEVICE_TYPE_IEM
    if "IEM" in name:
        return DEVICE_TYPE_IEM

    if any(token in text for token in ("AXT600", "ADX600", "WWB6", "SPECTRUM MANAGER")):
        return DEVICE_TYPE_SPECTRUM

    if any(
        token in text
        for token in ("UA844", "UA874", "UA833", "PA805", "COMBINER", "ANTENNA DISTRIB")
    ):
        return DEVICE_TYPE_ANTENNA

    if any(token in text for token in ("SBC", "CHARGER", "C1G", "C1L")):
        return DEVICE_TYPE_CHARGER
    if any(token in text for token in ("INTERCOM", "FSII", "RIEDEL", "BTR")):
        return DEVICE_TYPE_INTERCOM

    if any(token in text for token in ("EM 3732", "EM3732")):
        return DEVICE_TYPE_MICROPHONE

    if any(
        token in text
        for token in (
            "ULXD",
            "UHF",
            "UHFR",
            "QLX",
            "SLX",
            "AXIENT",
            "AD4",
            "AD2",
            "AD1",
            "MXW",
            "BLX",
            "EW ",
            "EW5",
            "SKM",
            "SM58",
            "HANDHELD",
            "BODYPACK",
            "UR4",
        )
    ):
        return DEVICE_TYPE_MICROPHONE
    return DEVICE_TYPE_OTHER


def device_type_from_workbench_types(dev_types: Iterable[str]) -> str:
    """Mapea `dev_type` de Workbench al tipo de agrupación de CONTROLADORF."""
    normalized = {str(value).strip().casefold() for value in dev_types if str(value).strip()}
    if not normalized:
        return DEVICE_TYPE_OTHER

    if "in ear monitor" in normalized:
        return DEVICE_TYPE_IEM
    if any("spectrum" in value for value in normalized):
        return DEVICE_TYPE_SPECTRUM
    if normalized.intersection({"antenna", "combiner", "antenna accessory"}):
        return DEVICE_TYPE_ANTENNA
    if "charger" in normalized:
        return DEVICE_TYPE_CHARGER
    if "intercom" in normalized:
        return DEVICE_TYPE_INTERCOM
    if "microphone" in normalized:
        return DEVICE_TYPE_MICROPHONE
    if "receiver" in normalized:
        return DEVICE_TYPE_MICROPHONE
    if "transmitter" in normalized:
        return DEVICE_TYPE_IEM
    return DEVICE_TYPE_OTHER


def resolve_device_type(item: Dict[str, Any]) -> str:
    """Tipo final del canal: Workbench > heurística sobre metadatos del item."""
    workbench_types = item.get("workbench_dev_types")
    if isinstance(workbench_types, list) and workbench_types:
        return device_type_from_workbench_types(workbench_types)
    return infer_device_type(
        str(item.get("model") or ""),
        str(item.get("series") or ""),
        channel_name=str(item.get("channel_name") or ""),
    )


def enrich_equipo_metadata(item: Dict[str, Any]) -> Dict[str, Any]:
    """Añade metadatos derivados si faltan (proyectos legacy o import parcial)."""
    model = str(item.get("model") or "")
    series = str(item.get("series") or "")
    item["device_type"] = resolve_device_type(item)
    if not item.get("network"):
        item["network"] = "Default"
    if not item.get("zone"):
        item["zone"] = "Default"
    if not item.get("series"):
        item["series"] = series or "—"
    if not item.get("modulation_class"):
        item["modulation_class"] = infer_modulation_class(item)
    return item


def infer_modulation_class(item: Dict[str, Any]) -> str:
    """Clasifica modulación RF del canal (analógico vs digital)."""
    from core.monitor.supervision.digital_supervision import infer_modulation_class as _infer

    return _infer(item)


def filter_equipos(equipos: Iterable[Dict[str, Any]], query: str) -> List[Dict[str, Any]]:
    needle = query.strip().casefold()
    if not needle:
        return [enrich_equipo_metadata(dict(item)) for item in equipos]

    filtered: List[Dict[str, Any]] = []
    for raw in equipos:
        item = enrich_equipo_metadata(dict(raw))
        haystack = " ".join(
            str(item.get(key, ""))
            for key in (
                "channel_name",
                "channel_number",
                "device_name",
                "model",
                "series",
                "band",
                "zone",
                "network",
                "frequency_mhz",
                "device_type",
            )
        ).casefold()
        if needle in haystack:
            filtered.append(item)
    return filtered


def group_key_for_item(item: Dict[str, Any], group_mode: str) -> str:
    if group_mode == GROUP_DEVICE_TYPE:
        return str(item.get("device_type") or DEVICE_TYPE_OTHER)
    if group_mode == GROUP_ZONE:
        return str(item.get("zone") or "Default")
    if group_mode == GROUP_NETWORK:
        return str(item.get("network") or "Default")
    if group_mode == GROUP_SERIES:
        return str(item.get("series") or "—")
    return GROUP_NONE


def group_label_for_key(group_mode: str, key: str, tr) -> str:
    if group_mode == GROUP_DEVICE_TYPE:
        i18n_key = _TYPE_I18N.get(key, "inventory_type_other")
        return tr(i18n_key)
    if key in ("", GROUP_NONE):
        return tr("inventory_group_all")
    return key


def sort_group_keys(group_mode: str, keys: Iterable[str]) -> List[str]:
    unique = list(dict.fromkeys(keys))
    if group_mode == GROUP_DEVICE_TYPE:
        order = {value: index for index, value in enumerate(DEVICE_TYPE_ORDER)}
        return sorted(unique, key=lambda value: order.get(value, len(order)))
    return sorted(unique, key=lambda value: value.casefold())


def build_inventory_groups(
    equipos: Iterable[Dict[str, Any]],
    *,
    group_mode: str,
    tr,
) -> List[Tuple[str, str, List[Dict[str, Any]]]]:
    """Devuelve [(group_key, group_label, items), ...] listo para pintar tablas."""
    items = [enrich_equipo_metadata(dict(item)) for item in equipos]
    if group_mode == GROUP_NONE:
        return [(GROUP_NONE, tr("inventory_group_all"), items)]

    buckets: Dict[str, List[Dict[str, Any]]] = {}
    for item in items:
        key = group_key_for_item(item, group_mode)
        buckets.setdefault(key, []).append(item)

    groups: List[Tuple[str, str, List[Dict[str, Any]]]] = []
    for key in sort_group_keys(group_mode, buckets.keys()):
        label = group_label_for_key(group_mode, key, tr)
        groups.append((key, label, buckets[key]))
    return groups
