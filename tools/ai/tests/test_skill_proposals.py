from __future__ import annotations

from forai.skill_ledger import LedgerStore
from forai.skill_metrics import METRIC_EXECUTION_PLAN_UNBLOCKED
from forai.skill_models import (
    CandidateKeyword,
    HitRateMetric,
    MetricsReport,
    MetricsWindow,
    OptimizerConfig,
    Signal,
)
from forai.skill_proposals import ProposalGenerator


def signal(run_id: str, term: str = "roslyn-gateway") -> Signal:
    return Signal(
        run_id=run_id,
        harvested_at="2026-06-15T00:00:00Z",
        preflight_first_pass=False,
        risk_review_blocked=True,
        clarification_round_trips=0,
        candidate_keywords=[
            CandidateKeyword(term=term, category="capability_registry", context="test")
        ],
        profile="change",
    )


def low_metrics() -> MetricsReport:
    return MetricsReport(
        run_id="skill-opt-test",
        window=MetricsWindow(from_="2026-06-01", to="2026-06-15"),
        included_run_count=4,
        skipped_run_count=0,
        metrics=[
            HitRateMetric(
                id=METRIC_EXECUTION_PLAN_UNBLOCKED,
                numerator=0,
                denominator=4,
                value=0.0,
                status="ok",
                run_ids=["train-1", "train-2", "validation-1", "validation-2"],
            )
        ],
    )


def test_proposals_do_not_use_validation_ledger_signals(tmp_path):
    store = LedgerStore(project_root=tmp_path)
    store.append(
        [
            signal("train-1"),
            signal("train-2"),
            signal("validation-1"),
        ]
    )
    training_ledger = store.filtered_by_run_ids({"train-1", "train-2"})

    result = ProposalGenerator().generate(
        low_metrics(), training_ledger, OptimizerConfig.default()
    )

    keyword_proposals = [p for p in result.proposals if p.keyword_category is not None]
    assert keyword_proposals == []
    assert result.proposals
    assert all(p.evidence is None for p in result.proposals)


def test_proposals_use_keyword_after_three_training_occurrences(tmp_path):
    store = LedgerStore(project_root=tmp_path)
    store.append([signal("train-1"), signal("train-2"), signal("train-3")])
    training_ledger = store.filtered_by_run_ids({"train-1", "train-2", "train-3"})

    result = ProposalGenerator().generate(
        low_metrics(), training_ledger, OptimizerConfig.default()
    )

    keyword_proposals = [p for p in result.proposals if p.keyword_category is not None]
    assert len(keyword_proposals) == 1
    assert keyword_proposals[0].evidence is not None
    assert keyword_proposals[0].evidence.ledger_occurrences == 3
