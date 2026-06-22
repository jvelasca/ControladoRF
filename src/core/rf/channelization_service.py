"""Servicio de canalización RF global (catálogo + preferencias de la APP)."""
from __future__ import annotations

from typing import List, Optional

from core.rf.channelization_allocations import AllocationSegment, collect_allocation_segments
from core.rf.channelization_state import ChannelizationState
from db.models.rf_standard import RfStandard, RfStandardChannel
from db.repositories.rf_channelization_prefs_repository import RfChannelizationPrefsRepository
from db.repositories.rf_standard_repository import RfStandardRepository


class ChannelizationService:
    """Resuelve canales ↔ frecuencias y persiste el modo canal global."""

    def __init__(
        self,
        standards: RfStandardRepository,
        prefs: RfChannelizationPrefsRepository,
    ) -> None:
        self._standards = standards
        self._prefs = prefs

    def get_state(self) -> ChannelizationState:
        return ChannelizationState.from_prefs(self._prefs.get_all())

    def save_state(self, state: ChannelizationState) -> None:
        self._prefs.set_many(state.to_prefs())

    def list_region_codes(self) -> List[str]:
        codes = self._standards.region_codes()
        return codes or ["ES", "EU", "US", "GLOBAL"]

    def list_standards(self, region_code: str | None = None) -> List[RfStandard]:
        return self._standards.list_standards(region_code)

    def get_standard(self, standard_id: str) -> Optional[RfStandard]:
        return self._standards.get_standard(standard_id)

    def list_channels(self, standard_id: str) -> List[RfStandardChannel]:
        return self._standards.list_channels(standard_id)

    def active_standards(self) -> List[RfStandard]:
        state = self.get_state()
        result: List[RfStandard] = []
        for std_id in state.active_standard_ids:
            std = self._standards.get_standard(std_id)
            if std is not None and std.enabled:
                result.append(std)
        return result

    def default_standards_for_region(self, region_code: str) -> List[str]:
        return self._standards.default_standard_ids_for_region(region_code)

    def resolve_channel(
        self,
        standard_id: str,
        *,
        label: str | None = None,
        channel_number: int | None = None,
    ) -> Optional[RfStandardChannel]:
        if label:
            return self._standards.find_channel_by_label(standard_id, label)
        if channel_number is not None:
            return self._standards.find_channel_by_number(standard_id, channel_number)
        return None

    def resolve_frequency_hz(
        self,
        standard_id: str,
        *,
        label: str | None = None,
        channel_number: int | None = None,
    ) -> Optional[float]:
        ch = self.resolve_channel(
            standard_id, label=label, channel_number=channel_number
        )
        return ch.center_freq_hz if ch else None

    def spectrum_allocation_segments(
        self, start_hz: float, stop_hz: float
    ) -> List[AllocationSegment]:
        return collect_allocation_segments(self, start_hz, stop_hz)

    def list_user_exclusions(self) -> List["SpectrumUserExclusion"]:
        from core.rf.spectrum_user_exclusions import PREFS_KEY, parse_exclusions_json

        return parse_exclusions_json(self._prefs.get(PREFS_KEY, "[]"))

    def upsert_user_exclusion(self, item: "SpectrumUserExclusion") -> None:
        from core.rf.spectrum_user_exclusions import PREFS_KEY, exclusions_to_json

        items = [ex for ex in self.list_user_exclusions() if ex.id != item.id]
        items.append(item)
        self._prefs.set(PREFS_KEY, exclusions_to_json(items))

    def remove_user_exclusion(self, exclusion_id: str) -> None:
        from core.rf.spectrum_user_exclusions import PREFS_KEY, exclusions_to_json

        items = [ex for ex in self.list_user_exclusions() if ex.id != exclusion_id]
        self._prefs.set(PREFS_KEY, exclusions_to_json(items))

    def clear_user_exclusions(self) -> None:
        from core.rf.spectrum_user_exclusions import PREFS_KEY, exclusions_to_json

        self._prefs.set(PREFS_KEY, exclusions_to_json([]))

    def find_user_exclusion(self, exclusion_id: str):
        for item in self.list_user_exclusions():
            if item.id == exclusion_id:
                return item
        return None

    def list_restrictions(self, standard_id: str):
        return self._standards.list_restrictions(standard_id)

    def find_nearest_channel(
        self, standard_id: str, freq_hz: float
    ) -> Optional[RfStandardChannel]:
        return self._standards.find_nearest_channel(standard_id, freq_hz)
