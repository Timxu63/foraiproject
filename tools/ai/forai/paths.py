from __future__ import annotations

from pathlib import Path


def find_project_root(start: Path | None = None) -> Path:
    current = (start or Path.cwd()).resolve()
    if current.is_file():
        current = current.parent

    for candidate in [current, *current.parents]:
        if (candidate / "ProjectSettings" / "ProjectVersion.txt").exists():
            return candidate

    raise FileNotFoundError("Could not find Unity project root from current path.")


def schema_dir(project_root: Path) -> Path:
    return project_root / "tools" / "ai" / "schemas"


def gateway_python_dir(project_root: Path) -> Path:
    return project_root / "Packages" / "com.forai.roslyn-gateway" / "Python~"

