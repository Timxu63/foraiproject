from __future__ import annotations

from forai.skill_ledger import LedgerStore
from forai.skill_models import (
    CandidateKeyword,
    OptimizerConfig,
    Signal,
)


def signal(run_id: str, *terms: str) -> Signal:
    return Signal(
        run_id=run_id,
        harvested_at="2026-06-15T00:00:00Z",
        preflight_first_pass=False,
        risk_review_blocked=True,
        clarification_round_trips=0,
        candidate_keywords=[
            CandidateKeyword(term=term, category="capability_registry", context="test")
            for term in terms
        ],
        profile="change",
    )


def test_default_keyword_threshold_requires_three_distinct_runs(tmp_path):
    config = OptimizerConfig.default()
    assert config.sample_threshold.min_keyword_occurrences == 3

    store = LedgerStore(project_root=tmp_path)
    store.append(
        [
            signal("run-1", "roslyn-gateway", "roslyn-gateway"),
            signal("run-2", "roslyn-gateway"),
        ]
    )

    progress = store.progress(config.sample_threshold)
    counts = store.candidate_keyword_counts()

    assert counts["roslyn-gateway"].occurrences == 2
    assert counts["roslyn-gateway"].run_ids == ["run-1", "run-2"]
    assert progress.has_recurring_keyword is False
    assert progress.threshold_met is False

    store.append([signal("run-3", "roslyn-gateway")])

    progress = store.progress(config.sample_threshold)
    counts = store.candidate_keyword_counts()

    assert counts["roslyn-gateway"].occurrences == 3
    assert counts["roslyn-gateway"].run_ids == ["run-1", "run-2", "run-3"]
    assert progress.has_recurring_keyword is True
    assert progress.threshold_met is True


def test_filtered_by_run_ids_returns_read_only_training_ledger_view(tmp_path):
    store = LedgerStore(project_root=tmp_path)
    store.append(
        [
            signal("train-1", "roslyn-gateway"),
            signal("train-2", "roslyn-gateway"),
            signal("validation-1", "roslyn-gateway"),
        ]
    )

    filtered = store.filtered_by_run_ids({"train-1", "train-2"})

    assert filtered is not store
    assert len(store.load().entries) == 3
    assert len(filtered.load().entries) == 2
    assert filtered.candidate_keyword_counts()["roslyn-gateway"].occurrences == 2
