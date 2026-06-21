"""Catálogo de equipos SDR compatibles (referencia SDR++ / CONTROLADORF)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Tuple


@dataclass(frozen=True)
class InstallStep:
    """Paso de instalación mostrado en el asistente."""

    step_id: str
    title_key: str
    detail_key: str
    command_key: str = ""
    doc_url: str = ""
    optional: bool = False


@dataclass(frozen=True)
class SdrDeviceSpec:
    """Definición de un equipo SDR soportado o planificado."""

    device_id: str
    display_name: str
    sdrpp_source: str
    is_default: bool = False
    usb_name_patterns: Tuple[str, ...] = ()
    usb_text_patterns: Tuple[str, ...] = ()
    vid_pid: Tuple[str, ...] = ()
    cli_tools: Tuple[str, ...] = ()
    native_libs: Dict[str, Tuple[str, ...]] = field(default_factory=dict)
    python_packages: Tuple[str, ...] = ()
    install_steps: Dict[str, Tuple[InstallStep, ...]] = field(default_factory=dict)


def _hackrf_steps() -> Dict[str, Tuple[InstallStep, ...]]:
    return {
        "win32": (
            InstallStep(
                "driver",
                "monitor_setup_hackrf_win_driver_title",
                "monitor_setup_hackrf_win_driver_detail",
                "monitor_setup_hackrf_win_driver_cmd",
                "https://github.com/greatscottgadgets/hackrf/releases",
            ),
            InstallStep(
                "path",
                "monitor_setup_hackrf_win_path_title",
                "monitor_setup_hackrf_win_path_detail",
                "monitor_setup_hackrf_win_path_cmd",
            ),
            InstallStep(
                "python",
                "monitor_setup_hackrf_python_title",
                "monitor_setup_hackrf_python_detail",
                "monitor_setup_hackrf_python_cmd",
                "https://pypi.org/project/python-hackrf/",
                optional=True,
            ),
        ),
        "darwin": (
            InstallStep(
                "brew",
                "monitor_setup_hackrf_mac_brew_title",
                "monitor_setup_hackrf_mac_brew_detail",
                "monitor_setup_hackrf_mac_brew_cmd",
                "https://formulae.brew.sh/formula/hackrf",
            ),
            InstallStep(
                "python",
                "monitor_setup_hackrf_python_title",
                "monitor_setup_hackrf_python_detail",
                "monitor_setup_hackrf_python_cmd",
                optional=True,
            ),
        ),
        "linux": (
            InstallStep(
                "packages",
                "monitor_setup_hackrf_linux_pkg_title",
                "monitor_setup_hackrf_linux_pkg_detail",
                "monitor_setup_hackrf_linux_pkg_cmd",
                "https://github.com/greatscottgadgets/hackrf",
            ),
            InstallStep(
                "udev",
                "monitor_setup_hackrf_linux_udev_title",
                "monitor_setup_hackrf_linux_udev_detail",
                "monitor_setup_hackrf_linux_udev_cmd",
            ),
            InstallStep(
                "python",
                "monitor_setup_hackrf_python_title",
                "monitor_setup_hackrf_python_detail",
                "monitor_setup_hackrf_python_cmd",
                optional=True,
            ),
        ),
    }


def _airspy_steps() -> Dict[str, Tuple[InstallStep, ...]]:
    return {
        "win32": (
            InstallStep(
                "driver",
                "monitor_setup_airspy_win_driver_title",
                "monitor_setup_airspy_win_driver_detail",
                "monitor_setup_airspy_win_driver_cmd",
                "https://airspy.com/download/",
            ),
            InstallStep(
                "tools",
                "monitor_setup_airspy_tools_title",
                "monitor_setup_airspy_tools_detail",
                "monitor_setup_airspy_win_tools_cmd",
            ),
        ),
        "darwin": (
            InstallStep(
                "brew",
                "monitor_setup_airspy_mac_brew_title",
                "monitor_setup_airspy_mac_brew_detail",
                "monitor_setup_airspy_mac_brew_cmd",
            ),
        ),
        "linux": (
            InstallStep(
                "packages",
                "monitor_setup_airspy_linux_pkg_title",
                "monitor_setup_airspy_linux_pkg_detail",
                "monitor_setup_airspy_linux_pkg_cmd",
            ),
            InstallStep(
                "udev",
                "monitor_setup_airspy_linux_udev_title",
                "monitor_setup_airspy_linux_udev_detail",
                "monitor_setup_airspy_linux_udev_cmd",
            ),
        ),
    }


def _airspy_hf_steps() -> Dict[str, Tuple[InstallStep, ...]]:
    return {
        "win32": (
            InstallStep(
                "driver",
                "monitor_setup_airspyhf_win_driver_title",
                "monitor_setup_airspyhf_win_driver_detail",
                "monitor_setup_airspyhf_win_driver_cmd",
                "https://airspy.com/airspy-hf-plus/",
            ),
            InstallStep(
                "tools",
                "monitor_setup_airspyhf_tools_title",
                "monitor_setup_airspyhf_tools_detail",
                "monitor_setup_airspyhf_win_tools_cmd",
            ),
        ),
        "darwin": (
            InstallStep(
                "brew",
                "monitor_setup_airspyhf_mac_brew_title",
                "monitor_setup_airspyhf_mac_brew_detail",
                "monitor_setup_airspyhf_mac_brew_cmd",
            ),
        ),
        "linux": (
            InstallStep(
                "packages",
                "monitor_setup_airspyhf_linux_pkg_title",
                "monitor_setup_airspyhf_linux_pkg_detail",
                "monitor_setup_airspyhf_linux_pkg_cmd",
            ),
        ),
    }


SDR_DEVICE_CATALOG: Tuple[SdrDeviceSpec, ...] = (
    SdrDeviceSpec(
        device_id="hackrf",
        display_name="HackRF One",
        sdrpp_source="hackrf_source",
        is_default=True,
        usb_name_patterns=("HackRF",),
        usb_text_patterns=(r"hackrf", r"1d50:6089", r"VID_1D50&PID_6089"),
        vid_pid=("1d50:6089",),
        cli_tools=("hackrf_info", "hackrf_transfer"),
        native_libs={
            "win32": ("hackrf.dll", "libhackrf.dll"),
            "darwin": ("libhackrf.dylib",),
            "linux": ("libhackrf.so",),
        },
        python_packages=("python_hackrf",),
        install_steps=_hackrf_steps(),
    ),
    SdrDeviceSpec(
        device_id="airspy",
        display_name="Airspy R2 / Mini",
        sdrpp_source="airspy_source",
        usb_name_patterns=("Airspy",),
        usb_text_patterns=(r"airspy", r"1d50:60a1", r"VID_1D50&PID_60A1"),
        vid_pid=("1d50:60a1",),
        cli_tools=("airspy_info",),
        native_libs={
            "win32": ("airspy.dll", "libairspy.dll"),
            "darwin": ("libairspy.dylib",),
            "linux": ("libairspy.so",),
        },
        python_packages=("pyairspy",),
        install_steps=_airspy_steps(),
    ),
    SdrDeviceSpec(
        device_id="airspy_hf",
        display_name="Airspy HF+",
        sdrpp_source="airspyhf_source",
        usb_name_patterns=("Airspy HF", "HF+"),
        usb_text_patterns=(r"airspy hf", r"1d50:60e1", r"VID_1D50&PID_60E1"),
        vid_pid=("1d50:60e1",),
        cli_tools=("airspy_info",),
        native_libs={
            "win32": ("airspyhf.dll", "libairspyhf.dll"),
            "darwin": ("libairspyhf.dylib",),
            "linux": ("libairspyhf.so",),
        },
        python_packages=("pyairspy",),
        install_steps=_airspy_hf_steps(),
    ),
)


def get_device_spec(device_id: str) -> SdrDeviceSpec | None:
    if device_id.startswith("airspy_hf"):
        base = "airspy_hf"
    elif device_id.startswith("airspy"):
        base = "airspy"
    elif device_id.startswith("hackrf"):
        base = "hackrf"
    else:
        base = device_id
    for spec in SDR_DEVICE_CATALOG:
        if spec.device_id == base:
            return spec
    return None


def get_default_device_id() -> str:
    for spec in SDR_DEVICE_CATALOG:
        if spec.is_default:
            return spec.device_id
    return SDR_DEVICE_CATALOG[0].device_id


def hardware_device_specs() -> List[SdrDeviceSpec]:
    return list(SDR_DEVICE_CATALOG)
