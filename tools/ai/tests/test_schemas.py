import pytest

from forai.paths import find_project_root
from forai.scanner import scan_context_pack
from forai.schemas import SchemaValidationError, load_schema, validate_payload


def test_validate_context_pack_accepts_valid_payload():
    root = find_project_root()
    schema = load_schema(root, "context-pack/v1")
    payload = {
        "version": "context-pack/v1",
        "projectRoot": str(root),
        "unityVersion": "2022.3.62f2",
        "packages": [{"name": "com.unity.test-framework", "version": "1.1.33"}],
        "paths": ["ProjectSettings/ProjectVersion.txt"],
        "summaries": [{"source": "ProjectSettings", "summary": "Unity version file present"}],
    }
    validate_payload(schema, payload)


def test_validate_context_pack_rejects_extra_property():
    root = find_project_root()
    schema = load_schema(root, "context-pack/v1")
    payload = {
        "version": "context-pack/v1",
        "projectRoot": str(root),
        "unityVersion": "2022.3.62f2",
        "packages": [],
        "paths": [],
        "summaries": [],
        "extra": True,
    }
    with pytest.raises(SchemaValidationError):
        validate_payload(schema, payload)


def test_context_scan_includes_current_ai_tooling_paths():
    root = find_project_root()
    payload = scan_context_pack(root)
    paths = set(payload["paths"])

    assert "tools/ai/schemas/workflow-state.v2.schema.json" in paths
    assert "tools/ai/forai/scanner.py" in paths
    assert "tools/ai/tests/test_workflow_engine.py" in paths


def test_validate_workflow_state_accepts_initial_state():
    root = find_project_root()
    schema = load_schema(root, "workflow-state/v1")
    payload = {
        "version": "workflow-state/v1",
        "runId": "schema-workflow",
        "projectRoot": str(root),
        "status": "initialized",
        "artifacts": [],
        "gates": [],
        "blockers": [],
    }
    validate_payload(schema, payload)


def test_validate_workflow_state_v2_accepts_initial_state():
    root = find_project_root()
    schema = load_schema(root, "workflow-state/v2")
    payload = {
        "version": "workflow-state/v2",
        "runId": "schema-workflow-v2",
        "projectRoot": str(root),
        "profile": "question",
        "intent": "解释当前 workflow",
        "phase": "report",
        "status": "initialized",
        "nextAction": {
            "kind": "report",
            "command": "workflow complete",
            "reason": "Question profile can report without execution.",
        },
        "artifacts": [],
        "gates": [],
        "blockers": [],
        "startedAtUtc": "2026-06-13T00:00:00Z",
        "updatedAtUtc": "2026-06-13T00:00:00Z",
    }
    validate_payload(schema, payload)


def test_validate_extended_execution_plan_accepts_operational_fields():
    root = find_project_root()
    schema = load_schema(root, "execution-plan/v1")
    payload = {
        "version": "execution-plan/v1",
        "runId": "extended-plan",
        "steps": [
            {
                "id": "validate-plan",
                "kind": "cli",
                "description": "Validate execution plan",
                "target": "tools/ai",
                "command": "python tools/ai/ai.py plan validate",
                "inputs": {"schema": "execution-plan/v1"},
                "outputs": ["artifacts/ai-runs/extended-plan/execution-plan.json"],
                "dryRunSupported": False,
                "validation": [
                    {
                        "name": "pytest",
                        "command": "python -m pytest tools/ai/tests -q",
                    }
                ],
                "requiresConfirmation": False,
            }
        ],
    }
    validate_payload(schema, payload)


def test_validate_risk_review_accepts_preview_contract_fields():
    root = find_project_root()
    schema = load_schema(root, "risk-review/v1")
    payload = {
        "version": "risk-review/v1",
        "runId": "preview-risk",
        "overallRisk": "high",
        "findings": [{"risk": "high", "message": "ProjectSettings changes are high risk."}],
        "confirmationRequired": True,
        "gateReason": "High risk requires explicit approval.",
        "previewRequired": True,
        "previewArtifacts": ["dry-run-preview"],
    }
    validate_payload(schema, payload)
