import json
import os
import subprocess
import sys
import uuid
from pathlib import Path

from forai.paths import find_project_root


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    root = find_project_root()
    env = os.environ.copy()
    env["PYTHONPATH"] = str(root / "tools" / "ai")
    return subprocess.run(
        [sys.executable, str(root / "tools" / "ai" / "ai.py"), *args],
        cwd=str(root),
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def parse_stdout(completed: subprocess.CompletedProcess[str]) -> dict:
    assert completed.stdout.strip(), completed.stderr
    return json.loads(completed.stdout)


def intent_payload() -> dict:
    return {
        "version": "intent-analysis/v1",
        "goal": "Implement workflow",
        "domain": "tools",
        "requestedChanges": ["Extend workflow engine"],
        "constraints": [],
        "unknowns": [],
        "riskHints": [],
    }


def requirement_payload(status: str = "ready") -> dict:
    return {
        "version": "requirement-check/v1",
        "status": status,
        "questions": [] if status == "ready" else ["Clarify requirement"],
        "defaults": [],
        "blockers": [] if status != "blocked" else ["Blocked requirement"],
    }


def spec_payload() -> dict:
    return {
        "version": "domain-spec/v1",
        "goal": "Implement workflow",
        "objects": [],
        "acceptanceCriteria": ["Workflow validates artifacts"],
    }


def extended_plan_payload(run_id: str, kind: str = "cli", target: str = "tools/ai") -> dict:
    return {
        "version": "execution-plan/v1",
        "runId": run_id,
        "steps": [
            {
                "id": "step-1",
                "kind": kind,
                "description": "Run deterministic work",
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


def write_json(path: Path, payload: dict) -> Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def attach_artifact(root: Path, run_id: str, name: str, schema: str, path: Path) -> dict:
    completed = run_cli(
        "workflow",
        "attach-artifact",
        "--run-id",
        run_id,
        "--name",
        name,
        "--schema",
        schema,
        "--input",
        str(path),
        "--project-root",
        str(root),
    )
    assert completed.returncode == 0, completed.stderr
    return parse_stdout(completed)


def test_root_command_prints_project_root():
    root = find_project_root()
    completed = run_cli("root")
    assert completed.returncode == 0, completed.stderr
    assert parse_stdout(completed)["projectRoot"] == str(root)


def test_workflow_init_status_and_gate_commands():
    root = find_project_root()
    run_id = "pytest-cli-workflow"

    init = run_cli("workflow", "init", "--run-id", run_id, "--project-root", str(root))
    assert init.returncode == 0, init.stderr
    assert parse_stdout(init)["status"] == "initialized"

    approve = run_cli(
        "gate",
        "approve",
        "--run-id",
        run_id,
        "--gate",
        "risk-review",
        "--reason",
        "pytest approval",
        "--project-root",
        str(root),
    )
    assert approve.returncode == 0, approve.stderr
    approve_payload = parse_stdout(approve)
    assert approve_payload["status"] == "approved"
    assert approve_payload["gates"][0]["status"] == "approved"

    reject = run_cli(
        "gate",
        "reject",
        "--run-id",
        run_id,
        "--gate",
        "risk-review",
        "--reason",
        "pytest rejection",
        "--project-root",
        str(root),
    )
    assert reject.returncode == 0, reject.stderr
    reject_payload = parse_stdout(reject)
    assert reject_payload["status"] == "rejected"
    assert reject_payload["blockers"] == ["Gate risk-review rejected: pytest rejection"]

    status = run_cli("workflow", "status", "--run-id", run_id, "--project-root", str(root))
    assert status.returncode == 0, status.stderr
    assert parse_stdout(status)["status"] == "rejected"


def test_validate_file_reports_schema_error(tmp_path: Path):
    root = find_project_root()
    invalid = tmp_path / "invalid-context-pack.json"
    invalid.write_text(
        json.dumps(
            {
                "version": "context-pack/v1",
                "projectRoot": str(root),
                "unityVersion": "2022.3.62f2",
                "packages": [],
                "paths": [],
                "summaries": [],
                "extra": True,
            }
        ),
        encoding="utf-8",
    )

    completed = run_cli(
        "validate",
        "file",
        "--schema",
        "context-pack/v1",
        "--input",
        str(invalid),
        "--project-root",
        str(root),
    )
    assert completed.returncode == 1
    payload = parse_stdout(completed)
    assert payload["status"] == "failed"
    assert "extra" in payload["error"]


def test_workflow_attach_artifact_validates_schema_and_records_run_id(tmp_path: Path):
    root = find_project_root()
    run_id = f"pytest-attach-{uuid.uuid4().hex}"

    begin = run_cli(
        "workflow",
        "begin",
        "--profile",
        "change",
        "--intent",
        "Implement workflow",
        "--run-id",
        run_id,
        "--project-root",
        str(root),
    )
    assert begin.returncode == 0, begin.stderr

    plan_path = write_json(tmp_path / "execution-plan.json", extended_plan_payload(run_id))
    state = attach_artifact(root, run_id, "execution-plan", "execution-plan/v1", plan_path)

    artifact = next(item for item in state["artifacts"] if item["name"] == "execution-plan")
    assert artifact["artifactRunId"] == run_id
    assert artifact["validationStatus"] == "passed"


def test_workflow_attach_artifact_rejects_run_id_mismatch(tmp_path: Path):
    root = find_project_root()
    run_id = f"pytest-attach-mismatch-{uuid.uuid4().hex}"
    begin = run_cli(
        "workflow",
        "begin",
        "--profile",
        "change",
        "--intent",
        "Implement workflow",
        "--run-id",
        run_id,
        "--project-root",
        str(root),
    )
    assert begin.returncode == 0, begin.stderr

    plan_path = write_json(tmp_path / "execution-plan.json", extended_plan_payload("other-run"))
    completed = run_cli(
        "workflow",
        "attach-artifact",
        "--run-id",
        run_id,
        "--name",
        "execution-plan",
        "--schema",
        "execution-plan/v1",
        "--input",
        str(plan_path),
        "--project-root",
        str(root),
    )

    assert completed.returncode == 1
    payload = parse_stdout(completed)
    assert payload["status"] == "failed"
    assert "runId" in payload["error"]


def test_requirements_spec_and_plan_validate_commands(tmp_path: Path):
    root = find_project_root()
    requirements = write_json(tmp_path / "requirement-check.json", requirement_payload())
    spec = write_json(tmp_path / "domain-spec.json", spec_payload())
    plan = write_json(tmp_path / "execution-plan.json", extended_plan_payload("validate-run"))

    requirements_result = run_cli(
        "requirements",
        "check",
        "--input",
        str(requirements),
        "--project-root",
        str(root),
    )
    assert requirements_result.returncode == 0, requirements_result.stderr
    assert parse_stdout(requirements_result)["status"] == "ready"

    spec_result = run_cli("spec", "validate", "--input", str(spec), "--project-root", str(root))
    assert spec_result.returncode == 0, spec_result.stderr
    assert parse_stdout(spec_result)["status"] == "passed"

    plan_result = run_cli("plan", "validate", "--input", str(plan), "--project-root", str(root))
    assert plan_result.returncode == 0, plan_result.stderr
    assert parse_stdout(plan_result)["status"] == "passed"


def test_risk_review_uses_workflow_run_id_when_provided(tmp_path: Path):
    root = find_project_root()
    plan = tmp_path / "execution-plan.json"
    plan.write_text(
        json.dumps(
            {
                "version": "execution-plan/v1",
                "runId": "plan-run-id",
                "steps": [
                    {
                        "id": "read-docs",
                        "kind": "read_only",
                        "description": "Read docs",
                        "target": "docs/ai/workflows.md",
                        "command": "",
                        "inputs": {},
                        "outputs": [],
                        "dryRunSupported": True,
                        "validation": [],
                        "requiresConfirmation": False,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    completed = run_cli(
        "risk",
        "review",
        "--run-id",
        "workflow-run-id",
        "--plan",
        str(plan),
        "--project-root",
        str(root),
    )

    assert completed.returncode == 0, completed.stderr
    assert parse_stdout(completed)["runId"] == "workflow-run-id"


def test_gate_approve_cannot_override_blocked_risk(tmp_path: Path):
    root = find_project_root()
    run_id = "pytest-blocked-risk-gate"
    plan = tmp_path / "blocked-plan.json"
    plan.write_text(
        json.dumps(
            {
                "version": "execution-plan/v1",
                "runId": "blocked-plan",
                "steps": [
                    {
                        "id": "escape-workspace",
                        "kind": "cli",
                        "description": "Write outside workspace",
                        "target": "../outside.txt",
                        "command": "write outside",
                        "inputs": {},
                        "outputs": [],
                        "dryRunSupported": False,
                        "validation": [],
                        "requiresConfirmation": False,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    review = run_cli(
        "risk",
        "review",
        "--run-id",
        run_id,
        "--plan",
        str(plan),
        "--project-root",
        str(root),
    )
    assert review.returncode == 0, review.stderr
    assert parse_stdout(review)["overallRisk"] == "blocked"

    approve = run_cli(
        "gate",
        "approve",
        "--run-id",
        run_id,
        "--gate",
        "risk-review",
        "--reason",
        "should not pass",
        "--project-root",
        str(root),
    )
    assert approve.returncode == 1
    approve_payload = parse_stdout(approve)
    assert approve_payload["status"] == "failed"
    assert "blocked" in approve_payload["error"]

    status = run_cli("workflow", "status", "--run-id", run_id, "--project-root", str(root))
    assert status.returncode == 0, status.stderr
    assert parse_stdout(status)["status"] == "blocked"


def test_workflow_begin_next_and_complete_commands():
    root = find_project_root()
    run_id = f"pytest-v2-question-{uuid.uuid4().hex}"

    begin = run_cli(
        "workflow",
        "begin",
        "--profile",
        "question",
        "--intent",
        "解释当前 workflow",
        "--run-id",
        run_id,
        "--project-root",
        str(root),
    )
    assert begin.returncode == 0, begin.stderr
    begin_payload = parse_stdout(begin)
    assert begin_payload["version"] == "workflow-state/v2"
    assert begin_payload["profile"] == "question"
    assert begin_payload["nextAction"]["kind"] == "report"

    next_result = run_cli("workflow", "next", "--run-id", run_id, "--project-root", str(root))
    assert next_result.returncode == 0, next_result.stderr
    assert parse_stdout(next_result)["nextAction"]["kind"] == "report"

    complete = run_cli(
        "workflow",
        "complete",
        "--run-id",
        run_id,
        "--summary",
        "pytest summary",
        "--project-root",
        str(root),
    )
    assert complete.returncode == 0, complete.stderr
    complete_payload = parse_stdout(complete)
    assert complete_payload["status"] == "completed"
    assert complete_payload["phase"] == "completed"


def test_change_workflow_preflight_requires_gate_then_passes(tmp_path: Path):
    root = find_project_root()
    run_id = f"pytest-v2-change-gate-{uuid.uuid4().hex}"
    plan = tmp_path / "medium-plan.json"
    write_json(
        plan,
        extended_plan_payload(
            run_id,
            kind="unity_adapter",
            target="Assets/_Project/ScriptableObjects/Item.asset",
        ),
    )

    begin = run_cli(
        "workflow",
        "begin",
        "--profile",
        "change",
        "--intent",
        "实现一个 Unity 资产创建功能",
        "--run-id",
        run_id,
        "--project-root",
        str(root),
    )
    assert begin.returncode == 0, begin.stderr

    missing = run_cli("workflow", "preflight", "--run-id", run_id, "--project-root", str(root))
    assert missing.returncode == 1
    assert "intent-analysis" in parse_stdout(missing)["error"]

    attach_artifact(
        root,
        run_id,
        "intent-analysis",
        "intent-analysis/v1",
        write_json(tmp_path / "intent-analysis.json", intent_payload()),
    )

    context = run_cli("scan", "context", "--run-id", run_id, "--project-root", str(root))
    assert context.returncode == 0, context.stderr

    attach_artifact(
        root,
        run_id,
        "requirement-check",
        "requirement-check/v1",
        write_json(tmp_path / "requirement-check.json", requirement_payload()),
    )
    attach_artifact(
        root,
        run_id,
        "domain-spec",
        "domain-spec/v1",
        write_json(tmp_path / "domain-spec.json", spec_payload()),
    )

    review = run_cli(
        "risk",
        "review",
        "--run-id",
        run_id,
        "--plan",
        str(plan),
        "--project-root",
        str(root),
    )
    assert review.returncode == 0, review.stderr
    assert parse_stdout(review)["overallRisk"] == "medium"

    gated = run_cli("workflow", "preflight", "--run-id", run_id, "--project-root", str(root))
    assert gated.returncode == 1
    assert "approved" in parse_stdout(gated)["error"]

    approve = run_cli(
        "gate",
        "approve",
        "--run-id",
        run_id,
        "--gate",
        "risk-review",
        "--reason",
        "pytest approval",
        "--project-root",
        str(root),
    )
    assert approve.returncode == 0, approve.stderr

    passed = run_cli("workflow", "preflight", "--run-id", run_id, "--project-root", str(root))
    assert passed.returncode == 0, passed.stderr
    passed_payload = parse_stdout(passed)
    assert passed_payload["status"] == "passed"
    assert passed_payload["nextAction"]["kind"] == "execute"
