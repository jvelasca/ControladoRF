"""Estado global de canalización RF (toda la APP)."""
from __future__ import annotations

import json
from dataclasses import dataclass, field


@dataclass
class ChannelizationState:
    input_mode: str = "frequency"  # frequency | channel
    active_region: str = "ES"
    active_standard_ids: list[str] = field(
        default_factory=lambda: [
            "FM_EU_100K",
            "DVB-T_ES",
            "MOBILE_700_ES",
            "MOBILE_800_ES",
        ]
    )
    show_spectrum_allocations: bool = True
    show_restrictions: bool = True

    def to_prefs(self) -> dict[str, str]:
        return {
            "input_mode": self.input_mode,
            "active_region": self.active_region,
            "active_standards_json": json.dumps(self.active_standard_ids, ensure_ascii=False),
            "show_spectrum_allocations": "1" if self.show_spectrum_allocations else "0",
            "show_restrictions": "1" if self.show_restrictions else "0",
        }

    @classmethod
    def from_prefs(cls, prefs: dict[str, str]) -> ChannelizationState:
        raw = prefs.get("active_standards_json") or "[]"
        try:
            ids = json.loads(raw)
            if not isinstance(ids, list):
                ids = []
        except json.JSONDecodeError:
            ids = []
        return cls(
            input_mode=str(prefs.get("input_mode") or "frequency"),
            active_region=str(prefs.get("active_region") or "ES"),
            active_standard_ids=[str(x) for x in ids],
            show_spectrum_allocations=str(prefs.get("show_spectrum_allocations", "1")) != "0",
            show_restrictions=str(prefs.get("show_restrictions", "1")) != "0",
        )
