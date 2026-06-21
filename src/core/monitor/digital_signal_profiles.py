"""Perfiles de señal digital — DAB, Shure y personalizado."""
from __future__ import annotations

from dataclasses import dataclass

from core.monitor.spectrum_params import SpectrumParams


@dataclass(frozen=True)
class DigitalSignalProfile:
    profile_id: str
    label_key: str
    channel_bw_hz: float
    recommended_sample_rate_hz: float
    modulation: str  # qpsk | qam16 | qam64 | ofdm
    symbol_rate_hz: float
    mod_order: int
    use_eye_center: bool = False


DIGITAL_PROFILES: dict[str, DigitalSignalProfile] = {
    "custom": DigitalSignalProfile(
        profile_id="custom",
        label_key="monitor_digital_profile_custom",
        channel_bw_hz=600_000.0,
        recommended_sample_rate_hz=2_000_000.0,
        modulation="qpsk",
        symbol_rate_hz=500_000.0,
        mod_order=4,
        use_eye_center=False,
    ),
    "shure_digital": DigitalSignalProfile(
        profile_id="shure_digital",
        label_key="monitor_digital_profile_shure",
        channel_bw_hz=600_000.0,
        recommended_sample_rate_hz=2_000_000.0,
        modulation="qpsk",
        symbol_rate_hz=500_000.0,
        mod_order=4,
        use_eye_center=True,
    ),
    "digital_profile": DigitalSignalProfile(
        profile_id="iem_qam16",
        label_key="monitor_digital_profile_iem_qam16",
        channel_bw_hz=600_000.0,
        recommended_sample_rate_hz=2_000_000.0,
        modulation="qam16",
        symbol_rate_hz=500_000.0,
        mod_order=16,
        use_eye_center=True,
    ),
    "dab_iii": DigitalSignalProfile(
        profile_id="dab_iii",
        label_key="monitor_digital_profile_dab",
        channel_bw_hz=1_536_000.0,
        recommended_sample_rate_hz=2_048_000.0,
        modulation="ofdm",
        symbol_rate_hz=1_000.0,
        mod_order=4,
        use_eye_center=False,
    ),
}

PROFILE_CHOICES: tuple[str, ...] = tuple(DIGITAL_PROFILES.keys())

MOD_ORDER_CHOICES: tuple[tuple[int, str], ...] = (
    (4, "monitor_digital_mod_qpsk"),
    (16, "monitor_digital_mod_qam16"),
    (64, "monitor_digital_mod_qam64"),
)


def get_digital_profile(profile_id: str) -> DigitalSignalProfile:
    return DIGITAL_PROFILES.get(profile_id, DIGITAL_PROFILES["custom"])


def resolve_mod_order(profile: DigitalSignalProfile, params: SpectrumParams) -> int:
    if profile.modulation == "ofdm":
        return 4
    order = int(params.digital_mod_order or profile.mod_order or 4)
    if order in (4, 16, 64):
        return order
    return profile.mod_order or 4


def apply_digital_profile_defaults(params: SpectrumParams, profile_id: str) -> SpectrumParams:
    """Aplica symbol rate, mod order y sample rate recomendado del perfil."""
    prof = get_digital_profile(profile_id)
    updated = params.copy()
    updated.digital_profile = prof.profile_id
    updated.digital_symbol_rate_hz = prof.symbol_rate_hz
    if prof.mod_order > 0:
        updated.digital_mod_order = prof.mod_order
    if updated.capture_mode == "iq" and prof.recommended_sample_rate_hz > 0:
        rate = float(prof.recommended_sample_rate_hz)
        if prof.modulation == "ofdm" or updated.sample_rate_hz < rate * 0.9:
            updated.span_mode = "manual"
            updated.span_hz = rate
            updated.manual_span_hz = rate
            updated.sample_rate_hz = rate
            updated.apply_span_as_sample_rate()
    return updated
