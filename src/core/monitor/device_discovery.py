"""Descubrimiento de dispositivos SDR sin bloquear la GUI."""
from __future__ import annotations

import json
import re
import subprocess
import sys
from dataclasses import dataclass
from typing import List, Optional

from core.monitor.sdr_catalog import SdrDeviceSpec, get_default_device_id, get_device_spec, hardware_device_specs
from core.monitor.sdr_setup import DeviceSetupReport, build_device_setup_report, map_source_id_to_device_id
from utils.subprocess_platform import run_hidden


@dataclass(frozen=True)
class UsbDeviceInfo:
    friendly_name: str
    status: str
    instance_id: str
    serial: str = ""
    device_family: str = ""

    @property
    def is_ok(self) -> bool:
        return self.status.upper() == "OK"


@dataclass(frozen=True)
class SourceDescriptor:
    source_id: str
    display_name: str
    available: bool
    detail: str
    device_family: str = "mock"
    usb_device: Optional[UsbDeviceInfo] = None
    backend_ready: bool = False
    setup_report: Optional[DeviceSetupReport] = None
    is_default: bool = False


def _serial_from_instance_id(instance_id: str) -> str:
    if not instance_id:
        return ""
    parts = instance_id.split("\\")
    if len(parts) >= 3:
        return parts[-1]
    return instance_id


def _matches_spec_text(text: str, spec: SdrDeviceSpec) -> bool:
    lowered = text.lower()
    for pattern in spec.usb_text_patterns:
        if re.search(pattern, lowered, re.IGNORECASE):
            return True
    for pattern in spec.usb_name_patterns:
        if pattern.lower() in lowered:
            return True
    return False


def enumerate_usb_for_spec(spec: SdrDeviceSpec, *, timeout_sec: float = 4.0) -> List[UsbDeviceInfo]:
    if sys.platform == "win32":
        return _enumerate_spec_windows(spec, timeout_sec=timeout_sec)
    return _enumerate_spec_generic(spec, timeout_sec=timeout_sec)


def _enumerate_spec_windows(spec: SdrDeviceSpec, *, timeout_sec: float) -> List[UsbDeviceInfo]:
    patterns = "|".join(re.escape(p) for p in spec.usb_name_patterns)
    if not patterns:
        patterns = spec.display_name
    script = (
        f"Get-PnpDevice -PresentOnly | Where-Object {{ $_.FriendlyName -match '{patterns}' }} | "
        "Select-Object FriendlyName, Status, InstanceId | ConvertTo-Json -Compress"
    )
    try:
        proc = run_hidden(
            ["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", script],
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            check=False,
        )
    except (subprocess.TimeoutExpired, OSError):
        return []
    raw = (proc.stdout or "").strip()
    if not raw:
        return []
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return []
    rows = payload if isinstance(payload, list) else [payload]
    devices: List[UsbDeviceInfo] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        name = str(row.get("FriendlyName") or spec.display_name)
        status = str(row.get("Status") or "Unknown")
        instance_id = str(row.get("InstanceId") or "")
        devices.append(
            UsbDeviceInfo(
                friendly_name=name,
                status=status,
                instance_id=instance_id,
                serial=_serial_from_instance_id(instance_id),
                device_family=spec.device_id,
            )
        )
    return devices


def _enumerate_spec_generic(spec: SdrDeviceSpec, *, timeout_sec: float) -> List[UsbDeviceInfo]:
    if sys.platform == "darwin":
        cmd = ["system_profiler", "SPUSBDataType"]
    elif sys.platform.startswith("linux"):
        cmd = ["lsusb"]
    else:
        return []
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_sec, check=False)
    except (subprocess.TimeoutExpired, OSError):
        return []
    text = proc.stdout or ""
    if not _matches_spec_text(text, spec):
        return []
    serial = ""
    for line in text.splitlines():
        if _matches_spec_text(line, spec):
            serial = line.strip()[:120]
            break
    return [
        UsbDeviceInfo(
            friendly_name=spec.display_name,
            status="OK",
            instance_id=serial or "usb",
            serial=serial,
            device_family=spec.device_id,
        )
    ]


def enumerate_hackrf_usb(*, timeout_sec: float = 4.0) -> List[UsbDeviceInfo]:
    spec = get_device_spec("hackrf")
    if not spec:
        return []
    return enumerate_usb_for_spec(spec, timeout_sec=timeout_sec)


def probe_hackrf_backend(*, timeout_sec: float = 3.0) -> tuple[bool, str]:
    from core.monitor.sdr_setup import probe_python_hackrf

    result = probe_python_hackrf(timeout_sec=timeout_sec)
    return result.ok, result.detail or result.summary


