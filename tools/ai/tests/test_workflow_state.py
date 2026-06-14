from forai.paths import find_project_root
from forai.schemas import load_schema, validate_payload
from forai.workflow_state import create_initial_state, set_gate


def test_create_initial_state_matches_schema():
    root = find_project_root()
    state = create_initial_state(root, "workflow-state-test")
    assert state["version"] == "workflow-state/v1"
    assert state["runId"] == "workflow-state-test"
    assert state["status"] == "initialized"
    validate_payload(load_schema(root, "workflow-state/v1"), state)


def test_set_gate_approve_updates_existing_gate():
    root = find_project_root()
    state = create_initial_state(root, "workflow-gate-test")
    state = set_gate(state, "risk-review", "pending", "waiting for human review")
    state = set_gate(state, "risk-review", "approved", "approved in pytest")
    assert state["status"] == "approved"
    assert len(state["gates"]) == 1
    assert state["gates"][0]["name"] == "risk-review"
    assert state["gates"][0]["status"] == "approved"
    assert state["gates"][0]["reason"] == "approved in pytest"
    validate_payload(load_schema(root, "workflow-state/v1"), state)


def test_set_gate_reject_blocks_execution():
    state = create_initial_state(find_project_root(), "workflow-reject-test")
    state = set_gate(state, "risk-review", "rejected", "human rejected")
    assert state["status"] == "rejected"
    assert state["blockers"] == ["Gate risk-review rejected: human rejected"]
