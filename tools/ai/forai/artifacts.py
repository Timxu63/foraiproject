from __future__ import annotations

import re
from pathlib import Path


def normalize_run_id(run_id: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9_.-]+", "-", run_id.strip())
    normalized = normalized.strip(".-")
    if not normalized:
        raise ValueError("run_id must contain at least one safe character.")
    return normalized


def artifact_dir(project_root: Path, run_id: str) -> Path:
    return project_root / "artifacts" / "ai-runs" / normalize_run_id(run_id)

