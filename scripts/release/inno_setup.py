"""Localiza Inno Setup (ISCC) y compila el instalador Windows."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.release.common import (  # noqa: E402
    APP_BASENAME,
    DEFAULT_OUTPUT_DIR,
    ROOT,
    SRC,
    ensure_icon,
    package_setup_name,
    read_version,
)

PACKAGING_DIR = ROOT / "packaging" / "w11"
ISS_FILE = PACKAGING_DIR / "installer.iss"

ISCC_CANDIDATES = (
    Path(r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe"),
    Path(r"C:\Program Files\Inno Setup 6\ISCC.exe"),
    Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Inno Setup 6" / "ISCC.exe",
    Path(os.environ.get("ProgramFiles(x86)", "")) / "Inno Setup 6" / "ISCC.exe",
    Path(os.environ.get("ProgramFiles", "")) / "Inno Setup 6" / "ISCC.exe",
)


def find_iscc() -> Path | None:
    for candidate in ISCC_CANDIDATES:
        if candidate.is_file():
            return candidate
    found = shutil.which("ISCC.exe") or shutil.which("iscc")
    return Path(found) if found else None


def install_inno_setup_via_winget() -> Path | None:
    if not shutil.which("winget"):
        return None
    print("Instalando Inno Setup 6 con winget…")
    try:
        subprocess.check_call(
            [
                "winget",
                "install",
                "--id",
                "JRSoftware.InnoSetup",
                "-e",
                "--accept-package-agreements",
                "--accept-source-agreements",
            ],
            stdout=subprocess.DEVNULL,
        )
    except (subprocess.CalledProcessError, OSError):
        return None
    return find_iscc()


def ensure_iscc(*, allow_install: bool = True) -> Path:
    path = find_iscc()
    if path is not None:
        return path
    if allow_install:
        path = install_inno_setup_via_winget()
        if path is not None:
            return path
    raise RuntimeError(
        "Inno Setup 6 no encontrado. Instálelo desde https://jrsoftware.org/isinfo.php "
        "o ejecute: winget install JRSoftware.InnoSetup"
    )


def build_installer(
    *,
    package_dir: Path,
    output_dir: Path | None = None,
    version: str | None = None,
    allow_iscc_install: bool = True,
) -> Path:
    if not package_dir.is_dir():
        raise FileNotFoundError(f"No existe la carpeta del paquete: {package_dir}")

    version = version or read_version()
    output_dir = (output_dir or DEFAULT_OUTPUT_DIR).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    iscc = ensure_iscc(allow_install=allow_iscc_install)
    icon_path = ensure_icon()

    defines = [
        f"/DMyAppVersion={version}",
        f"/DSourceDir={package_dir}",
        f"/DOutputDir={output_dir}",
        f"/DMyAppIcon={icon_path}",
    ]
    cmd = [str(iscc), *defines, str(ISS_FILE)]
    print("Compilando instalador Inno Setup…")
    subprocess.check_call(cmd, cwd=str(ROOT))

    setup_path = output_dir / package_setup_name(version)
    if not setup_path.is_file():
        raise FileNotFoundError(f"No se generó el instalador esperado: {setup_path}")
    size_mb = setup_path.stat().st_size / (1024 * 1024)
    print(f"Setup:     {setup_path} ({size_mb:.1f} MB)")
    return setup_path


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Genera el instalador Setup.exe (Inno Setup)")
    parser.add_argument(
        "--package-dir",
        type=Path,
        help="Carpeta ControladoRF-<version>-w11 (por defecto: output dir + versión)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Destino del Setup.exe (por defecto: {DEFAULT_OUTPUT_DIR})",
    )
    parser.add_argument("--no-winget-install", action="store_true")
    args = parser.parse_args(argv)

    version = read_version()
    output_dir = args.output_dir.expanduser().resolve()
    package_dir = args.package_dir
    if package_dir is None:
        package_dir = output_dir / f"{APP_BASENAME}-{version}-w11"
    package_dir = package_dir.expanduser().resolve()

    build_installer(
        package_dir=package_dir,
        output_dir=output_dir,
        version=version,
        allow_iscc_install=not args.no_winget_install,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