def _descriptor_from_spec(
    spec: SdrDeviceSpec,
    usb_devices: List[UsbDeviceInfo],
    *,
    probe_backend: bool,
) -> List[SourceDescriptor]:
    labels = [f"{d.friendly_name} · USB {d.status}" + (f" · S/N {d.serial}" if d.serial else "") for d in usb_devices]
    report = build_device_setup_report(spec, usb_devices=labels, probe_python=probe_backend)
    items: List[SourceDescriptor] = []

    if usb_devices:
        for index, dev in enumerate(usb_devices):
            serial_short = dev.serial[-8:] if len(dev.serial) > 8 else dev.serial
            suffix = f" · {serial_short}" if serial_short else ""
            source_id = spec.device_id if index == 0 else f"{spec.device_id}_{index}"
            detail = labels[index]
            if probe_backend:
                detail += f" · Backend: {report.python_backend.summary}"
            items.append(
                SourceDescriptor(
                    source_id=source_id,
                    display_name=f"{dev.friendly_name}{suffix}",
                    available=dev.is_ok,
                    detail=detail,
                    device_family=spec.device_id,
                    usb_device=dev,
                    backend_ready=report.python_backend.ok or report.cli.ok or report.native_lib.ok,
                    setup_report=report,
                    is_default=spec.is_default,
                )
            )
    else:
        detail = "No detectado por USB"
        if probe_backend:
            detail += f" · {report.cli.summary} · {report.native_lib.summary}"
        items.append(
            SourceDescriptor(
                source_id=spec.device_id,
                display_name=spec.display_name,
                available=False,
                detail=detail,
                device_family=spec.device_id,
                backend_ready=False,
                setup_report=report,
                is_default=spec.is_default,
            )
        )
    return items


def detect_sources(*, probe_backend: bool = False) -> List[SourceDescriptor]:
    results: List[SourceDescriptor] = [
        SourceDescriptor(
            source_id="mock",
            display_name="Simulación",
            available=True,
            detail="Generador sintético interno (sin hardware)",
            device_family="mock",
            backend_ready=True,
        )
    ]

    from core.rf.source_ids import ANALYZER_ONLY_DEVICES

    for spec in hardware_device_specs():
        if spec.device_id in ANALYZER_ONLY_DEVICES:
            continue
        usb_devices = enumerate_usb_for_spec(spec)
        results.extend(_descriptor_from_spec(spec, usb_devices, probe_backend=probe_backend))

    from core.monitor.serial_discovery import detect_serial_analyzers

    results.extend(detect_serial_analyzers())

    return results


def idle_message_for_source(source_id: str, *, descriptors: Optional[List[SourceDescriptor]] = None) -> str:
    items = descriptors or detect_sources(probe_backend=False)
    base = map_source_id_to_device_id(source_id)
    for item in items:
        if item.source_id == source_id or (
            item.device_family == base and item.source_id.startswith(base)
        ):
            if item.setup_report and item.setup_report.ready_for_capture:
                return f"Listo: {item.display_name} — {item.detail}"
            if not item.available:
                return f"{item.display_name}: conecte por USB o revise el asistente de instalación"
            if item.setup_report and not item.setup_report.ready_for_capture:
                return f"{item.display_name} detectado — complete la instalación del driver/backend"
            if item.available:
                return f"Listo: {item.display_name} — {item.detail}"
            return item.detail
    return "Fuente seleccionada — pulse Iniciar"


def get_default_source_id(*, descriptors: Optional[List[SourceDescriptor]] = None) -> str:
    from core.rf.source_ids import is_analyzer_only_source

    items = descriptors or detect_sources(probe_backend=False)
    default_family = get_default_device_id()
    for item in items:
        if item.device_family == default_family and item.available:
            return item.source_id
    for item in items:
        if item.device_family == default_family:
            return item.source_id
    for item in items:
        if item.source_id != "mock" and item.available and not is_analyzer_only_source(item.source_id):
            return item.source_id
    for item in items:
        if item.source_id != "mock" and item.available:
            return item.source_id
    return "mock"


def prefer_playable_source_id(*, descriptors: Optional[List[SourceDescriptor]] = None) -> str:
    """Fuente para PLAY automático — prioriza SDR (HackRF) frente a analizadores serie."""
    from core.rf.source_ids import is_analyzer_only_source

    items = descriptors or detect_sources(probe_backend=False)
    for item in items:
        if item.source_id == "mock":
            continue
        if not item.available or is_analyzer_only_source(item.source_id):
            continue
        return item.source_id
    return get_default_source_id(descriptors=items)
