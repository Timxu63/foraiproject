import json

import pytest

from forai.paths import find_project_root
from forai.schemas import SchemaValidationError, load_schema, validate_payload
from forai.workflow_engine import (
    WorkflowPreflightError,
    apply_next_action,
    classify_profile,
    create_workflow_state_v2,
    preflight_execution,
)
from forai.workflow_state import add_artifact, set_gate


def write_json(path, payload):
    path.write_text(json.dumps(payload), encoding="utf-8")


def context_payload(root):
    return {
        "version": "context-pack/v1",
        "projectRoot": str(root),
        "unityVersion": "2022.3.62f2",
        "packages": [],
        "paths": [],
        "summaries": [],
    }


def intent_payload():
    return {
        "version": "intent-analysis/v1",
        "goal": "Implement workflow",
        "domain": "tools",
        "requestedChanges": ["Extend workflow engine"],
        "constraints": [],
        "unknowns": [],
        "riskHints": [],
    }


def requirements_payload(status="ready"):
    return {
        "version": "requirement-check/v1",
        "status": status,
        "questions": [] if status == "ready" else ["Clarify requirement"],
        "defaults": [],
        "blockers": [] if status != "blocked" else ["Blocked requirement"],
    }


def spec_payload():
    return {
        "version": "domain-spec/v1",
        "goal": "Implement workflow",
        "objects": [],
        "acceptanceCriteria": ["Workflow validates artifacts"],
    }


def plan_payload(run_id, target="tools/ai"):
    return {
        "version": "execution-plan/v1",
        "runId": run_id,
        "steps": [
            {
                "id": "change-tools",
                "kind": "cli",
                "description": "Change workflow tools",
                "target": target,
                "command": "python tools/ai/ai.py plan validate",
                "inputs": {},
                "outputs": ["artifacts/ai-runs/{runId}/execution-plan.json"],
                "dryRunSupported": False,
                "validation": [{"name": "pytest", "command": "python -m pytest tools/ai/tests -q"}],
                "requiresConfirmation": False,
            }
        ],
    }


def risk_payload(run_id, overall="low", preview_required=False):
    return {
        "version": "risk-review/v1",
        "runId": run_id,
        "overallRisk": overall,
        "findings": [{"risk": overall, "message": f"{overall} risk"}],
        "confirmationRequired": overall in {"medium", "high", "blocked"},
        "gateReason": "High risk requires approval." if overall == "high" else "",
        "previewRequired": preview_required,
        "previewArtifacts": ["dry-run-preview"] if preview_required else [],
    }


def attach_required_artifacts(root, state, tmp_path, run_id, risk=None):
    payloads = {
        "intent-analysis": ("intent-analysis/v1", intent_payload()),
        "context-pack": ("context-pack/v1", context_payload(root)),
        "requirement-check": ("requirement-check/v1", requirements_payload()),
        "domain-spec": ("domain-spec/v1", spec_payload()),
        "execution-plan": ("execution-plan/v1", plan_payload(run_id)),
        "risk-review": ("risk-review/v1", risk or risk_payload(run_id)),
    }
    for name, (schema, payload) in payloads.items():
        path = tmp_path / f"{name}.json"
        write_json(path, payload)
        state = add_artifact(state, name, path, "pytest", schema, run_id=payload.get("runId"))
    return state


def test_auto_profile_classifies_common_intents():
    assert classify_profile("解释当前 workflow 是怎么工作的") == "question"
    assert classify_profile("规划一个新的 Unity 自动化流程") == "plan"
    assert classify_profile("实现 Workflow Engine v2") == "change"


def test_auto_profile_prefers_plan_for_design_execution_plan_intents():
    assert classify_profile("\u8bbe\u8ba1\u4e00\u4e2a\u65b0\u7684\u6267\u884c\u65b9\u6848") == "plan"
    assert classify_profile("\u89c4\u5212 workflow execution plan") == "plan"


def test_workflow_state_v2_matches_schema():
    root = find_project_root()
    state = create_workflow_state_v2(root, "v2-schema-test", "解释当前 workflow", "question")

    assert state["version"] == "workflow-state/v2"
    assert state["profile"] == "question"
    assert state["phase"] == "report"
    assert state["nextAction"]["kind"] == "report"
    validate_payload(load_schema(root, "workflow-state/v2"), state)


def test_workflow_state_v2_rejects_extra_field():
    root = find_project_root()
    state = create_workflow_state_v2(root, "v2-extra-field-test", "解释当前 workflow", "question")
    state["extra"] = True

    with pytest.raises(SchemaValidationError):
        validate_payload(load_schema(root, "workflow-state/v2"), state)


def test_change_preflight_requires_context_plan_and_risk_review():
    state = create_workflow_state_v2(find_project_root(), "v2-preflight-missing", "实现功能", "change")

    with pytest.raises(WorkflowPreflightError, match="intent-analysis"):
        preflight_execution(state)


