"""run_manifest.json: her çalıştırmanın başında yazılan tekrar üretilebilirlik kaydı."""
from __future__ import annotations

import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path

from .utils import ensure_parent, sha256_file

PACKAGES = ["layered-scoring", "openai", "anthropic", "google-genai", "pandas", "numpy", "scipy", "scikit-learn",
            "pydantic", "jinja2", "typer", "sentence-transformers", "torch", "spylls", "matplotlib"]


def new_run_id(tag: str) -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + f"_{tag}"


def _git(*args: str) -> str | None:
    try:
        return subprocess.run(["git", *args], capture_output=True, text=True, check=True).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def write_manifest(run_id: str, logs_dir: str | Path, results_dir: str | Path, config_files: list[str | Path],
                   seeds: dict, extra: dict, copy_to_results: bool = True) -> dict:
    files = [Path(p) for p in config_files] + sorted(Path("prompts").glob("*.j2"))
    versions = {}
    for p in PACKAGES:
        try:
            versions[p] = metadata.version(p)
        except metadata.PackageNotFoundError:
            versions[p] = None
    status = _git("status", "--porcelain")
    m = {
        "run_id": run_id,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit": _git("rev-parse", "HEAD"),
        "git_dirty": bool(status),
        "git_dirty_files": status.splitlines() if status else [],
        "config_sha256": {str(p): sha256_file(p) for p in files if p.exists()},
        "seeds": seeds,
        "python": sys.version,
        "platform": platform.platform(),
        "packages": versions,
        "argv": sys.argv,
        **extra,
    }
    targets = [Path(logs_dir) / run_id] + ([Path(results_dir) / "manifests"] if copy_to_results else [])
    for d in targets:
        name = "run_manifest.json" if d.name == run_id else f"{run_id}.json"
        ensure_parent(d / name).write_text(json.dumps(m, ensure_ascii=False, indent=2), encoding="utf-8")
    return m
