from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .artifacts import artifact_dir, normalize_run_id
from .json_io import read_json
from .schemas import SchemaValidationError, load_schema, validate_payload
from .workflow_state import add_artifact, workflow_state_path


PROFILES = {"question", "plan", "change"}
WORKFLOW_ARTIFACTS = [
    ("intent-analysis", "intent-analysis/v1", "intent_analysis", "produce intent-analysis/v1"),
    ("context-pack", "context-pack/v1", "context", "scan context"),
    ("requirement-check", "requirement-check/v1", "requirements", "produce requirement-check/v1"),
    ("domain-spec", "domain-spec/v1", "spec", "produce domain-spec/v1"),
    ("execution-plan", "execution-plan/v1", "plan", "produce execution-plan/v1"),
    ("risk-review", "risk-review/v1", "risk_review", "risk review"),
]


class WorkflowPreflightError(ValueError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def classify_profile(intent: str) -> str:
    normalized = intent.strip().lower()
    plan_phrase_keywords = [
        "执行方案",
        "执行计划",
        "实施方案",
        "实现方案",
        "设计方案",
        "workflow execution plan",
        "execution plan",
    ]
    change_keywords = [
        "实现",
        "修改",
        "修复",
        "新增",
        "添加",
        "删除",
        "执行",
        "implement",
        "change",
        "fix",
        "add",
        "delete",
        "build",
    ]
    plan_keywords = ["计划", "规划", "方案", "设计", "plan", "spec", "design"]

    if any(keyword in normalized for keyword in plan_phrase_keywords):
        return "plan"
    if any(keyword in normalized for keyword in change_keywords):
        return "change"
    if any(keyword in normalized for keyword in plan_keywords):
        return "plan"
    return "question"


def build_run_id(profile: str) -> str:
    return normalize_run_id(f"{profile}-{datetime.now().strftime('%Y%m%d-%H%M%S')}")


def create_workflow_state_v2(
    project_root: Path,
    run_id: str,
    intent: str,
    profile: str,
) -> dict[str, Any]:
    resolved_profile = classify_profile(intent) if profile == "auto" else profile
    if resolved_profile not in PROFILES:
        raise ValueError(f"Unsupported workflow profile: {profile}")

    now = utc_now()
    state = {
        "version": "workflow-state/v2",
        "runId": normalize_run_id(run_id),
        "projectRoot": str(project_root),
        "profile": resolved_profile,
        "intent": intent,
        "phase": "intent",
        "status": "initialized",
        "nextAction": {
            "kind": "inspect",
            "command": "workflow next",
            "reason": "Workflow state was initialized.",
        },
        "artifacts": [],
        "gates": [],
        "blockers": [],
        "startedAtUtc": now,
        "updatedAtUtc": now,
    }
    return apply_next_action(state)


def begin_or_resume_workflow(
    project_root: Path,
    intent: str,
    profile: str,
    run_id: str | None,
) -> dict[str, Any]:
    resolved_profile = classify_profile(intent) if profile == "auto" else profile
    resolved_run_id = normalize_run_id(run_id) if run_id else build_run_id(resolved_profile)
    path = workflow_state_path(project_root, resolved_run_id)
    if path.exists():
        return apply_next_action(ensure_workflow_state_v2(project_root, read_json(path), intent, resolved_profile))
    return create_workflow_state_v2(project_root, resolved_run_id, intent, resolved_profile)


def ensure_workflow_state_v2(
    project_root: Path,
    state: dict[str, Any],
    intent: str = "",
    profile: str = "change",
) -> dict[str, Any]:
    if state.get("version") == "workflow-state/v2":
        return apply_next_action(state)

    run_id = str(state.get("runId", build_run_id(profile)))
    migrated = create_workflow_state_v2(
        project_root,
        run_id,
        intent or str(state.get("intent", "")),
        profile,
    )
    migrated["status"] = str(state.get("status", migrated["status"]))
    migrated["artifacts"] = list(state.get("artifacts", []))
    migrated["gates"] = list(state.get("gates", []))
    migrated["blockers"] = list(state.get("blockers", []))
    return apply_next_action(migrated)


def apply_next_action(state: dict[str, Any]) -> dict[str, Any]:
    next_state = dict(state)
    next_state["nextAction"] = evaluate_next_action(next_state)
    next_state["phase"] = phase_for_action(next_state["nextAction"]["kind"])
    if next_state["nextAction"]["kind"] == "blocked" and next_state["status"] != "rejected":
        next_state["status"] = "blocked"
        next_state["blockers"] = [next_state["nextAction"]["reason"]]
    elif next_state["status"] not in {"completed", "rejected", "blocked", "approved"}:
        if next_state["nextAction"]["kind"] == "gate":
            next_state["status"] = "waiting_for_gate"
        elif next_state["nextAction"]["kind"] not in {"execute", "report"}:
            next_state["status"] = "running"
    next_state["updatedAtUtc"] = utc_now()
    return next_state


def evaluate_next_action(state: dict[str, Any]) -> dict[str, str]:
    if state.get("status") == "completed":
        return action("done", "none", "Workflow is already completed.")
    if state.get("status") == "rejected":
        return action("blocked", "revise request", "Workflow was rejected by a human gate.")
    if state.get("status") == "blocked":
        return action("blocked", "revise execution-plan", "Workflow is blocked and cannot be approved through a gate.")

    profile = state.get("profile")
    if profile == "question":
        return action("report", "workflow complete", "Question profile can report without execution.")

    blocker = artifact_validation_blocker(state)
    if blocker:
        return action("blocked", "revise artifact", blocker)

    for name, schema, kind, command in WORKFLOW_ARTIFACTS:
        if not has_artifact(state, name):
            return action(kind, command, f"{name} artifact is required before planning or execution.")

        if name == "requirement-check":
            requirement = requirement_check_payload(state)
            status = requirement.get("status")
            if status == "blocked":
                return action("blocked", "revise requirements", "Requirement check is blocked.")
            if status == "needs_clarification":
                return action("blocked", "clarify requirements", "Requirement check needs clarification.")

    if profile == "plan":
        return action("report", "workflow complete", "Plan profile can report after risk review.")

    if profile == "change":
        risk = risk_review_payload(state)
        if risk.get("overallRisk") == "blocked":
            return action("blocked", "revise execution-plan", "Blocked risk cannot proceed.")
        if risk.get("confirmationRequired") and gate_status(state, "risk-review") != "approved":
            return action("gate", "gate approve --gate risk-review", "Risk review requires human approval.")
        missing_preview = missing_preview_artifacts(state, risk)
        if missing_preview:
            return action(
                "gate",
                "produce dry-run-preview",
                f"Risk review requires preview evidence: {', '.join(missing_preview)}.",
            )
        return action("execute", "workflow preflight", "Execution preflight can pass for this change workflow.")

    return action("blocked", "revise workflow profile", f"Unsupported workflow profile: {profile}")


def phase_for_action(kind: str) -> str:
    return {
        "intent_analysis": "intent",
        "context": "context",
        "requirements": "requirements",
        "spec": "spec",
        "plan": "planning",
        "risk_review": "risk_review",
        "gate": "gate",
        "execute": "execute",
        "report": "report",
        "done": "completed",
        "blocked": "blocked",
    }.get(kind, "intent")


def action(kind: str, command: str, reason: str) -> dict[str, str]:
    return {"kind": kind, "command": command, "reason": reason}


def has_artifact(state: dict[str, Any], name: str) -> bool:
    return artifact_by_name(state, name) is not None


def artifact_by_name(state: dict[str, Any], name: str) -> dict[str, Any] | None:
    for artifact in state.get("artifacts", []):
        if artifact.get("name") == name:
            return artifact
    return None


def gate_status(state: dict[str, Any], name: str) -> str | None:
    for gate in state.get("gates", []):
        if gate.get("name") == name:
            return gate.get("status")
    return None


def risk_review_payload(state: dict[str, Any]) -> dict[str, Any]:
    artifact = artifact_by_name(state, "risk-review")
    if artifact is None:
        return {}
    path = Path(str(artifact["path"]))
    return read_json(path)


def requirement_check_payload(state: dict[str, Any]) -> dict[str, Any]:
    artifact = artifact_by_name(state, "requirement-check")
    if artifact is None:
        return {}
    return read_json(Path(str(artifact["path"])))


def artifact_validation_blocker(state: dict[str, Any]) -> str | None:
    project_root = Path(str(state.get("projectRoot", "")))
    workflow_run_id = str(state.get("runId", ""))
    for artifact in state.get("artifacts", []):
        name = str(artifact.get("name", ""))
        path = Path(str(artifact.get("path", "")))
        schema_id = str(artifact.get("schema", ""))
        validation_status = str(artifact.get("validationStatus", ""))
        if validation_status != "passed":
            return f"{name} artifact validation status is {validation_status}."
        if not path.exists():
            return f"{name} artifact path does not exist: {path}"
        try:
            payload = read_json(path)
            validate_payload(load_schema(project_root, schema_id), payload)
        except (FileNotFoundError, KeyError, SchemaValidationError, ValueError) as exc:
            return f"{name} artifact failed schema validation: {exc}"

        artifact_run_id = artifact.get("artifactRunId")
        payload_run_id = payload.get("runId") if isinstance(payload, dict) else None
        for candidate in (artifact_run_id, payload_run_id):
            if candidate and str(candidate) != workflow_run_id:
                return f"{name} artifact runId {candidate!r} does not match workflow runId {workflow_run_id!r}."
        if artifact_run_id and payload_run_id and str(artifact_run_id) != str(payload_run_id):
            return f"{name} artifact metadata runId does not match payload runId."
    return None


def missing_preview_artifacts(state: dict[str, Any], risk: dict[str, Any]) -> list[str]:
    if not risk.get("previewRequired"):
        return []
    required = [str(name) for name in risk.get("previewArtifacts", [])]
    return [name for name in required if not has_artifact(state, name)]


def preflight_execution(state: dict[str, Any]) -> dict[str, Any]:
    profile = state.get("profile")
    if profile in {"question", "plan"}:
        raise WorkflowPreflightError(f"{profile} workflow cannot execute modifications.")
    if profile != "change":
        raise WorkflowPreflightError(f"Unsupported workflow profile: {profile}")
    blocker = artifact_validation_blocker(state)
    if blocker:
        raise WorkflowPreflightError(blocker)
    for name, _schema, _kind, _command in WORKFLOW_ARTIFACTS:
        if not has_artifact(state, name):
            raise WorkflowPreflightError(f"Missing {name} artifact.")

    requirement = requirement_check_payload(state)
    if requirement.get("status") == "blocked":
        raise WorkflowPreflightError("Requirement check is blocked.")
    if requirement.get("status") == "needs_clarification":
        raise WorkflowPreflightError("Requirement check needs clarification.")
    risk = risk_review_payload(state)
    if risk.get("overallRisk") == "blocked" or state.get("status") == "blocked":
        raise WorkflowPreflightError("Workflow has blocked risk and cannot execute.")
    if risk.get("confirmationRequired") and gate_status(state, "risk-review") != "approved":
        raise WorkflowPreflightError("Risk review must be approved before execution.")
    missing_preview = missing_preview_artifacts(state, risk)
    if missing_preview:
        raise WorkflowPreflightError(f"Missing preview evidence artifact: {', '.join(missing_preview)}.")
    if state.get("status") == "rejected":
        raise WorkflowPreflightError("Workflow was rejected and cannot execute.")

    state = apply_next_action(state)
    if state["nextAction"]["kind"] != "execute":
        raise WorkflowPreflightError(state["nextAction"]["reason"])
    return {"status": "passed", "runId": state["runId"], "nextAction": state["nextAction"]}


def complete_workflow(
    project_root: Path,
    state: dict[str, Any],
    summary: str,
) -> dict[str, Any]:
    report_path = artifact_dir(project_root, state["runId"]) / "final-report.json"
    next_state = add_artifact(state, "final-report", report_path, "workflow complete", "final-report/v1")
    next_state["status"] = "completed"
    next_state["phase"] = "completed"
    next_state["nextAction"] = action("done", "none", "Workflow is completed.")
    next_state["updatedAtUtc"] = utc_now()
    return next_state
