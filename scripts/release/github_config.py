"""Lee la configuración de GitHub Releases desde update_config.json."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from scripts.release.common import ROOT, read_version

UPDATE_CONFIG = ROOT / "src" / "resources" / "update_config.json"


@dataclass(frozen=True)
class GitHubReleaseConfig:
    enabled: bool
    owner: str
    repo: str
    version: str

    @property
    def slug(self) -> str:
        return f"{self.owner}/{self.repo}"

    @property
    def tag(self) -> str:
        return f"v{self.version}"


def load_github_release_config(*, version: str | None = None) -> GitHubReleaseConfig:
    version = version or read_version()
    if not UPDATE_CONFIG.is_file():
        raise FileNotFoundError(f"No se encontró {UPDATE_CONFIG}")
    data = json.loads(UPDATE_CONFIG.read_text(encoding="utf-8"))
    owner = str(data.get("github_owner") or "").strip()
    repo = str(data.get("github_repo") or "").strip()
    if not owner or not repo or owner.startswith("TU_"):
        raise ValueError(
            "Configure github_owner y github_repo en src/resources/update_config.json"
        )
    return GitHubReleaseConfig(
        enabled=bool(data.get("enabled")),
        owner=owner,
        repo=repo,
        version=version,
    )
