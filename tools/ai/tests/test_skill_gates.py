from __future__ import annotations

from pathlib import Path

from forai.skill_gates import GateOutcome, decide, pytest_gate, schema_gate, unity_compile_gate
from forai.skill_models import Edit, EditProposal, GateResult, ProposalEvaluation


def proposal(target_path: str = "docs/ai/capability-registry.md") -> EditProposal:
    return EditProposal(
        proposal_id="prop-0001",
        target_path=target_path,
        is_maintained_file=True,
        edits=[
            Edit(
                type="add",
                anchor="## 能力关键词",
                new_text="- roslyn-gateway",
                changed_lines=1,
            )
        ],
        total_changed_lines=1,
        target_metric="execution_plan_unblocked_rate",
        rationale="test proposal",
        status="skipped",
    )


def improved() -> ProposalEvaluation:
    return ProposalEvaluation(
        validation_delta_before=0.0,
        validation_delta_after=0.1,
        strictly_improved=True,
    )


def test_noop_gates_report_not_applicable_without_rejecting(tmp_path: Path):
    gate_results = [
        schema_gate(proposal(), tmp_path),
        pytest_gate(proposal(), tmp_path),
        unity_compile_gate(proposal(), tmp_path),
    ]

    assert [result.status for result in gate_results] == [
        "not_applicable",
        "not_applicable",
        "not_applicable",
    ]
    assert all(result.passed for result in gate_results)

    decided = decide(proposal(), improved(), GateOutcome(gate_results, passed=True))

    assert decided.status == "accepted"
    assert decided.gate_results is not None
    assert all(result.status == "not_applicable" for result in decided.gate_results)


def test_failed_gate_reports_failed_status_and_rejects():
    failed_gate = GateResult(gate="schema", passed=False, status="failed", output="bad")

    decided = decide(proposal(), improved(), GateOutcome([failed_gate], passed=False))

    assert decided.status == "rejected"
    assert decided.gate_results == [failed_gate]
