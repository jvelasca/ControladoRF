"""Etiquetas traducidas para exportación de inventario."""

from __future__ import annotations



from dataclasses import dataclass

from typing import Any, Dict



from core.inventory_catalog import DEVICE_TYPE_ORDER, _TYPE_I18N

from core.inventory_export import CHANNEL_EXPORT_FIELDS, LIST_METADATA_FIELDS

from i18n.json_translation import tr



PDF_DETAIL_SECTIONS: tuple[tuple[str, tuple[str, ...]], ...] = (

    (

        "rf",

        (

            "channel_number",

            "channel_name",

            "frequency_mhz",

            "band",

            "zone",

            "network",

        ),

    ),

    (

        "device",

        (

            "device_type",

            "model",

            "series",

            "manufacturer",

            "device_name",

        ),

    ),

    (

        "coord",

        (

            "coordination_include",

            "coordination_active",

        ),

    ),

    (

        "meta",

        (

            "notes",

            "color",

            "locked",

        ),

    ),

    (

        "ids",

        (

            "channel_key",

            "source",

            "workbench_channel_id",

            "workbench_device_id",

            "db_id",

        ),

    ),

)



_SECTION_I18N = {

    "rf": "inventory_prop_section_rf",

    "device": "inventory_prop_section_device",

    "coord": "inventory_prop_section_coord",

    "meta": "inventory_prop_section_meta",

    "ids": "inventory_prop_section_ids",

}





@dataclass(frozen=True)

class InventoryExportLabels:

    title: str

    project_label: str

    exported_at_label: str

    channel_count_label: str

    list_metadata_title: str

    channels_title: str

    channel_details_title: str

    page_label: str

    field_labels: Dict[str, str]

    section_titles: Dict[str, str]

    bool_true: str

    bool_false: str





def build_inventory_export_labels() -> InventoryExportLabels:

    field_labels = _field_labels()

    section_titles = {key: tr(i18n_key) for key, i18n_key in _SECTION_I18N.items()}

    return InventoryExportLabels(

        title=tr("inventory_export_pdf_title"),

        project_label=tr("inventory_export_pdf_project"),

        exported_at_label=tr("inventory_export_pdf_date"),

        channel_count_label=tr("inventory_export_pdf_channels"),

        list_metadata_title=tr("inventory_export_pdf_list_meta"),

        channels_title=tr("inventory_export_pdf_table_title"),

        channel_details_title=tr("inventory_export_pdf_details_title"),

        page_label=tr("inventory_export_pdf_page"),

        field_labels=field_labels,

        section_titles=section_titles,

        bool_true=tr("inventory_export_bool_yes"),

        bool_false=tr("inventory_export_bool_no"),

    )





def _field_labels() -> Dict[str, str]:

    mapping = {

        "channel_number": "inventory_col_channel",

        "channel_name": "inventory_col_name",

        "frequency_mhz": "inventory_col_frequency",

        "band": "inventory_col_band",

        "zone": "inventory_col_zone",

        "network": "inventory_prop_network",

        "model": "inventory_col_model",

        "series": "inventory_prop_series",

        "manufacturer": "inventory_prop_manufacturer",

        "device_name": "inventory_col_device",

        "device_type": "inventory_prop_type",

        "coordination_include": "inventory_prop_coord_include",

        "coordination_active": "inventory_prop_coord_active",

        "notes": "inventory_col_notes",

        "color": "inventory_col_color",

        "locked": "inventory_col_locked",

        "channel_key": "inventory_prop_channel_key",

        "source": "inventory_prop_source",

        "workbench_channel_id": "inventory_prop_workbench_channel",

        "workbench_device_id": "inventory_prop_workbench_device",

        "db_id": "inventory_prop_db_id",

    }

    labels: Dict[str, str] = {}

    for field in CHANNEL_EXPORT_FIELDS:

        key = mapping.get(field, field)

        labels[field] = tr(key)

    for field in LIST_METADATA_FIELDS:

        if field == "notes":

            labels[field] = tr("inventory_prop_notes")

        elif field == "color":

            labels[field] = tr("inventory_prop_color")

        elif field == "locked":

            labels[field] = tr("inventory_prop_locked")

    for device_type in DEVICE_TYPE_ORDER:

        labels[f"device_type:{device_type}"] = tr(_TYPE_I18N.get(device_type, "inventory_type_other"))

    return labels





def format_device_type(value: str, labels: InventoryExportLabels) -> str:

    key = f"device_type:{value}"

    return labels.field_labels.get(key, value or "")





def format_bool(value: Any, labels: InventoryExportLabels) -> str:

    return labels.bool_true if bool(value) else labels.bool_false





def format_export_field(field: str, value: Any, labels: InventoryExportLabels) -> str:

    if field in ("coordination_include", "coordination_active", "locked"):

        return format_bool(value, labels)

    if field == "device_type":

        return format_device_type(str(value or ""), labels)

    if field == "frequency_mhz" and isinstance(value, (int, float)):

        return f"{value:.3f}"

    if value in (None, ""):

        return "—"

    return str(value)


