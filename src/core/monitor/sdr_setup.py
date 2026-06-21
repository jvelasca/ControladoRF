"""Comprobación multiplataforma de drivers, CLI y backends SDR."""
from __future__ import annotations

import importlib.util
import os
import platform
import shutil
import sys
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from core.monitor.sdr_catalog import InstallStep, SdrDeviceSpec, get_device_spec, hardware_device_specs


@dataclass(frozen=True)
class PlatformInfo:
    system: str
    machine: str
    python_version: str
    platform_key: str


@dataclass
class CheckResult:
    ok: bool
    summary: str
    detail: str = ""


@dataclass
class DeviceSetupReport:
    device_id: str
    display_name: str
    is_default: bool
    usb: CheckResult
    cli: CheckResult
    native_lib: CheckResult
    python_backend: CheckResult
    usb_devices: List[str] = field(default_factory=list)
    install_steps: Tuple[InstallStep, ...] = ()
    ready_for_capture: bool = False

    @property
    def overall_status(self) -> str:
        if self.ready_for_capture:
            return "ready"
        if self.usb.ok and (self.cli.ok or self.native_lib.ok):
            return "partial"
        if self.usb.ok:
            return "usb_only"
        return "missing"


def get_platform_info() -> PlatformInfo:
    system = sys.platform
    if system.startswith("linux"):
        key = "linux"
    elif system == "darwin":
        key = "darwin"
    else:
        key = "win32"
    return PlatformInfo(
        system=system,
        machine=platform.machine(),
        python_version=platform.python_version(),
        platform_key=key,
    )


def _find_native_lib(names: Tuple[str, ...]) -> CheckResult:
    from core.monitor.hackrf_paths import local_pothos_bin_dir, resolve_hackrf_bin_dir

    local = local_pothos_bin_dir()
    if local:
        for name in names:
            candidate = local / name
            if candidate.is_file():
                return CheckResult(True, name, str(candidate))

    bin_dir = resolve_hackrf_bin_dir()
    if bin_dir:
        for name in names:
            candidate = bin_dir / name
            if candidate.is_file():
                return CheckResult(True, name, str(candidate))

    search_dirs: list[str] = []
    if sys.platform == "win32":
        search_dirs.extend(
            [
                os.environ.get("HACKRF_LIB_DIR", ""),
                os.environ.get("AIRSPY_LIB_DIR", ""),
                r"C:\Program Files\HackRF\bin",
                r"C:\Program Files\PothosSDR\bin",
                r"C:\Program Files\Airspy\bin",
            ]
        )
        path_env = os.environ.get("PATH", "")
        search_dirs.extend(path_env.split(os.pathsep))
    else:
        search_dirs.extend(
            [
                "/usr/local/lib",
                "/usr/lib",
                "/opt/homebrew/lib",
                "/Library/Frameworks",
            ]
        )
    for directory in search_dirs:
        if not directory or not os.path.isdir(directory):
            continue
        for name in names:
            candidate = os.path.join(directory, name)
            if os.path.isfile(candidate):
                return CheckResult(True, name, candidate)
    return CheckResult(False, "No encontrada", ", ".join(names))


def _check_cli(tools: Tuple[str, ...]) -> CheckResult:
    from core.monitor.hackrf_paths import resolve_hackrf_tool

    for tool in tools:
        path = resolve_hackrf_tool(tool)
        if path:
            return CheckResult(True, tool, str(path))
    found = [tool for tool in tools if shutil.which(tool)]
    if found:
        return CheckResult(True, found[0], shutil.which(found[0]) or found[0])
    return CheckResult(False, "No en PATH", ", ".join(tools))


def _check_python_packages(packages: Tuple[str, ...]) -> CheckResult:
    missing = []
    found = []
    for package in packages:
        module = package.replace("-", "_")
        if importlib.util.find_spec(module) is not None:
            found.append(package)
        else:
            missing.append(package)
    if found and not missing:
        return CheckResult(True, ", ".join(found), "Paquetes Python instalados")
    if found:
        return CheckResult(False, "Parcial", f"OK: {found} · Falta: {missing}")
    return CheckResult(False, "No instalado", ", ".join(packages))


def probe_python_hackrf(*, timeout_sec: float = 4.0) -> CheckResult:
    if importlib.util.find_spec("python_hackrf") is None:
        return CheckResult(False, "python_hackrf ausente", "pip install python_hackrf")
    try:
        import python_hackrf as ph  # type: ignore

        count = len(ph.HackRFDevice.get_all_devices())
        return CheckResult(True, "python_hackrf OK", f"{count} dispositivo(s)")
    except Exception as exc:  # pragma: no cover
        return CheckResult(False, "Backend error", str(exc)[:200])


def build_device_setup_report(
    spec: SdrDeviceSpec,
    *,
    usb_devices: Optional[List[str]] = None,
    platform_info: Optional[PlatformInfo] = None,
    probe_python: bool = True,
) -> DeviceSetupReport:
    pinfo = platform_info or get_platform_info()
    libs = spec.native_libs.get(pinfo.platform_key, ())
    cli = _check_cli(spec.cli_tools)
    native = _find_native_lib(libs)
    python = _check_python_packages(spec.python_packages)

    if spec.device_id == "hackrf" and probe_python:
        python = probe_python_hackrf()

    usb_list = usb_devices or []
    usb_ok = len(usb_list) > 0
    usb = CheckResult(
        usb_ok,
        f"{len(usb_list)} detectado(s)" if usb_ok else "No detectado",
        "; ".join(usb_list) if usb_list else "Conecte el equipo por USB",
    )

    steps = spec.install_steps.get(pinfo.platform_key, ())
    ready = usb_ok and (cli.ok or native.ok or python.ok)

    return DeviceSetupReport(
        device_id=spec.device_id,
        display_name=spec.display_name,
        is_default=spec.is_default,
        usb=usb,
        cli=cli,
        native_lib=native,
        python_backend=python,
        usb_devices=usb_list,
        install_steps=steps,
        ready_for_capture=ready,
    )


def build_all_setup_reports(*, probe_python: bool = True) -> List[DeviceSetupReport]:
    from core.monitor.device_discovery import enumerate_usb_for_spec

    reports = []
    for spec in hardware_device_specs():
        usb = enumerate_usb_for_spec(spec)
        labels = [f"{d.friendly_name} ({d.serial or d.status})" for d in usb]
        reports.append(
            build_device_setup_report(spec, usb_devices=labels, probe_python=probe_python)
        )
    return reports


def recommended_next_steps(report: DeviceSetupReport) -> List[InstallStep]:
    if report.ready_for_capture:
        return []
    pending = []
    for step in report.install_steps:
        if report.usb.ok and step.step_id in {"driver", "brew", "packages", "udev"}:
            if report.cli.ok or report.native_lib.ok:
                continue
        pending.append(step)
    return pending


def map_source_id_to_device_id(source_id: str) -> str:
    if source_id == "mock":
        return "mock"
    if source_id.startswith("airspy_hf"):
        return "airspy_hf"
    if source_id.startswith("airspy"):
        return "airspy"
    if source_id.startswith("hackrf"):
        return "hackrf"
    spec = get_device_spec(source_id)
    return spec.device_id if spec else source_id
