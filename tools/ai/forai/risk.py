from __future__ import annotations

from typing import Any


RISK_ORDER = {"low": 0, "medium": 1, "high": 2, "blocked": 3}
DIRECT_UNITY_YAML_EXTENSIONS = (".unity", ".prefab", ".asset", ".meta")
SENSITIVE_PROJECT_FILES = {"Packages/manifest.json", "Packages/packages-lock.json"}
HIGH_RISK_DESCRIPTION_KEYWORDS = ("overwrite", "delete", "move", "rename", "bulk", "批量", "删除", "移动", "重命名", "覆盖")


def max_risk(left: str, right: str) -> str:
    return left if RISK_ORDER[left] >= RISK_ORDER[right] else right


def classify_step(step: dict[str, Any]) -> tuple[str, str]:
    step_id = str(step.get("id", ""))
    kind = str(step.get("kind", ""))
    target = str(step.get("target", "")).replace("\\", "/")
    description = str(step.get("description", ""))
    parts = [part for part in target.split("/") if part]

    if ".." in parts:
        return "blocked", f"Step {step_id} targets a parent-directory path."

    if target.startswith("ProjectSettings/") or target in SENSITIVE_PROJECT_FILES:
        return "high", f"Step {step_id} changes sensitive project configuration."

    if kind != "unity_adapter" and target.endswith(DIRECT_UNITY_YAML_EXTENSIONS):
        return "blocked", f"Step {step_id} attempts direct Unity YAML or metadata mutation."

    if kind == "unity_adapter":
        if target.endswith((".unity", ".prefab")):
            return "high", f"Step {step_id} changes scene or prefab content through Unity Editor Adapter."
        if any(keyword in description.lower() for keyword in HIGH_RISK_DESCRIPTION_KEYWORDS):
            return "high", f"Step {step_id} describes a high-risk Unity operation: {description}"
        return "medium", f"Step {step_id} uses Unity Editor Adapter: {description}"

    if kind in {"cli", "validation"}:
        return "low", f"Step {step_id} is deterministic CLI or validation work."

    if kind == "read_only":
        return "low", f"Step {step_id} is read-only."

    return "medium", f"Step {step_id} has unknown risk kind: {kind}"


def review_execution_plan(plan: dict[str, Any]) -> dict[str, Any]:
    overall = "low"
    findings: list[dict[str, str]] = []

    for step in plan.get("steps", []):
        risk, message = classify_step(step)
        overall = max_risk(overall, risk)
        findings.append({"risk": risk, "message": message})

    preview_required = overall == "high"
    return {
        "version": "risk-review/v1",
        "runId": plan["runId"],
        "overallRisk": overall,
        "findings": findings,
        "confirmationRequired": overall in {"medium", "high", "blocked"},
        "gateReason": gate_reason(overall),
        "previewRequired": preview_required,
        "previewArtifacts": ["dry-run-preview"] if preview_required else [],
    }


def gate_reason(risk: str) -> str:
    if risk == "blocked":
        return "Blocked risk requires revising the execution plan."
    if risk == "high":
        return "High risk requires explicit approval and preview evidence."
    if risk == "medium":
        return "Medium risk requires approval before execution."
    return ""
