"""Repositorio del catálogo global de estándares y canales RF."""
from __future__ import annotations

from typing import List, Optional

from ..connection import Database
from ..models.rf_standard import RfChannelRestriction, RfStandard, RfStandardChannel


class RfStandardRepository:
    """Acceso a rf_standards, rf_standard_channels y restricciones."""

    def __init__(self, db: Database) -> None:
        self._db = db

    def count_standards(self) -> int:
        row = self._db.fetchone("SELECT COUNT(*) AS n FROM rf_standards")
        return int(row["n"]) if row else 0

    def list_standards(self, region_code: str | None = None) -> List[RfStandard]:
        if region_code:
            rows = self._db.fetchall(
                """
                SELECT s.*
                FROM rf_standards s
                INNER JOIN rf_standard_regions r ON r.standard_id = s.id
                WHERE r.region_code = ?
                ORDER BY r.priority, s.name
                """,
                (region_code.upper(),),
            )
        else:
            rows = self._db.fetchall("SELECT * FROM rf_standards ORDER BY name")
        return [self._row_to_standard(row) for row in rows]

    def get_standard(self, standard_id: str) -> Optional[RfStandard]:
        row = self._db.fetchone(
            "SELECT * FROM rf_standards WHERE id = ?",
            (standard_id,),
        )
        return self._row_to_standard(row) if row else None

    def list_channels(self, standard_id: str) -> List[RfStandardChannel]:
        rows = self._db.fetchall(
            """
            SELECT * FROM rf_standard_channels
            WHERE standard_id = ?
            ORDER BY sort_order, channel_number, channel_label
            """,
            (standard_id,),
        )
        return [self._row_to_channel(row) for row in rows]

    def list_restrictions(self, standard_id: str | None = None) -> List[RfChannelRestriction]:
        if standard_id:
            rows = self._db.fetchall(
                """
                SELECT * FROM rf_channel_restrictions
                WHERE standard_id = ?
                ORDER BY freq_min_hz
                """,
                (standard_id,),
            )
        else:
            rows = self._db.fetchall(
                "SELECT * FROM rf_channel_restrictions ORDER BY standard_id, freq_min_hz"
            )
        return [self._row_to_restriction(row) for row in rows]

    def region_codes(self) -> List[str]:
        rows = self._db.fetchall(
            "SELECT DISTINCT region_code FROM rf_standard_regions ORDER BY region_code"
        )
        return [str(row["region_code"]) for row in rows]

    def default_standard_ids_for_region(self, region_code: str) -> List[str]:
        rows = self._db.fetchall(
            """
            SELECT standard_id FROM rf_standard_regions
            WHERE region_code = ?
            ORDER BY priority
            """,
            (region_code.upper(),),
        )
        return [str(row["standard_id"]) for row in rows]

    def find_channel_by_label(
        self, standard_id: str, label: str
    ) -> Optional[RfStandardChannel]:
        row = self._db.fetchone(
            """
            SELECT * FROM rf_standard_channels
            WHERE standard_id = ? AND channel_label = ? COLLATE NOCASE
            """,
            (standard_id, label.strip()),
        )
        return self._row_to_channel(row) if row else None

    def find_channel_by_number(
        self, standard_id: str, channel_number: int
    ) -> Optional[RfStandardChannel]:
        row = self._db.fetchone(
            """
            SELECT * FROM rf_standard_channels
            WHERE standard_id = ? AND channel_number = ?
            """,
            (standard_id, channel_number),
        )
        return self._row_to_channel(row) if row else None

    def find_nearest_channel(
        self, standard_id: str, freq_hz: float
    ) -> Optional[RfStandardChannel]:
        row = self._db.fetchone(
            """
            SELECT * FROM rf_standard_channels
            WHERE standard_id = ?
            ORDER BY ABS(center_freq_hz - ?)
            LIMIT 1
            """,
            (standard_id, freq_hz),
        )
        return self._row_to_channel(row) if row else None

    @staticmethod
    def _row_to_standard(row) -> RfStandard:
        return RfStandard(
            id=str(row["id"]),
            name=str(row["name"]),
            region_code=str(row["region_code"]),
            service_type=str(row["service_type"]),
            freq_min_hz=float(row["freq_min_hz"]) if row["freq_min_hz"] is not None else None,
            freq_max_hz=float(row["freq_max_hz"]) if row["freq_max_hz"] is not None else None,
            channel_spacing_hz=float(row["channel_spacing_hz"])
            if row["channel_spacing_hz"] is not None
            else None,
            metadata_json=str(row["metadata_json"] or "{}"),
            enabled=bool(row["enabled"]),
        )

    @staticmethod
    def _row_to_channel(row) -> RfStandardChannel:
        return RfStandardChannel(
            id=int(row["id"]),
            standard_id=str(row["standard_id"]),
            channel_number=int(row["channel_number"])
            if row["channel_number"] is not None
            else None,
            channel_label=str(row["channel_label"]),
            center_freq_hz=float(row["center_freq_hz"]),
            bandwidth_hz=float(row["bandwidth_hz"]),
            sort_order=int(row["sort_order"]),
            metadata_json=str(row["metadata_json"] or "{}"),
        )

    @staticmethod
    def _row_to_restriction(row) -> RfChannelRestriction:
        return RfChannelRestriction(
            id=int(row["id"]),
            standard_id=str(row["standard_id"]),
            label=str(row["label"]),
            freq_min_hz=float(row["freq_min_hz"]),
            freq_max_hz=float(row["freq_max_hz"]),
            severity=str(row["severity"]),
            color_hex=str(row["color_hex"]),
            message_key=str(row["message_key"]),
            metadata_json=str(row["metadata_json"] or "{}"),
        )
