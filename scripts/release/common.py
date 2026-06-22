"""Utilidades compartidas para empaquetado CONTROLADORF."""
from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
ENTRY = SRC / "main.py"
DEFAULT_OUTPUT_DIR = Path.home() / "Documents" / "distribuciones python"
APP_BASENAME = "ControladoRF"
BUILD_DIR = ROOT / "build" / "pyinstaller"
SPEC_DIR = ROOT / "build" / "spec"
STAGING_ROOT = ROOT / "build" / "dist"


@dataclass(frozen=True)
class PyInstallerResult:
    exe_path: Path
    bundle_dir: Path


def sep() -> str:
    return ";" if os.name == "nt" else ":"


def read_version() -> str:
    version_file = SRC / "VERSION"
    try:
        return version_file.read_text(encoding="utf-8").strip() or "0.0.0"
    except OSError:
        return "0.0.0"


def package_folder_name(version: str) -> str:
    return f"{APP_BASENAME}-{version}-w11"


def package_zip_name(version: str) -> str:
    return f"{package_folder_name(version)}.zip"


def package_setup_name(version: str) -> str:
    return f"{package_folder_name(version)}-Setup.exe"


def ensure_pyinstaller() -> None:
    if importlib.util.find_spec("PyInstaller") is None:
        print("Instalando PyInstaller…")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller>=6.0"])


def ensure_src_path() -> None:
    src_text = str(SRC)
    if src_text not in sys.path:
        sys.path.insert(0, src_text)


def ensure_icon(icons_dir: Path | None = None) -> Path:
    target_dir = icons_dir or (SRC / "resources" / "icons")
    target_dir.mkdir(parents=True, exist_ok=True)
    ico_path = target_dir / "ico.ico"
    if ico_path.is_file():
        return ico_path

    for candidate in ("brand.png", "logo.png", "app.png"):
        png_path = target_dir / candidate
        if png_path.is_file():
            ensure_src_path()
            from PyQt6.QtGui import QPixmap
            from PyQt6.QtWidgets import QApplication

            app = QApplication.instance() or QApplication([])
            pixmap = QPixmap(str(png_path))
            if not pixmap.isNull() and pixmap.save(str(ico_path), "ICO"):
                return ico_path

    ensure_src_path()
    from PyQt6.QtWidgets import QApplication
    from gui.app_branding import get_app_window_icon

    app = QApplication.instance() or QApplication([])
    icon = get_app_window_icon()
    pixmap = icon.pixmap(256, 256)
    if pixmap.isNull() or not pixmap.save(str(ico_path), "ICO"):
        raise RuntimeError(f"No se pudo generar el icono en {ico_path}")
    return ico_path


def collect_data_files() -> list[tuple[str, str]]:
    datas: list[tuple[str, str]] = []

    def add(source: Path, target: str) -> None:
        if source.is_file():
            datas.append((str(source), target))
        elif source.is_dir():
            for path in sorted(source.rglob("*")):
                if path.is_file():
                    rel = path.relative_to(source)
                    datas.append((str(path), str(Path(target) / rel).replace("\\", "/")))

    add(SRC / "VERSION", ".")
    add(SRC / "i18n" / "es.json", "i18n")
    add(SRC / "i18n" / "en.json", "i18n")

    docs = ROOT / "docs"
    for name in (
        "ayuda.md",
        "help.md",
        "monitor_supervision_ayuda.md",
        "monitor_supervision_help.md",
    ):
        add(docs / name, "docs")

    workspace_seed = SRC / "workspace" / "data" / "workspaces.json"
    add(workspace_seed, "workspace/data")

    icons_dir = SRC / "resources" / "icons"
    for name in ("ico.ico", "brand.png", "logo.png", "app.png"):
        add(icons_dir / name, "resources/icons")
    add(SRC / "resources" / "update_config.json", "resources")

    return datas


def format_add_data_args(datas: list[tuple[str, str]]) -> list[str]:
    args: list[str] = []
    for source, target in datas:
        args.extend(["--add-data", f"{source}{sep()}{target}"])
    return args


def run_pyinstaller(
    *,
    icon_path: Path,
    output_dir: Path,
    version: str,
    clean: bool,
    exe_basename: str | None = None,
    onefile: bool = False,
) -> PyInstallerResult:
    output_dir.mkdir(parents=True, exist_ok=True)
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    SPEC_DIR.mkdir(parents=True, exist_ok=True)

    exe_name = exe_basename or APP_BASENAME
    datas = collect_data_files()

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--onedir" if not onefile else "--onefile",
        "--windowed",
        "--name",
        exe_name,
        "--distpath",
        str(output_dir),
        "--workpath",
        str(BUILD_DIR),
        "--specpath",
        str(SPEC_DIR),
        "--paths",
        str(SRC),
        "--icon",
        str(icon_path),
        *format_add_data_args(datas),
        "--hidden-import",
        "PyQt6.sip",
        "--hidden-import",
        "PyQt6.QtMultimedia",
        "--collect-submodules",
        "PyQt6",
        "--collect-submodules",
        "PyQt6.QtMultimedia",
        "--collect-submodules",
        "numpy",
        str(ENTRY),
    ]
    if clean:
        cmd.insert(4, "--clean")

    print("Ejecutando PyInstaller…")
    subprocess.check_call(cmd, cwd=str(ROOT))

    if onefile:
        exe_path = output_dir / f"{exe_name}.exe"
        if not exe_path.is_file():
            raise FileNotFoundError(f"No se generó el ejecutable esperado: {exe_path}")
        return PyInstallerResult(exe_path=exe_path, bundle_dir=output_dir)

    bundle_dir = output_dir / exe_name
    exe_path = bundle_dir / f"{exe_name}.exe"
    if not exe_path.is_file():
        raise FileNotFoundError(f"No se generó el ejecutable esperado: {exe_path}")
    return PyInstallerResult(exe_path=exe_path, bundle_dir=bundle_dir)


def timestamp() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
