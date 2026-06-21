"""Antena / bias-tee / RF amp."""
from __future__ import annotations

from core.rf.types import BlockState, RfFrontendConfig


def apply_frontend_config(config: RfFrontendConfig) -> tuple[RfFrontendConfig, BlockState]:
    applied = RfFrontendConfig(
        rf_amp_enable=bool(config.rf_amp_enable),
        bias_tee_enable=bool(config.bias_tee_enable),
    )
    state = BlockState(
        requested=f"amp={config.rf_amp_enable},bias={config.bias_tee_enable}",
        applied=f"amp={applied.rf_amp_enable},bias={applied.bias_tee_enable}",
        valid=True,
    )
    return applied, state
