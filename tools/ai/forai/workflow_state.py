from __future__ import annotations

from pathlib import Path
from typing import Any

from .artifacts import artifact_dir
from .json_io import read_json, write_json


def workflow_state_path(project_root: Path, run_id: str) -> Path:
    return artifact_dir(project_root, run_id) / "workflow-state.json"


def create_initial_state(project_root: Path, run_id: str) -> dict[str, Any]:
    return {
        "version": "workflow-state/v1",
        "runId": run_id,
        "projectRoot": str(project_root),
        "status": "initialized",
        "artifacts": [],
        "gates": [],
        "blockers": [],
    }


def load_workflow_state(project_root: Path, run_id: str) -> dict[str, Any]:
    return read_json(workflow_state_path(project_root, run_id))


def load_or_create_workflow_state(project_root: Path, run_id: str) -> dict[str, Any]:
    path = workflow_state_path(project_root, run_id)
    if path.exists():
        return read_json(path)
    return create_initial_state(project_root, run_id)


def save_workflow_state(project_root: Path, state: dict[str, Any]) -> Path:
    path = workflow_state_path(project_root, state["runId"])
    write_json(path, state)
    return path


def add_artifact(
    state: dict[str, Any],
    name: str,
    path: Path,
    producer: str,
    schema: str,
    validation_status: str = "passed",
    run_id: str | None = None,
) -> dict[str, Any]:
    next_state = dict(state)
    artifacts = [
        artifact
        for artifact in state.get("artifacts", [])
        if artifact.get("name") != name
    ]
    artifact = {
        "name": name,
        "path": str(path),
        "producer": producer,
        "schema": schema,
        "validationStatus": validation_status,
    }
    if run_id:
        artifact["artifactRunId"] = run_id
    artifacts.append(artifact)
    next_state["artifacts"] = artifacts
    return next_state


def set_gate(state: dict[str, Any], name: str, status: str, reason: str) -> dict[str, Any]:
    next_state = dict(state)
    gates = [
        gate
        for gate in state.get("gates", [])
        if gate.get("name") != name
    ]
    gates.append({"name": name, "status": status, "reason": reason})
    next_state["gates"] = gates

    blockers = list(state.get("blockers", []))
    if status == "approved":
        next_state["status"] = "approved"
    elif status == "rejected":
        next_state["status"] = "rejected"
        blockers = [f"Gate {name} rejected: {reason}"]
    elif status == "pending":
        next_state["status"] = "waiting_for_gate"
    else:
        raise ValueError(f"Unsupported gate status: {status}")

    next_state["blockers"] = blockers
    return next_state
