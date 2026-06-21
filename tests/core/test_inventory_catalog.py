"""Tests de catálogo y agrupación del inventario RF."""
from core.inventory_catalog import (
    DEVICE_TYPE_IEM,
    DEVICE_TYPE_MICROPHONE,
    GROUP_DEVICE_TYPE,
    GROUP_NONE,
    build_inventory_groups,
    device_type_from_workbench_types,
    enrich_equipo_metadata,
    filter_equipos,
    infer_device_type,
)


def test_infer_device_type_ulxd_is_microphone():
    assert infer_device_type(model="ULXD4", series="ULX-D") == DEVICE_TYPE_MICROPHONE


def test_infer_device_type_psm_is_iem():
    assert infer_device_type(model="P10T", series="PSM1000") == DEVICE_TYPE_IEM


def test_infer_device_type_sr2050_is_iem():
    assert infer_device_type(model="SR 2050", series="SR 2050") == DEVICE_TYPE_IEM


def test_infer_device_type_em3732_is_microphone():
    assert infer_device_type(model="EM 3732-II", series="EM 3732-II") == DEVICE_TYPE_MICROPHONE


def test_enrich_equipo_metadata_adds_device_type_and_defaults():
    item = enrich_equipo_metadata({"model": "ULXD1", "series": "ULX-D"})
    assert item["device_type"] == DEVICE_TYPE_MICROPHONE
    assert item["network"] == "Default"
    assert item["zone"] == "Default"


def test_filter_equipos_matches_channel_name():
    equipos = [
        {"channel_name": "Vocal 1", "model": "ULXD1"},
        {"channel_name": "IEM A", "model": "P10T"},
    ]
    result = filter_equipos(equipos, "vocal")
    assert len(result) == 1
    assert result[0]["channel_name"] == "Vocal 1"


def test_build_inventory_groups_by_type():
    equipos = [
        enrich_equipo_metadata({"model": "ULXD1", "series": "ULX-D", "channel_name": "M1"}),
        enrich_equipo_metadata({"model": "P10T", "series": "PSM1000", "channel_name": "I1"}),
    ]

    def _tr(key, **kwargs):
        return kwargs.get("label", key)

    groups = build_inventory_groups(equipos, group_mode=GROUP_DEVICE_TYPE, tr=_tr)
    assert len(groups) == 2
    assert sum(len(items) for _, _, items in groups) == 2


def test_build_inventory_groups_none_is_single_section():
    equipos = [{"model": "ULXD1", "channel_name": "M1"}]

    def _tr(key, **kwargs):
        return key

    groups = build_inventory_groups(equipos, group_mode=GROUP_NONE, tr=_tr)
    assert len(groups) == 1
    assert len(groups[0][2]) == 1


def test_device_type_from_workbench_types_iem():
    assert device_type_from_workbench_types(
        ["Transmitter", "In Ear Monitor", "Rack"]
    ) == DEVICE_TYPE_IEM


def test_device_type_from_workbench_types_microphone():
    assert device_type_from_workbench_types(
        ["Microphone", "Receiver", "Rack"]
    ) == DEVICE_TYPE_MICROPHONE
