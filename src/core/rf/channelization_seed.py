"""Datos iniciales y actualización del catálogo mundial de canalizaciones RF."""
from __future__ import annotations

import json
from typing import Any

from db.connection import Database
from utils.logger import get_logger

logger = get_logger(__name__)

# v2: TDT España 21–48 (≤694 MHz) + bandas móviles 700/800/LTE/5G
CATALOG_VERSION = 2
CATALOG_VERSION_KEY = "catalog_version"

# TDT España: RD 391/2019 y RD 250/2025 — 470–694 MHz (canal UHF 21–48)
DVB_T_ES_FIRST = 21
DVB_T_ES_LAST = 48
DVB_T_ES_FREQ_MAX_HZ = 694.0e6

# Banda 700 MHz liberada (694–790 MHz) — LTE B28 / 5G NR n28 (UE 2016/687)
MOBILE_700_FIRST = 49
MOBILE_700_LAST = 60
MOBILE_700_FREQ_MAX_HZ = 790.0e6

STANDARDS: list[dict[str, Any]] = [
    {
        "id": "FM_EU_100K",
        "name": "FM Europa 100 kHz (87.5–108 MHz)",
        "region_code": "EU",
        "service_type": "fm",
        "freq_min_hz": 87.5e6,
        "freq_max_hz": 108.0e6,
        "channel_spacing_hz": 100_000.0,
    },
    {
        "id": "FM_US_200K",
        "name": "FM USA 200 kHz (88.1–107.9 MHz)",
        "region_code": "US",
        "service_type": "fm",
        "freq_min_hz": 88.1e6,
        "freq_max_hz": 107.9e6,
        "channel_spacing_hz": 200_000.0,
    },
    {
        "id": "DVB-T_EU",
        "name": "DVB-T/T2 Europa UHF (canal 21–69)",
        "region_code": "EU",
        "service_type": "dvb-t",
        "freq_min_hz": 474.0e6,
        "freq_max_hz": 862.0e6,
        "channel_spacing_hz": 8_000_000.0,
    },
    {
        "id": "DVB-T_ES",
        "name": "DVB-T/T2 España UHF (canal 21–48, 470–694 MHz)",
        "region_code": "ES",
        "service_type": "dvb-t",
        "freq_min_hz": 474.0e6,
        "freq_max_hz": DVB_T_ES_FREQ_MAX_HZ,
        "channel_spacing_hz": 8_000_000.0,
    },
    {
        "id": "MOBILE_700_ES",
        "name": "Banda 700 MHz España (694–790 MHz) LTE B28 / 5G n28",
        "region_code": "ES",
        "service_type": "5g",
        "freq_min_hz": 694.0e6,
        "freq_max_hz": MOBILE_700_FREQ_MAX_HZ,
        "channel_spacing_hz": 8_000_000.0,
    },
    {
        "id": "MOBILE_800_ES",
        "name": "Banda 800 MHz España (791–862 MHz) LTE B20",
        "region_code": "ES",
        "service_type": "lte",
        "freq_min_hz": 791.0e6,
        "freq_max_hz": 862.0e6,
        "channel_spacing_hz": None,
    },
    {
        "id": "MOBILE_LTE_ES",
        "name": "LTE España (900 / 1800 / 2100 / 2600 MHz)",
        "region_code": "ES",
        "service_type": "lte",
        "freq_min_hz": 925.0e6,
        "freq_max_hz": 2690.0e6,
        "channel_spacing_hz": None,
    },
    {
        "id": "MOBILE_5G_ES",
        "name": "5G NR España (3,4–3,8 GHz banda n78)",
        "region_code": "ES",
        "service_type": "5g",
        "freq_min_hz": 3400.0e6,
        "freq_max_hz": 3800.0e6,
        "channel_spacing_hz": None,
    },
]

REGION_DEFAULTS: list[tuple[str, str, int]] = [
    ("ES", "FM_EU_100K", 0),
    ("ES", "DVB-T_ES", 1),
    ("ES", "MOBILE_700_ES", 2),
    ("ES", "MOBILE_800_ES", 3),
    ("ES", "MOBILE_LTE_ES", 4),
    ("ES", "MOBILE_5G_ES", 5),
    ("EU", "FM_EU_100K", 0),
    ("EU", "DVB-T_EU", 1),
    ("US", "FM_US_200K", 0),
    ("GB", "FM_EU_100K", 0),
    ("GB", "DVB-T_EU", 1),
    ("DE", "FM_EU_100K", 0),
    ("DE", "DVB-T_EU", 1),
    ("JP", "FM_EU_100K", 0),
    ("LATAM", "FM_EU_100K", 0),
    ("GLOBAL", "FM_EU_100K", 0),
    ("GLOBAL", "DVB-T_EU", 1),
    ("GLOBAL", "FM_US_200K", 2),
]

