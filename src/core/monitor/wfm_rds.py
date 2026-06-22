"""Decodificador RDS (57 kHz) — PI, PS, PTY y metadatos de emisora."""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

RDS_BIT_RATE = 1187.5
RDS_SUBCARRIER_HZ = 57_000.0
_RDS_CRC_POLY = 0x5D9
_RDS_BLOCK_OFFSET = (0x0FC, 0x198, 0x168, 0x1B8)

_PTY_NAMES = (
    "None",
    "News",
    "Current Affairs",
    "Information",
    "Sport",
    "Education",
    "Drama",
    "Culture",
    "Science",
    "Varied",
    "Pop Music",
    "Rock Music",
    "Easy Listening",
    "Light Classical",
    "Serious Classical",
    "Other Music",
    "Weather",
    "Finance",
    "Children's",
    "Social Affairs",
    "Religion",
    "Phone-In",
    "Travel",
    "Leisure",
    "Jazz Music",
    "Country Music",
    "National Music",
    "Oldies Music",
    "Folk Music",
    "Documentary",
    "Alarm Test",
    "Alarm",
)

_PI_REGION = {
    0x1: "Europe",
    0x2: "Europe",
    0x3: "Europe",
    0xA: "Spain",
    0xB: "Spain",
    0xC: "Spain",
    0xD: "Spain",
    0xE: "Spain",
    0xF: "Spain",
}


@dataclass
class RdsDecoderState:
    """Estado del decodificador RDS entre bloques MPX."""

    mix_phase: float = 0.0
    bit_phase: float = 0.0
    lpf_i: float = 0.0
    lpf_q: float = 0.0
    last_symbol: int = 0
    raw_bits: list[int] = field(default_factory=list)
    pi_code: int | None = None
    ps_name: str = ""
    ps_buffer: list[str] = field(default_factory=lambda: [" "] * 8)
    pty_code: int | None = None
    tp: bool = False
    ms_music: bool | None = None
    ecc: int | None = None
    reference_number: int | None = None
    status: str = ""
    synced: bool = False

    def reset(self) -> None:
        self.mix_phase = 0.0
        self.bit_phase = 0.0
        self.lpf_i = 0.0
        self.lpf_q = 0.0
        self.last_symbol = 0
        self.raw_bits.clear()
        self.pi_code = None
        self.ps_name = ""
        self.ps_buffer = [" "] * 8
        self.pty_code = None
        self.tp = False
        self.ms_music = None
        self.ecc = None
        self.reference_number = None
        self.status = ""
        self.synced = False

    @property
    def pi_hex(self) -> str:
        if self.pi_code is None:
            return ""
        return f"{int(self.pi_code):04X}"

    @property
    def country_code(self) -> str:
        if self.ecc is not None:
            return f"{int(self.ecc):02X}"
        if self.pi_code is None:
            return ""
        region = _PI_REGION.get((int(self.pi_code) >> 12) & 0xF, "")
        if region:
            return region
        return f"{(int(self.pi_code) >> 12) & 0xF:X}"

    @property
    def program_coverage(self) -> str:
        if not self.synced:
            return ""
        if self.tp:
            return "TP"
        return "Local"

    @property
    def program_type(self) -> str:
        if self.pty_code is None:
            return ""
        idx = int(self.pty_code) & 0x1F
        if 0 <= idx < len(_PTY_NAMES):
            return _PTY_NAMES[idx]
        return f"PTY {idx}"

    @property
    def music_label(self) -> str:
        if self.ms_music is None:
            if self.pty_code is not None and int(self.pty_code) >= 16:
                return "Music"
            if self.pty_code is not None:
                return "Speech"
            return ""
        return "Music" if self.ms_music else "Speech"

    @property
    def reference_display(self) -> str:
        if self.reference_number is not None:
            return str(int(self.reference_number))
        if self.pi_code is not None:
            return self.pi_hex
        return ""


def _rds_crc(block26: int) -> int:
    reg = 0
    for bit in range(25, -1, -1):
        reg ^= ((block26 >> bit) & 1) << 10
        if reg & 0x400:
            reg = ((reg << 1) ^ _RDS_CRC_POLY) & 0x7FF
        else:
            reg = (reg << 1) & 0x7FF
    return reg


def _block_valid(block26: int, offset: int) -> bool:
    return _rds_crc(block26 ^ (offset << 16)) == 0


def _bits_to_int(bits: list[int], start: int, length: int) -> int:
    value = 0
    for i in range(length):
        value = (value << 1) | (bits[start + i] & 1)
    return value


def _decode_group_payload(blocks: list[int], state: RdsDecoderState) -> None:
    group_b = blocks[1]
    group_type = (group_b >> 12) & 0x0F
    group_ver = (group_b >> 11) & 1
    state.tp = bool((group_b >> 10) & 1)
    state.pty_code = (group_b >> 5) & 0x1F
    state.ms_music = bool((group_b >> 3) & 1)

    if group_type == 0 and group_ver == 0:
        ps_index = group_b & 0x03
        char_a = (blocks[2] >> 8) & 0xFF
        char_b = blocks[2] & 0xFF
        if 32 <= char_a <= 126:
            state.ps_buffer[ps_index * 2] = chr(char_a)
        if 32 <= char_b <= 126:
            state.ps_buffer[ps_index * 2 + 1] = chr(char_b)
        state.ps_name = "".join(state.ps_buffer).strip()
        pin = ((blocks[2] & 0x0F) << 12) | (blocks[3] & 0x0FFF)
        if pin > 0:
            state.reference_number = pin

    if group_type == 1 and group_ver == 0:
        state.ecc = (blocks[2] >> 8) & 0xFF
        lic = blocks[2] & 0x0F
        if lic:
            state.reference_number = lic


