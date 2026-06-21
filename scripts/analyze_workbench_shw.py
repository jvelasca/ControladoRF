"""Análisis rápido de un fichero Shure Wireless Workbench (.shw)."""
from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path


def _text(el) -> str:
    return (el.text or "").strip() if el is not None else ""


def analyze(path: Path) -> None:
    tree = ET.parse(path)
    root = tree.getroot()
    print(f"Root: <{root.tag}> {root.attrib}")

    for child in root:
        ver = child.get("version", "")
        print(f"  - {child.tag} (version={ver!r}) direct_children={len(list(child))}")

    sp = root.find("show_properties")
    if sp is not None:
        print("\nShow properties:")
        print(f"  name: {_text(sp.find('.//show_info/name'))}")
        print(f"  customer: {_text(sp.find('.//show_info/customer'))}")
        print(f"  contact: {_text(sp.find('.//point_of_contact_info/name'))}")

    inv = root.find("inventory")
    if inv is None:
        print("No inventory section")
        return

    devices = inv.findall("device")
    print(f"\nInventory: {len(devices)} devices")
    series_c: Counter = Counter()
    model_c: Counter = Counter()
    band_c: Counter = Counter()
    role_c: Counter = Counter()
    channels = []

    for device in devices:
        series_c[_text(device.find("series"))] += 1
        model_c[_text(device.find("model"))] += 1
        band_c[_text(device.find("band"))] += 1
        zone = _text(device.find("zone"))
        if zone:
            role_c[zone] += 1

        dev_id = device.find("id")
        wb_id = dev_id.text if dev_id is not None else ""
        dcid = dev_id.get("dcid", "") if dev_id is not None else ""

        for ch in device.findall("channel"):
            ch_num = ch.get("number", "?")
            freq_el = ch.find("frequency")
            freq = int(freq_el.text) if freq_el is not None and freq_el.text else None
            channels.append({
                "device_id": wb_id,
                "device_dcid": dcid,
                "device_name": _text(device.find("device_name")),
                "series": _text(device.find("series")),
                "model": _text(device.find("model")),
                "band": _text(device.find("band")),
                "zone": zone,
                "channel_number": ch_num,
                "channel_name": _text(ch.find("channel_name")),
                "frequency_khz": freq,
            })

    print("  Series:", dict(series_c))
    print("  Models:", model_c.most_common(10))
    print("  Bands:", dict(band_c))
    print("  Zones:", dict(role_c))
    print(f"  Channels: {len(channels)}")

    freqs = [c["frequency_khz"] for c in channels if c["frequency_khz"]]
    if freqs:
        print(f"  Frequency range (raw units): {min(freqs)} - {max(freqs)}")

    coord = root.find("coordination_info")
    if coord is not None:
        print(f"\ncoordination_info children: {[c.tag for c in coord][:20]}")

    cdr = root.find("coordinated_data_root")
    if cdr is not None:
        print(f"\ncoordinated_data_root id={cdr.get('id')} children={len(list(cdr))}")

    mon = root.find("monitoring_info")
    if mon is not None:
        print(f"\nmonitoring_info children: {[c.tag for c in mon][:15]}")


if __name__ == "__main__":
    p = Path(sys.argv[1] if len(sys.argv) > 1 else "auxiliares/ejempo impor workbench.shw")
    analyze(p)
