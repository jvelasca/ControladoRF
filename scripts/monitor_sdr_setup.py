#!/usr/bin/env python
"""Informe completo de instalación SDR multiplataforma (sin GUI)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from core.monitor.device_discovery import detect_sources
from core.monitor.sdr_setup import build_all_setup_reports, get_platform_info, recommended_next_steps


def main() -> int:
    parser = argparse.ArgumentParser(description="CONTROLADORF — diagnóstico SDR")
    parser.add_argument("--backend", action="store_true", help="Comprobar backends Python")
    parser.add_argument("--json", action="store_true", help="Salida JSON")
    args = parser.parse_args()

    pinfo = get_platform_info()
    reports = build_all_setup_reports(probe_python=args.backend)
    sources = detect_sources(probe_backend=args.backend)

    if args.json:
        payload = {
            "platform": pinfo.__dict__,
            "sources": [
                {
                    "source_id": s.source_id,
                    "display_name": s.display_name,
                    "available": s.available,
                    "detail": s.detail,
                    "device_family": s.device_family,
                }
                for s in sources
            ],
            "setup": [
                {
                    "device_id": r.device_id,
                    "display_name": r.display_name,
                    "ready": r.ready_for_capture,
                    "status": r.overall_status,
                    "usb": r.usb.__dict__,
                    "cli": r.cli.__dict__,
                    "native_lib": r.native_lib.__dict__,
                    "python_backend": r.python_backend.__dict__,
                    "next_steps": [step.step_id for step in recommended_next_steps(r)],
                }
                for r in reports
            ],
        }
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0

    print(f"Plataforma: {pinfo.system} / {pinfo.platform_key} / Python {pinfo.python_version}\n")
    print("=== Fuentes detectadas ===")
    for item in sources:
        flag = "OK" if item.available else "—"
        print(f"  [{flag}] {item.source_id}: {item.display_name}")
        print(f"       {item.detail}")

    print("\n=== Informe de instalación ===")
    for report in reports:
        mark = "READY" if report.ready_for_capture else report.overall_status.upper()
        default = " (default)" if report.is_default else ""
        print(f"\n--- {report.display_name}{default} [{mark}] ---")
        print(f"  USB:    {report.usb.summary} — {report.usb.detail}")
        print(f"  CLI:    {report.cli.summary} — {report.cli.detail}")
        print(f"  Lib:    {report.native_lib.summary} — {report.native_lib.detail}")
        print(f"  Python: {report.python_backend.summary} — {report.python_backend.detail}")
        steps = recommended_next_steps(report)
        if steps:
            print("  Pasos:")
            for step in steps:
                print(f"    • {step.step_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