def _one_pole_lpf(x: np.ndarray, alpha: float, y0: float) -> tuple[np.ndarray, float]:
    """Filtro IIR paso bajo vectorizado (estado y0 entre bloques)."""
    x = np.asarray(x, dtype=np.float64).reshape(-1)
    n = x.size
    if n == 0:
        return x, y0
    one_m = 1.0 - alpha
    i = np.arange(n, dtype=np.float64)
    pow_alpha = np.power(alpha, i)
    w = x / np.maximum(pow_alpha, 1e-300)
    cs = np.cumsum(one_m * w)
    y = pow_alpha * (alpha * float(y0) + cs)
    return y, float(y[-1])


_RDS_MAX_BITS_PER_CHUNK = 64
_RDS_DECODE_SCAN_MAX = 96


def _decode_rds_groups(bits: list[int], state: RdsDecoderState) -> None:
    if len(bits) < 104:
        return
    scan_span = 32 if state.synced else _RDS_DECODE_SCAN_MAX
    scan_start = max(0, len(bits) - scan_span - 103)
    for offset in range(scan_start, len(bits) - 103):
        chunk = bits[offset : offset + 104]
        blocks: list[int] = []
        ok = True
        for index in range(4):
            block26 = _bits_to_int(chunk, index * 26, 26)
            if not _block_valid(block26, _RDS_BLOCK_OFFSET[index]):
                ok = False
                break
            blocks.append(block26 >> 10)
        if not ok or len(blocks) != 4:
            continue
        state.synced = True
        pi = blocks[0] & 0xFFFF
        if pi != 0:
            state.pi_code = pi
        _decode_group_payload(blocks, state)
        if state.pi_code is not None:
            state.status = f"PI {state.pi_code:04X}"
            if state.ps_name:
                state.status += f" · {state.ps_name}"
            if state.synced:
                return


def _extract_manchester_bits(
    filtered: np.ndarray,
    *,
    sample_rate_hz: float,
    state: RdsDecoderState,
) -> list[int]:
    """Decodifica bi-fase-L RDS (transición al inicio = 1, al medio = 0)."""
    x = np.asarray(filtered, dtype=np.float64).reshape(-1)
    n = x.size
    if n < 16:
        return []
    bit_samples = float(sample_rate_hz) / RDS_BIT_RATE
    half_bit = bit_samples * 0.5
    threshold = max(float(np.std(x)) * 0.12, 1e-6)
    bits: list[int] = []
    pos = float(state.bit_phase)
    prev_enc = int(state.last_symbol) & 1
    bits_budget = _RDS_MAX_BITS_PER_CHUNK

    while pos + bit_samples < n and bits_budget > 0:
        start = int(pos)
        end = min(n, int(pos + bit_samples))
        mid = int(pos + half_bit)
        if end - start < 4:
            break
        seg = x[start:end]
        if seg.size < 5:
            pos += bit_samples * 0.15
            bits_budget -= 1
            continue
        dif = np.diff(seg)
        quarter = max(1, len(dif) // 4)
        head = dif[:quarter]
        start_edge = float(np.max(np.abs(head))) > threshold if head.size else False
        mid_lo = max(0, len(dif) // 2 - 1)
        mid_hi = min(len(dif), mid_lo + 3)
        mid_edge = float(np.max(np.abs(dif[mid_lo:mid_hi]))) > threshold

        if start_edge:
            enc = 1
        elif mid_edge:
            enc = 0
        else:
            pos += bit_samples * 0.15
            continue

        bits.append(enc ^ prev_enc)
        prev_enc = enc
        pos += bit_samples
        bits_budget -= 1

    state.bit_phase = pos - n
    state.last_symbol = prev_enc
    return bits


def feed_rds_mpx(
    mpx: np.ndarray,
    *,
    sample_rate_hz: float,
    state: RdsDecoderState,
) -> str:
    """Demodula BPSK en 57 kHz y actualiza metadatos RDS."""
    x = np.asarray(mpx, dtype=np.float64).reshape(-1)
    if x.size == 0:
        return state.status
    n = x.size
    idx = np.arange(n, dtype=np.float64)
    phase_inc = 2.0 * math.pi * RDS_SUBCARRIER_HZ / float(sample_rate_hz)
    phase = state.mix_phase + idx * phase_inc
    carrier_i = np.cos(phase)
    carrier_q = np.sin(phase)
    mixed_i = x * carrier_i
    mixed_q = x * carrier_q
    alpha = math.exp(-2.0 * math.pi * 2_400.0 / float(sample_rate_hz))
    bb_i, state.lpf_i = _one_pole_lpf(mixed_i, alpha, state.lpf_i)
    bb_q, state.lpf_q = _one_pole_lpf(mixed_q, alpha, state.lpf_q)
    state.mix_phase = (state.mix_phase + n * phase_inc) % (2.0 * math.pi)

    filtered = bb_i
    bits = _extract_manchester_bits(filtered, sample_rate_hz=sample_rate_hz, state=state)

    if bits:
        state.raw_bits.extend(bits)
        if len(state.raw_bits) > 4096:
            state.raw_bits = state.raw_bits[-2048:]
        _decode_rds_groups(state.raw_bits, state)
    if state.synced and state.pi_code is not None and not state.status:
        state.status = f"PI {state.pi_code:04X}"
    return state.status