DEFAULT_PREFS = {
    "input_mode": "frequency",
    "active_region": "ES",
    "active_standards_json": '["FM_EU_100K","DVB-T_ES","MOBILE_700_ES","MOBILE_800_ES"]',
    "show_spectrum_allocations": "1",
    "show_restrictions": "1",
}

ES_DEFAULT_STANDARD_IDS = [
    "FM_EU_100K",
    "DVB-T_ES",
    "MOBILE_700_ES",
    "MOBILE_800_ES",
]


def _fm_eu_channels() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    freq = 87.5e6
    n = 1
    while freq <= 108.0e6 + 1.0:
        rows.append(
            {
                "channel_number": n,
                "channel_label": f"FM{n}",
                "center_freq_hz": freq,
                "bandwidth_hz": 100_000.0,
                "sort_order": n,
            }
        )
        freq += 100_000.0
        n += 1
    return rows


def _fm_us_channels() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    freq = 88.1e6
    n = 1
    while freq <= 107.9e6 + 1.0:
        rows.append(
            {
                "channel_number": n,
                "channel_label": f"FM{n}",
                "center_freq_hz": freq,
                "bandwidth_hz": 200_000.0,
                "sort_order": n,
            }
        )
        freq += 200_000.0
        n += 1
    return rows


def _dvb_t_uhf_channels(first: int = 21, last: int = 69) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for n in range(first, last + 1):
        center = 474.0e6 + (n - 21) * 8_000_000.0
        rows.append(
            {
                "channel_number": n,
                "channel_label": f"CH{n}",
                "center_freq_hz": center,
                "bandwidth_hz": 8_000_000.0,
                "sort_order": n,
            }
        )
    return rows


def _mobile_700_es_channels() -> list[dict[str, Any]]:
    """Bloques 8 MHz en rejilla UHF 49–60 (694–790 MHz)."""
    return _dvb_t_uhf_channels(MOBILE_700_FIRST, MOBILE_700_LAST)


def _mobile_800_es_channels() -> list[dict[str, Any]]:
    return [
        {
            "channel_number": 1,
            "channel_label": "B20-DL",
            "center_freq_hz": 806.0e6,
            "bandwidth_hz": 30.0e6,
            "sort_order": 1,
        },
        {
            "channel_number": 2,
            "channel_label": "B20-UL",
            "center_freq_hz": 847.0e6,
            "bandwidth_hz": 30.0e6,
            "sort_order": 2,
        },
    ]


def _mobile_lte_es_channels() -> list[dict[str, Any]]:
    bands = [
        (8, "B8-900", 942.5e6, 35.0e6),
        (3, "B3-1800", 1842.5e6, 75.0e6),
        (1, "B1-2100", 2140.0e6, 60.0e6),
        (7, "B7-2600", 2655.0e6, 70.0e6),
    ]
    rows: list[dict[str, Any]] = []
    for idx, (_num, label, center, bw) in enumerate(bands, start=1):
        rows.append(
            {
                "channel_number": idx,
                "channel_label": label,
                "center_freq_hz": center,
                "bandwidth_hz": bw,
                "sort_order": idx,
            }
        )
    return rows


def _mobile_5g_es_channels() -> list[dict[str, Any]]:
    return [
        {
            "channel_number": 78,
            "channel_label": "n78-3500",
            "center_freq_hz": 3600.0e6,
            "bandwidth_hz": 400.0e6,
            "sort_order": 1,
        },
        {
            "channel_number": 28,
            "channel_label": "n28-700",
            "center_freq_hz": 742.0e6,
            "bandwidth_hz": 45.0e6,
            "sort_order": 2,
        },
    ]


def _channels_for_standard(standard_id: str) -> list[dict[str, Any]]:
    if standard_id == "FM_EU_100K":
        return _fm_eu_channels()
    if standard_id == "FM_US_200K":
        return _fm_us_channels()
    if standard_id == "DVB-T_EU":
        return _dvb_t_uhf_channels()
    if standard_id == "DVB-T_ES":
        return _dvb_t_uhf_channels(DVB_T_ES_FIRST, DVB_T_ES_LAST)
    if standard_id == "MOBILE_700_ES":
        return _mobile_700_es_channels()
    if standard_id == "MOBILE_800_ES":
        return _mobile_800_es_channels()
    if standard_id == "MOBILE_LTE_ES":
        return _mobile_lte_es_channels()
    if standard_id == "MOBILE_5G_ES":
        return _mobile_5g_es_channels()
    return []