def test_plan_profile_requires_intent_context_requirements_spec_plan_and_risk(tmp_path):
    root = find_project_root()
    state = create_workflow_state_v2(root, "v2-plan-sequence", "Plan workflow", "plan")
    assert state["nextAction"]["kind"] == "intent_analysis"

    intent = tmp_path / "intent-analysis.json"
    write_json(intent, intent_payload())
    state = add_artifact(state, "intent-analysis", intent, "pytest", "intent-analysis/v1")
    state = apply_next_action(state)
    assert state["nextAction"]["kind"] == "context"

    context = tmp_path / "context-pack.json"
    write_json(context, context_payload(root))
    state = add_artifact(state, "context-pack", context, "pytest", "context-pack/v1")
    state = apply_next_action(state)
    assert state["nextAction"]["kind"] == "requirements"

    requirements = tmp_path / "requirement-check.json"
    write_json(requirements, requirements_payload())
    state = add_artifact(state, "requirement-check", requirements, "pytest", "requirement-check/v1")
    state = apply_next_action(state)
    assert state["nextAction"]["kind"] == "spec"

    spec = tmp_path / "domain-spec.json"
    write_json(spec, spec_payload())
    state = add_artifact(state, "domain-spec", spec, "pytest", "domain-spec/v1")
    state = apply_next_action(state)
    assert state["nextAction"]["kind"] == "plan"

    plan = tmp_path / "execution-plan.json"
    write_json(plan, plan_payload("v2-plan-sequence"))
    state = add_artifact(
        state,
        "execution-plan",
        plan,
        "pytest",
        "execution-plan/v1",
        run_id="v2-plan-sequence",
    )
    state = apply_next_action(state)
    assert state["nextAction"]["kind"] == "risk_review"

    risk = tmp_path / "risk-review.json"
    write_json(risk, risk_payload("v2-plan-sequence"))
    state = add_artifact(state, "risk-review", risk, "pytest", "risk-review/v1", run_id="v2-plan-sequence")
    state = apply_next_action(state)
    assert state["nextAction"]["kind"] == "report"


def test_workflow_next_blocks_invalid_artifact_payload(tmp_path):
    root = find_project_root()
    invalid = tmp_path / "intent-analysis.json"
    write_json(invalid, {"version": "intent-analysis/v1"})
    state = create_workflow_state_v2(root, "v2-invalid-artifact", "Implement workflow", "change")
    state = add_artifact(state, "intent-analysis", invalid, "pytest", "intent-analysis/v1")

    state = apply_next_action(state)

    assert state["status"] == "blocked"
    assert state["nextAction"]["kind"] == "blocked"
    assert "intent-analysis" in state["nextAction"]["reason"]


def test_workflow_next_blocks_run_id_mismatch(tmp_path):
    root = find_project_root()
    plan = tmp_path / "execution-plan.json"
    write_json(plan, plan_payload("other-run"))
    state = create_workflow_state_v2(root, "v2-run-id-mismatch", "Implement workflow", "change")
    state = add_artifact(state, "execution-plan", plan, "pytest", "execution-plan/v1", run_id="other-run")

    state = apply_next_action(state)

    assert state["status"] == "blocked"
    assert "runId" in state["nextAction"]["reason"]


def test_question_and_plan_profiles_cannot_preflight_execution():
    root = find_project_root()
    question = create_workflow_state_v2(root, "v2-question-preflight", "解释当前 workflow", "question")
    plan = create_workflow_state_v2(root, "v2-plan-preflight", "规划一个新功能", "plan")

    with pytest.raises(WorkflowPreflightError, match="question"):
        preflight_execution(question)
    with pytest.raises(WorkflowPreflightError, match="plan"):
        preflight_execution(plan)


def test_change_preflight_requires_gate_for_confirmation_risk(tmp_path):
    root = find_project_root()
    run_id = "v2-preflight-gate"

    state = create_workflow_state_v2(root, run_id, "实现功能", "change")
    state = attach_required_artifacts(root, state, tmp_path, run_id, risk_payload(run_id, "medium"))
    state = apply_next_action(state)

    with pytest.raises(WorkflowPreflightError, match="approved"):
        preflight_execution(state)

    approved = set_gate(state, "risk-review", "approved", "pytest approval")
    approved = apply_next_action(approved)
    payload = preflight_execution(approved)
    assert payload["status"] == "passed"
    assert payload["nextAction"]["kind"] == "execute"


def test_change_preflight_blocks_blocked_risk(tmp_path):
    root = find_project_root()
    run_id = "v2-preflight-blocked"

    state = create_workflow_state_v2(root, run_id, "实现功能", "change")
    state = attach_required_artifacts(root, state, tmp_path, run_id, risk_payload(run_id, "blocked"))
    state = apply_next_action(state)

    with pytest.raises(WorkflowPreflightError, match="blocked"):
        preflight_execution(state)


def test_high_risk_preflight_requires_preview_evidence(tmp_path):
    root = find_project_root()
    run_id = "v2-preflight-preview"
    state = create_workflow_state_v2(root, run_id, "Implement high risk workflow", "change")
    state = attach_required_artifacts(root, state, tmp_path, run_id, risk_payload(run_id, "high", True))
    state = set_gate(state, "risk-review", "approved", "pytest approval")
    state = apply_next_action(state)

    with pytest.raises(WorkflowPreflightError, match="dry-run-preview"):
        preflight_execution(state)

    preview = tmp_path / "dry-run-preview.json"
    write_json(
        preview,
        {
            "version": "validation-report/v1",
            "runId": run_id,
            "status": "passed",
            "checks": [{"name": "dry-run-preview", "status": "passed", "evidence": "preview ok"}],
        },
    )
    state = add_artifact(state, "dry-run-preview", preview, "pytest", "validation-report/v1", run_id=run_id)
    state = apply_next_action(state)

    payload = preflight_execution(state)
    assert payload["status"] == "passed"
