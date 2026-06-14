from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def read_unity_version(project_root: Path) -> str:
    version_file = project_root / "ProjectSettings" / "ProjectVersion.txt"
    for line in version_file.read_text(encoding="utf-8-sig").splitlines():
        if line.startswith("m_EditorVersion:"):
            return line.split(":", 1)[1].strip()
    return ""


def read_packages(project_root: Path) -> list[dict[str, str]]:
    manifest = json.loads((project_root / "Packages" / "manifest.json").read_text(encoding="utf-8-sig"))
    dependencies = manifest.get("dependencies", {})
    return [
        {"name": name, "version": str(version)}
        for name, version in sorted(dependencies.items())
    ]


def scan_paths(project_root: Path) -> list[str]:
    candidates = set([
        "AGENTS.md",
        "docs/ai/architecture.md",
        "docs/ai/capability-registry.md",
        "docs/ai/project-map.md",
        "docs/ai/risk-policy.md",
        "docs/ai/workflows.md",
        "docs/ai/agent-orchestration.md",
        "Packages/manifest.json",
        "ProjectSettings/ProjectVersion.txt",
        "tools/ai/ai.py",
        "tools/ai/schemas/context-pack.v1.schema.json",
        "tools/ai/schemas/domain-spec.v1.schema.json",
        "tools/ai/schemas/execution-plan.v1.schema.json",
        "tools/ai/schemas/intent-analysis.v1.schema.json",
        "tools/ai/schemas/requirement-check.v1.schema.json",
        "tools/ai/schemas/risk-review.v1.schema.json",
        "tools/ai/schemas/unity-execution.v1.schema.json",
        "tools/ai/schemas/validation-report.v1.schema.json",
        "tools/ai/schemas/workflow-state.v1.schema.json",
    ])

    for pattern in (
        "tools/ai/schemas/*.json",
        "tools/ai/forai/*.py",
        "tools/ai/tests/test_*.py",
        "tools/ai/examples/*.json",
    ):
        candidates.update(
            path.relative_to(project_root).as_posix()
            for path in project_root.glob(pattern)
            if path.is_file()
        )

    return sorted(path for path in candidates if (project_root / path).exists())


def scan_context_pack(project_root: Path) -> dict[str, Any]:
    return {
        "version": "context-pack/v1",
        "projectRoot": str(project_root),
        "unityVersion": read_unity_version(project_root),
        "packages": read_packages(project_root),
        "paths": scan_paths(project_root),
        "summaries": [
            {
                "source": "ProjectSettings/ProjectVersion.txt",
                "summary": "Unity editor version is recorded for deterministic target matching.",
            },
            {
                "source": "Packages/manifest.json",
                "summary": "Unity package dependencies are captured for planning and validation context.",
            },
            {
                "source": "docs/ai",
                "summary": "AI architecture, workflow, capability and risk documents define project boundaries.",
            },
        ],
    }
