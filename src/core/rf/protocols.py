"""Contratos abstractos del motor RF (Protocol)."""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from core.rf.types import (
    AcquisitionPlan,
    ConfigureResult,
    OperatorIntent,
    RfHardwareConfig,
    RfTelemetry,
    SpectrumFrame,
    SweepPlan,
)


@runtime_checkable
class RfDevice(Protocol):
  """Driver de un equipo SDR — sin PyQt, sin política de analizador."""

  @property
  def device_id(self) -> str: ...

  def open(self) -> None: ...

  def close(self) -> None: ...

  @property
  def is_open(self) -> bool: ...

  def configure(self, hardware: RfHardwareConfig, *, window_center_hz: float) -> ConfigureResult: ...

  def capture_sweep(self, plan: SweepPlan) -> SpectrumFrame: ...

  def capture_iq_spectrum(self, plan: AcquisitionPlan) -> SpectrumFrame: ...


@runtime_checkable
class AcquisitionPolicy(Protocol):
  def plan(self, intent: OperatorIntent, *, device_id: str, instant_bw_hz: float) -> AcquisitionPlan: ...


@runtime_checkable
class AnalysisPolicy(Protocol):
  def resolve(self, intent: OperatorIntent, acquisition: AcquisitionPlan) -> OperatorIntent: ...


@runtime_checkable
class ISpectrumView(Protocol):
  """Puerto GUI mínimo — implementado por widgets Monitor."""

  def show_frame(self, frame: SpectrumFrame, *, ref_level_dbm: float, ref_range_db: float) -> None: ...

  def show_telemetry(self, telemetry: RfTelemetry) -> None: ...

  def show_error(self, message: str) -> None: ...