def _get_catalog_version(db: Database) -> int:
    row = db.fetchone(
        "SELECT value FROM rf_app_channelization WHERE key = ?",
        (CATALOG_VERSION_KEY,),
    )
    if row is None:
        return 0
    try:
        return int(str(row["value"]))
    except ValueError:
        return 0


def _set_catalog_version(db: Database, version: int) -> None:
    db.execute(
        """
        INSERT OR REPLACE INTO rf_app_channelization (key, value, updated_at)
        VALUES (?, ?, datetime('now'))
        """,
        (CATALOG_VERSION_KEY, str(version)),
    )


def _insert_standard(db: Database, std: dict[str, Any]) -> None:
    db.execute(
        """
        INSERT INTO rf_standards (
            id, name, region_code, service_type,
            freq_min_hz, freq_max_hz, channel_spacing_hz,
            metadata_json, enabled
        ) VALUES (?, ?, ?, ?, ?, ?, ?, '{}', 1)
        """,
        (
            std["id"],
            std["name"],
            std["region_code"],
            std["service_type"],
            std["freq_min_hz"],
            std["freq_max_hz"],
            std["channel_spacing_hz"],
        ),
    )


def _upsert_standard(db: Database, std: dict[str, Any]) -> None:
    db.execute(
        """
        INSERT INTO rf_standards (
            id, name, region_code, service_type,
            freq_min_hz, freq_max_hz, channel_spacing_hz,
            metadata_json, enabled
        ) VALUES (?, ?, ?, ?, ?, ?, ?, '{}', 1)
        ON CONFLICT(id) DO UPDATE SET
            name = excluded.name,
            region_code = excluded.region_code,
            service_type = excluded.service_type,
            freq_min_hz = excluded.freq_min_hz,
            freq_max_hz = excluded.freq_max_hz,
            channel_spacing_hz = excluded.channel_spacing_hz,
            enabled = 1
        """,
        (
            std["id"],
            std["name"],
            std["region_code"],
            std["service_type"],
            std["freq_min_hz"],
            std["freq_max_hz"],
            std["channel_spacing_hz"],
        ),
    )


def _replace_standard_channels(db: Database, standard_id: str) -> None:
    db.execute("DELETE FROM rf_standard_channels WHERE standard_id = ?", (standard_id,))
    for ch in _channels_for_standard(standard_id):
        db.execute(
            """
            INSERT INTO rf_standard_channels (
                standard_id, channel_number, channel_label,
                center_freq_hz, bandwidth_hz, sort_order, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, '{}')
            """,
            (
                standard_id,
                ch["channel_number"],
                ch["channel_label"],
                ch["center_freq_hz"],
                ch["bandwidth_hz"],
                ch["sort_order"],
            ),
        )


def _insert_dvb_t_es_restrictions(db: Database) -> None:
    for n in range(DVB_T_ES_FIRST, DVB_T_ES_LAST + 1):
        f_min = 474.0e6 + (n - 21) * 8_000_000.0 - 4.0e6
        f_max = f_min + 8_000_000.0
        db.execute(
            """
            INSERT INTO rf_channel_restrictions (
                standard_id, label, freq_min_hz, freq_max_hz,
                severity, color_hex, message_key, metadata_json
            ) VALUES (?, ?, ?, ?, 'warning', '#c0404088', ?, '{}')
            """,
            (
                "DVB-T_ES",
                f"TDT CH{n}",
                f_min,
                f_max,
                "channelization_restriction_dvb_t",
            ),
        )


def _insert_mobile_restrictions(db: Database) -> None:
    mobile_defs = (
        ("MOBILE_700_ES", "700 MHz", 694.0e6, MOBILE_700_FREQ_MAX_HZ, "channelization_restriction_mobile_700"),
        ("MOBILE_800_ES", "800 MHz B20", 791.0e6, 862.0e6, "channelization_restriction_lte"),
        ("MOBILE_LTE_ES", "LTE", 925.0e6, 2690.0e6, "channelization_restriction_lte"),
        ("MOBILE_5G_ES", "5G NR", 3400.0e6, 3800.0e6, "channelization_restriction_5g"),
    )
    for standard_id, label, f_min, f_max, message_key in mobile_defs:
        db.execute(
            """
            INSERT INTO rf_channel_restrictions (
                standard_id, label, freq_min_hz, freq_max_hz,
                severity, color_hex, message_key, metadata_json
            ) VALUES (?, ?, ?, ?, 'info', '#4060c088', ?, '{}')
            """,
            (standard_id, label, f_min, f_max, message_key),
        )


