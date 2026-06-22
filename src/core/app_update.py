"""Comprobación de actualizaciones vía GitHub Releases."""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from app_paths import bundle_path, is_frozen
from gui.app_branding import get_app_version


@dataclass(frozen=True)
class UpdateInfo:
    current_version: str
    latest_version: str
    release_name: str
    release_notes: str
    download_url: str
    html_url: str


@dataclass(frozen=True)
class UpdateCheckResult:
    """Resultado de comprobar GitHub Releases (/releases/latest)."""

    status: str  # available | current | error | disabled | not_packaged
    info: Optional[UpdateInfo] = None
    latest_published: str = ""
    current_version: str = ""


def _config_path() -> Path:
    return bundle_path("resources", "update_config.json")


def load_update_config() -> dict[str, Any]:
    path = _config_path()
    if not path.is_file():
        return {"enabled": False}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"enabled": False}
    return data if isinstance(data, dict) else {"enabled": False}


def _parse_version(text: str) -> tuple[int, ...]:
    match = re.search(r"(\d+(?:\.\d+)*)", str(text or ""))
    if not match:
        return (0,)
    parts: list[int] = []
    for chunk in match.group(1).split("."):
        try:
            parts.append(int(chunk))
        except ValueError:
            parts.append(0)
    return tuple(parts) or (0,)


def is_newer_version(current: str, latest: str) -> bool:
    return _parse_version(latest) > _parse_version(current)


def _asset_suffixes(config: dict[str, Any]) -> list[str]:
    raw = config.get("asset_suffixes")
    if isinstance(raw, list):
        suffixes = [str(item).strip() for item in raw if str(item).strip()]
        if suffixes:
            return suffixes
    legacy = str(config.get("asset_suffix") or "-w11.zip").strip()
    return [legacy] if legacy else ["-w11.zip"]


def _pick_asset_url(release: dict[str, Any], suffixes: list[str]) -> str:
    assets = release.get("assets") or []
    if not isinstance(assets, list):
        return ""
    for suffix in suffixes:
        suffix_lower = suffix.lower()
        for asset in assets:
            if not isinstance(asset, dict):
                continue
            name = str(asset.get("name") or "")
            url = str(asset.get("browser_download_url") or "")
            if name.lower().endswith(suffix_lower) and url:
                return url
    for asset in assets:
        if not isinstance(asset, dict):
            continue
        name = str(asset.get("name") or "").lower()
        url = str(asset.get("browser_download_url") or "")
        if name.endswith(".exe") and "setup" in name and url:
            return url
    for asset in assets:
        if not isinstance(asset, dict):
            continue
        name = str(asset.get("name") or "").lower()
        url = str(asset.get("browser_download_url") or "")
        if name.endswith(".zip") and url:
            return url
    return ""


def check_for_update(*, timeout_sec: float = 12.0) -> UpdateCheckResult:
    """Consulta GitHub Releases (/releases/latest)."""
    current = get_app_version()
    if not is_frozen():
        return UpdateCheckResult(status="not_packaged", current_version=current)
    config = load_update_config()
    if not config.get("enabled"):
        return UpdateCheckResult(status="disabled", current_version=current)
    owner = str(config.get("github_owner") or "").strip()
    repo = str(config.get("github_repo") or "").strip()
    if not owner or not repo or owner.startswith("TU_"):
        return UpdateCheckResult(status="disabled", current_version=current)

    suffixes = _asset_suffixes(config)
    url = f"https://api.github.com/repos/{owner}/{repo}/releases/latest"
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "ControladoRF-Updater",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_sec) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return UpdateCheckResult(status="error", current_version=current)

    if not isinstance(payload, dict):
        return UpdateCheckResult(status="error", current_version=current)
    tag = str(payload.get("tag_name") or payload.get("name") or "").lstrip("vV")
    if not tag:
        return UpdateCheckResult(status="error", current_version=current)
    if not is_newer_version(current, tag):
        return UpdateCheckResult(
            status="current",
            current_version=current,
            latest_published=tag,
        )

    download_url = _pick_asset_url(payload, suffixes)
    html_url = str(payload.get("html_url") or "")
    if not download_url and not html_url:
        return UpdateCheckResult(status="error", current_version=current)

    notes = str(payload.get("body") or "").strip()
    info = UpdateInfo(
        current_version=current,
        latest_version=tag,
        release_name=str(payload.get("name") or f"v{tag}"),
        release_notes=notes,
        download_url=download_url,
        html_url=html_url,
    )
    return UpdateCheckResult(status="available", info=info, current_version=current)
