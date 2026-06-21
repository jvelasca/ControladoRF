"""Sesión persistente del asistente de calibración guiada."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

UserVerdict = Literal["pending", "pass", "fail", "skip"]


@dataclass
class StepRecord:
    step_id: str
    index: int
    title: str = ""
    user_verdict: UserVerdict = "pending"
    backend_passed: bool | None = None
    user_comment: str = ""
    backend_analysis: dict[str, Any] = field(default_factory=dict)
    coherence: dict[str, Any] = field(default_factory=dict)
    recorded_at: str = ""

    # Compatibilidad con logs antiguos
    @property
    def user_note(self) -> str:
        return self.user_comment

    @property
    def backend_snapshot(self) -> dict[str, Any]:
        return self.backend_analysis

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class WizardSession:
    session_id: str
    started_at: str
    records: dict[str, StepRecord] = field(default_factory=dict)
    finished_at: str = ""

    @property
    def passed_count(self) -> int:
        return sum(1 for r in self.records.values() if r.user_verdict == "pass")

    @property
    def failed_count(self) -> int:
        return sum(1 for r in self.records.values() if r.user_verdict == "fail")

    @property
    def skipped_count(self) -> int:
        return sum(1 for r in self.records.values() if r.user_verdict == "skip")

    @property
    def backend_fail_count(self) -> int:
        return sum(1 for r in self.records.values() if r.backend_passed is False)

    @property
    def incoherent_count(self) -> int:
        return sum(
            1
            for r in self.records.values()
            if r.coherence and not r.coherence.get("coherent", True)
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "summary": {
                "user_pass": self.passed_count,
                "user_fail": self.failed_count,
                "user_skip": self.skipped_count,
                "backend_fail": self.backend_fail_count,
                "incoherent": self.incoherent_count,
                "total_recorded": len(self.records),
            },
            "records": {k: v.to_dict() for k, v in self.records.items()},
        }


def new_session() -> WizardSession:
    now = datetime.now(timezone.utc)
    sid = now.strftime("%Y%m%d_%H%M%S")
    return WizardSession(session_id=sid, started_at=now.isoformat())


def record_step(
    session: WizardSession,
    *,
    step_id: str,
    index: int,
    title: str,
    user_verdict: UserVerdict,
    backend_passed: bool | None,
    backend_analysis: dict[str, Any],
    user_comment: str = "",
    coherence: dict[str, Any] | None = None,
) -> StepRecord:
    rec = StepRecord(
        step_id=step_id,
        index=index,
        title=title,
        user_verdict=user_verdict,
        backend_passed=backend_passed,
        user_comment=user_comment.strip(),
        backend_analysis=backend_analysis,
        coherence=coherence or {},
        recorded_at=datetime.now(timezone.utc).isoformat(),
    )
    session.records[step_id] = rec
    return rec


def save_session(session: WizardSession, log_dir: Path) -> tuple[Path, Path]:
    log_dir.mkdir(parents=True, exist_ok=True)
    json_path = log_dir / f"wizard_{session.session_id}.json"
    md_path = log_dir / f"wizard_{session.session_id}.md"
    json_path.write_text(
        json.dumps(session.to_dict(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    md_path.write_text(export_session_markdown(session), encoding="utf-8")
    latest_json = log_dir / "wizard_latest.json"
    latest_md = log_dir / "wizard_latest.md"
    latest_json.write_text(json_path.read_text(encoding="utf-8"), encoding="utf-8")
    latest_md.write_text(md_path.read_text(encoding="utf-8"), encoding="utf-8")
    return json_path, md_path


def load_session(path: Path) -> WizardSession | None:
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    session = WizardSession(
        session_id=str(data.get("session_id", "")),
        started_at=str(data.get("started_at", "")),
        finished_at=str(data.get("finished_at", "")),
    )
    for step_id, rec in (data.get("records") or {}).items():
        session.records[step_id] = StepRecord(
            step_id=str(rec.get("step_id", step_id)),
            index=int(rec.get("index", 0)),
            title=str(rec.get("title", "")),
            user_verdict=rec.get("user_verdict", "pending"),
            backend_passed=rec.get("backend_passed"),
            user_comment=str(rec.get("user_comment") or rec.get("user_note", "")),
            backend_analysis=dict(rec.get("backend_analysis") or rec.get("backend_snapshot") or {}),
            coherence=dict(rec.get("coherence") or {}),
            recorded_at=str(rec.get("recorded_at", "")),
        )
    return session


def export_session_markdown(session: WizardSession) -> str:
    """Informe legible para depuración y revisión."""
    lines = [
        "# Informe calibración guiada",
        "",
        f"- Sesión: `{session.session_id}`",
        f"- Inicio: {session.started_at}",
        f"- Fin: {session.finished_at or '—'}",
        "",
        "## Resumen",
        "",
        f"| Métrica | Valor |",
        f"|---------|-------|",
        f"| OK operador | {session.passed_count} |",
        f"| Falla operador | {session.failed_count} |",
        f"| Omitidos | {session.skipped_count} |",
        f"| Backend FAIL | {session.backend_fail_count} |",
        f"| Registros incoherentes | {session.incoherent_count} |",
        "",
        "## Checklist",
        "",
    ]
    ordered = sorted(session.records.values(), key=lambda r: r.index)
    for rec in ordered:
        icon = {"pass": "✓", "fail": "✗", "skip": "—"}.get(rec.user_verdict, "○")
        be = "PASS" if rec.backend_passed else ("FAIL" if rec.backend_passed is False else "—")
        lines.append(f"### {icon} {rec.index + 1}. {rec.title or rec.step_id}")
        lines.append("")
        lines.append(f"- **Operador:** {rec.user_verdict} | **Backend:** {be}")
        if rec.user_comment:
            lines.append(f"- **Comentario operador:** {rec.user_comment}")
            tags = (rec.coherence.get("comment_analysis") or {}).get("tags") or []
            if tags:
                lines.append(f"- **Etiquetas:** {', '.join(tags)}")
        if rec.coherence.get("issues"):
            lines.append("- **Incoherencias:**")
            for issue in rec.coherence["issues"]:
                lines.append(f"  - {issue}")
        analysis = rec.backend_analysis
        if analysis.get("mismatches"):
            lines.append("- **Esperado ≠ real:**")
            for m in analysis["mismatches"]:
                lines.append(f"  - {m}")
        if analysis.get("failed_checks"):
            lines.append("- **Cadena RF:**")
            for chk in analysis["failed_checks"]:
                lines.append(f"  - {chk.get('name')}: {chk.get('detail')}")
        if analysis.get("diagnosis"):
            lines.append("- **Diagnóstico backend:**")
            for d in analysis["diagnosis"]:
                lines.append(f"  - {d}")
        lines.append("")
    fails = [r for r in ordered if r.user_verdict == "fail" or r.backend_passed is False]
    if fails:
        lines.append("## Acciones sugeridas")
        lines.append("")
        for rec in fails:
            lines.append(f"- **{rec.step_id}**: revisar comentario y diagnóstico backend.")
        lines.append("")
    return "\n".join(lines)