def _seed_region_defaults(db: Database) -> None:
    for region, standard_id, priority in REGION_DEFAULTS:
        db.execute(
            """
            INSERT OR IGNORE INTO rf_standard_regions (region_code, standard_id, priority)
            VALUES (?, ?, ?)
            """,
            (region, standard_id, priority),
        )


def _refresh_es_region_defaults(db: Database) -> None:
    db.execute("DELETE FROM rf_standard_regions WHERE region_code = 'ES'")
    for region, standard_id, priority in REGION_DEFAULTS:
        if region != "ES":
            continue
        db.execute(
            """
            INSERT INTO rf_standard_regions (region_code, standard_id, priority)
            VALUES (?, ?, ?)
            """,
            (region, standard_id, priority),
        )


def _maybe_upgrade_es_active_standards(db: Database) -> None:
    row = db.fetchone(
        "SELECT value FROM rf_app_channelization WHERE key = 'active_standards_json'"
    )
    if row is None:
        return
    raw = str(row["value"])
    old_defaults = {
        '["FM_EU_100K","DVB-T_ES"]',
        '["FM_EU_100K", "DVB-T_ES"]',
    }
    if raw.strip() not in old_defaults:
        return
    db.execute(
        """
        UPDATE rf_app_channelization
        SET value = ?, updated_at = datetime('now')
        WHERE key = 'active_standards_json'
        """,
        (json.dumps(ES_DEFAULT_STANDARD_IDS, ensure_ascii=False),),
    )


def _seed_full(db: Database) -> None:
    logger.info("Sembrando catálogo RF global (FM, TDT ES/EU, móvil ES)…")
    with db.transaction():
        for std in STANDARDS:
            _insert_standard(db, std)
            _replace_standard_channels(db, std["id"])

        _seed_region_defaults(db)
        _insert_dvb_t_es_restrictions(db)
        _insert_mobile_restrictions(db)

        for key, value in DEFAULT_PREFS.items():
            db.execute(
                """
                INSERT OR REPLACE INTO rf_app_channelization (key, value, updated_at)
                VALUES (?, ?, datetime('now'))
                """,
                (key, value),
            )
        _set_catalog_version(db, CATALOG_VERSION)
    logger.info("Catálogo RF global sembrado (v%d).", CATALOG_VERSION)


def _upgrade_catalog_v2(db: Database) -> None:
    logger.info("Actualizando catálogo RF a v2 (TDT ES 21–48 + bandas móviles)…")
    mobile_ids = ("MOBILE_700_ES", "MOBILE_800_ES", "MOBILE_LTE_ES", "MOBILE_5G_ES")
    with db.transaction():
        for std in STANDARDS:
            _upsert_standard(db, std)
            _replace_standard_channels(db, std["id"])

        db.execute(
            """
            DELETE FROM rf_standard_channels
            WHERE standard_id = 'DVB-T_ES' AND channel_number > ?
            """,
            (DVB_T_ES_LAST,),
        )
        db.execute("DELETE FROM rf_channel_restrictions WHERE standard_id = 'DVB-T_ES'")
        db.execute(
            "DELETE FROM rf_channel_restrictions WHERE standard_id IN (?, ?, ?, ?)",
            mobile_ids,
        )

        _insert_dvb_t_es_restrictions(db)
        _insert_mobile_restrictions(db)
        _refresh_es_region_defaults(db)
        _maybe_upgrade_es_active_standards(db)
        _set_catalog_version(db, CATALOG_VERSION)
    logger.info("Catálogo RF actualizado a v%d.", CATALOG_VERSION)


def ensure_channelization_seed(db: Database) -> None:
    """Inserta o actualiza el catálogo global de canalizaciones."""
    row = db.fetchone("SELECT COUNT(*) AS n FROM rf_standards")
    if not row or int(row["n"]) == 0:
        _seed_full(db)
        return

    if _get_catalog_version(db) < CATALOG_VERSION:
        _upgrade_catalog_v2(db)
