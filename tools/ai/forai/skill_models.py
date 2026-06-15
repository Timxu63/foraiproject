"""local-skill-optimization 数据模型。

本模块定义闭环各产物（Signal、Signal_Ledger、Metrics_Report、Edit_Proposal、
OptimizerConfig、Adoption_Stage、proposal-decisions）的可序列化 dataclass。

约定：
- 所有 dataclass 提供 ``to_dict()`` 返回 schema 形状的 dict（含 ``version`` 字段），
  以及 classmethod ``from_dict(data)`` 重建对象。
- round-trip 不变量成立：``from_dict(to_dict(x)) == x``（dataclass 自动 ``__eq__``）。
- 字段名与 ``tools/ai/schemas/skill-*.v1.schema.json`` 完全对齐。
- IO 复用 ``forai/json_io.py``，校验复用 ``forai/schemas.py``。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .json_io import read_json, write_json
from .schemas import load_schema, validate_payload


def _opt(target: dict[str, Any], key: str, value: Any) -> None:
    """仅当 value 不为 None 时写入 target[key]，以保持 round-trip 一致。"""
    if value is not None:
        target[key] = value


# ---------------------------------------------------------------------------
# Signal / Signal_Ledger
# ---------------------------------------------------------------------------


@dataclass
class CandidateKeyword:
    """Harvest 中观察到的候选关键词，类别保持中立。"""

    term: str
    category: str  # steering_match | capability_registry | intent_classification
    context: str | None = None

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {"term": self.term, "category": self.category}
        _opt(data, "context", self.context)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CandidateKeyword:
        return cls(
            term=data["term"],
            category=data["category"],
            context=data.get("context"),
        )


@dataclass
class SkippedSignal:
    """因缺失/非法 JSON 而被跳过的信号及原因。"""

    signal: str
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {"signal": self.signal, "reason": self.reason}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SkippedSignal:
        return cls(signal=data["signal"], reason=data["reason"])


@dataclass
class Signal:
    """从单条 Run_History 中确定性提取的原始证据条目。"""

    SCHEMA_ID = "skill-signal/v1"

    run_id: str
    harvested_at: str
    preflight_first_pass: bool
    risk_review_blocked: bool
    clarification_round_trips: int
    candidate_keywords: list[CandidateKeyword] = field(default_factory=list)
    skipped: list[SkippedSignal] = field(default_factory=list)
    profile: str | None = None
    version: str = "skill-signal/v1"

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {"version": self.version, "runId": self.run_id}
        _opt(data, "profile", self.profile)
        data["harvestedAt"] = self.harvested_at
        data["preflightFirstPass"] = self.preflight_first_pass
        data["riskReviewBlocked"] = self.risk_review_blocked
        data["clarificationRoundTrips"] = self.clarification_round_trips
        data["candidateKeywords"] = [kw.to_dict() for kw in self.candidate_keywords]
        data["skipped"] = [item.to_dict() for item in self.skipped]
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Signal:
        return cls(
            version=data.get("version", "skill-signal/v1"),
            run_id=data["runId"],
            harvested_at=data["harvestedAt"],
            profile=data.get("profile"),
            preflight_first_pass=data["preflightFirstPass"],
            risk_review_blocked=data["riskReviewBlocked"],
            clarification_round_trips=data["clarificationRoundTrips"],
            candidate_keywords=[
                CandidateKeyword.from_dict(item)
                for item in data.get("candidateKeywords", [])
            ],
            skipped=[SkippedSignal.from_dict(item) for item in data.get("skipped", [])],
        )


@dataclass
class KeywordCount:
    """Signal_Ledger 聚合中的单个候选关键词跨历史复现统计。"""

    category: str
    occurrences: int
    run_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "category": self.category,
            "occurrences": self.occurrences,
            "runIds": list(self.run_ids),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> KeywordCount:
        return cls(
            category=data["category"],
            occurrences=data["occurrences"],
            run_ids=list(data.get("runIds", [])),
        )


@dataclass
class LedgerAggregate:
    """Signal_Ledger 的聚合统计。"""

    total_runs: int = 0
    keyword_counts: dict[str, KeywordCount] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "totalRuns": self.total_runs,
            "keywordCounts": {
                term: count.to_dict() for term, count in self.keyword_counts.items()
            },
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LedgerAggregate:
        return cls(
            total_runs=data.get("totalRuns", 0),
            keyword_counts={
                term: KeywordCount.from_dict(value)
                for term, value in data.get("keywordCounts", {}).items()
            },
        )


@dataclass
class SignalLedger:
    """append-only 的累积账本（可序列化模型）。"""

    SCHEMA_ID = "skill-ledger/v1"

    entries: list[Signal] = field(default_factory=list)
    aggregate: LedgerAggregate = field(default_factory=LedgerAggregate)
    version: str = "skill-ledger/v1"

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "entries": [entry.to_dict() for entry in self.entries],
            "aggregate": self.aggregate.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SignalLedger:
        return cls(
            version=data.get("version", "skill-ledger/v1"),
            entries=[Signal.from_dict(item) for item in data.get("entries", [])],
            aggregate=LedgerAggregate.from_dict(data.get("aggregate", {})),
        )


# ---------------------------------------------------------------------------
# Hit_Rate_Metric / Metrics_Report
# ---------------------------------------------------------------------------


@dataclass
class HitRateMetric:
    """单个命中率指标。

    ``value`` 与 ``delta_from_previous`` 可为 None：
    - ``value`` 为 None 表示 ``status == "not_applicable"``（分母为 0）。
    - ``delta_from_previous`` 为 None 表示无上一次运行可对比。
    """

    id: str
    numerator: int
    denominator: int
    value: float | None
    status: str  # ok | not_applicable
    run_ids: list[str] = field(default_factory=list)
    delta_from_previous: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "numerator": self.numerator,
            "denominator": self.denominator,
            "value": self.value,
            "status": self.status,
            "runIds": list(self.run_ids),
            "deltaFromPrevious": self.delta_from_previous,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> HitRateMetric:
        return cls(
            id=data["id"],
            numerator=data["numerator"],
            denominator=data["denominator"],
            value=data.get("value"),
            status=data["status"],
            run_ids=list(data.get("runIds", [])),
            delta_from_previous=data.get("deltaFromPrevious"),
        )


@dataclass
class MetricsWindow:
    """指标计算的时间窗口。"""

    from_: str
    to: str

    def to_dict(self) -> dict[str, Any]:
        return {"from": self.from_, "to": self.to}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MetricsWindow:
        return cls(from_=data["from"], to=data["to"])


@dataclass
class MetricsReport:
    """聚合所有 Hit_Rate_Metric 的机器可读报告。"""

    SCHEMA_ID = "skill-metrics/v1"

    run_id: str
    window: MetricsWindow
    included_run_count: int
    skipped_run_count: int
    metrics: list[HitRateMetric] = field(default_factory=list)
    version: str = "skill-metrics/v1"

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "runId": self.run_id,
            "window": self.window.to_dict(),
            "includedRunCount": self.included_run_count,
            "skippedRunCount": self.skipped_run_count,
            "metrics": [metric.to_dict() for metric in self.metrics],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MetricsReport:
        return cls(
            version=data.get("version", "skill-metrics/v1"),
            run_id=data["runId"],
            window=MetricsWindow.from_dict(data["window"]),
            included_run_count=data["includedRunCount"],
            skipped_run_count=data["skippedRunCount"],
            metrics=[HitRateMetric.from_dict(item) for item in data.get("metrics", [])],
        )


# ---------------------------------------------------------------------------
# Edit / Edit_Proposal
# ---------------------------------------------------------------------------


@dataclass
class Edit:
    """单次有界编辑。"""

    type: str  # add | delete | replace
    anchor: str
    new_text: str
    changed_lines: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "anchor": self.anchor,
            "newText": self.new_text,
            "changedLines": self.changed_lines,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Edit:
        return cls(
            type=data["type"],
            anchor=data["anchor"],
            new_text=data["newText"],
            changed_lines=data["changedLines"],
        )


@dataclass
class ProposalEvidence:
    """提案的 ledger 证据。"""

    ledger_occurrences: int
    threshold_met: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "ledgerOccurrences": self.ledger_occurrences,
            "thresholdMet": self.threshold_met,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ProposalEvidence:
        return cls(
            ledger_occurrences=data["ledgerOccurrences"],
            threshold_met=data["thresholdMet"],
        )


@dataclass
class ProposalEvaluation:
    """留出集评估结论。"""

    validation_delta_before: float
    validation_delta_after: float
    strictly_improved: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "validationDeltaBefore": self.validation_delta_before,
            "validationDeltaAfter": self.validation_delta_after,
            "strictlyImproved": self.strictly_improved,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ProposalEvaluation:
        return cls(
            validation_delta_before=data["validationDeltaBefore"],
            validation_delta_after=data["validationDeltaAfter"],
            strictly_improved=data["strictlyImproved"],
        )


@dataclass
class GateResult:
    """单个 Deterministic_Gate 的结果。"""

    gate: str
    passed: bool
    status: str | None = None  # passed | failed | not_applicable
    security_check: bool | None = None
    output: str | None = None

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {"gate": self.gate, "passed": self.passed}
        _opt(data, "status", self.status)
        _opt(data, "securityCheck", self.security_check)
        _opt(data, "output", self.output)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GateResult:
        return cls(
            gate=data["gate"],
            passed=data["passed"],
            status=data.get("status"),
            security_check=data.get("securityCheck"),
            output=data.get("output"),
        )


@dataclass
class EditProposal:
    """针对单个 Maintained_File 的一组有界编辑提案。"""

    SCHEMA_ID = "skill-proposal/v1"

    proposal_id: str
    target_path: str
    is_maintained_file: bool
    edits: list[Edit]
    total_changed_lines: int
    target_metric: str
    rationale: str
    status: str  # accepted | rejected | skipped
    keyword_category: str | None = None
    evidence: ProposalEvidence | None = None
    evaluation: ProposalEvaluation | None = None
    gate_results: list[GateResult] | None = None
    version: str = "skill-proposal/v1"

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "version": self.version,
            "proposalId": self.proposal_id,
            "targetPath": self.target_path,
            "isMaintainedFile": self.is_maintained_file,
            "edits": [edit.to_dict() for edit in self.edits],
            "totalChangedLines": self.total_changed_lines,
        }
        _opt(data, "keywordCategory", self.keyword_category)
        data["targetMetric"] = self.target_metric
        data["rationale"] = self.rationale
        if self.evidence is not None:
            data["evidence"] = self.evidence.to_dict()
        if self.evaluation is not None:
            data["evaluation"] = self.evaluation.to_dict()
        if self.gate_results is not None:
            data["gateResults"] = [result.to_dict() for result in self.gate_results]
        data["status"] = self.status
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EditProposal:
        evidence = data.get("evidence")
        evaluation = data.get("evaluation")
        gate_results = data.get("gateResults")
        return cls(
            version=data.get("version", "skill-proposal/v1"),
            proposal_id=data["proposalId"],
            target_path=data["targetPath"],
            is_maintained_file=data["isMaintainedFile"],
            edits=[Edit.from_dict(item) for item in data.get("edits", [])],
            total_changed_lines=data["totalChangedLines"],
            keyword_category=data.get("keywordCategory"),
            target_metric=data["targetMetric"],
            rationale=data["rationale"],
            evidence=ProposalEvidence.from_dict(evidence) if evidence is not None else None,
            evaluation=ProposalEvaluation.from_dict(evaluation)
            if evaluation is not None
            else None,
            gate_results=[GateResult.from_dict(item) for item in gate_results]
            if gate_results is not None
            else None,
            status=data["status"],
        )


# ---------------------------------------------------------------------------
# OptimizerConfig / Sample_Threshold
# ---------------------------------------------------------------------------


@dataclass
class SampleThreshold:
    """触发 Layer B 批量优化的样本阈值。"""

    min_total_runs: int
    min_keyword_occurrences: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "minTotalRuns": self.min_total_runs,
            "minKeywordOccurrences": self.min_keyword_occurrences,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SampleThreshold:
        return cls(
            min_total_runs=data["minTotalRuns"],
            min_keyword_occurrences=data["minKeywordOccurrences"],
        )


@dataclass
class ValidationSplit:
    """训练集/留出集划分配置。"""

    ratio: float
    seed: int

    def to_dict(self) -> dict[str, Any]:
        return {"ratio": self.ratio, "seed": self.seed}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ValidationSplit:
        return cls(ratio=data["ratio"], seed=data["seed"])


# 默认指标阈值（低于该值触发提案生成）。
DEFAULT_METRIC_THRESHOLDS: dict[str, float] = {
    "preflight_first_pass_rate": 0.9,
    "execution_plan_unblocked_rate": 0.9,
    "unity_compile_first_pass_rate": 0.95,
}


@dataclass
class OptimizerConfig:
    """Local_Skill_Optimizer 的可配置参数。"""

    SCHEMA_ID = "skill-config/v1"

    max_lines_per_edit: int
    max_lines_per_proposal: int
    sample_threshold: SampleThreshold
    validation_split: ValidationSplit
    metric_thresholds: dict[str, float] = field(default_factory=dict)
    version: str = "skill-config/v1"

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "maxLinesPerEdit": self.max_lines_per_edit,
            "maxLinesPerProposal": self.max_lines_per_proposal,
            "sampleThreshold": self.sample_threshold.to_dict(),
            "validationSplit": self.validation_split.to_dict(),
            "metricThresholds": dict(self.metric_thresholds),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> OptimizerConfig:
        return cls(
            version=data.get("version", "skill-config/v1"),
            max_lines_per_edit=data["maxLinesPerEdit"],
            max_lines_per_proposal=data["maxLinesPerProposal"],
            sample_threshold=SampleThreshold.from_dict(data["sampleThreshold"]),
            validation_split=ValidationSplit.from_dict(data["validationSplit"]),
            metric_thresholds=dict(data.get("metricThresholds", {})),
        )

    @classmethod
    def default(cls) -> OptimizerConfig:
        """返回设计文档约定的默认配置。"""
        return cls(
            max_lines_per_edit=5,
            max_lines_per_proposal=20,
            sample_threshold=SampleThreshold(min_total_runs=1, min_keyword_occurrences=3),
            validation_split=ValidationSplit(ratio=0.3, seed=1337),
            metric_thresholds=dict(DEFAULT_METRIC_THRESHOLDS),
        )


# ---------------------------------------------------------------------------
# Adoption_Stage
# ---------------------------------------------------------------------------


@dataclass
class ExpectedGain:
    """暂存提案的预期收益。"""

    target_metric: str
    delta: float

    def to_dict(self) -> dict[str, Any]:
        return {"targetMetric": self.target_metric, "delta": self.delta}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExpectedGain:
        return cls(target_metric=data["targetMetric"], delta=data["delta"])


@dataclass
class StagedProposal:
    """Adoption_Stage 中的单条待采纳提案记录。"""

    proposal_id: str
    target_path: str
    diff: str
    expected_gain: ExpectedGain
    rationale: str
    anchor_checksum: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "proposalId": self.proposal_id,
            "targetPath": self.target_path,
            "diff": self.diff,
            "expectedGain": self.expected_gain.to_dict(),
            "rationale": self.rationale,
            "anchorChecksum": self.anchor_checksum,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StagedProposal:
        return cls(
            proposal_id=data["proposalId"],
            target_path=data["targetPath"],
            diff=data["diff"],
            expected_gain=ExpectedGain.from_dict(data["expectedGain"]),
            rationale=data["rationale"],
            anchor_checksum=data["anchorChecksum"],
        )


@dataclass
class AdoptionStage:
    """等待人审采纳的提案集合。"""

    SCHEMA_ID = "skill-adoption-stage/v1"

    run_id: str
    staged_proposals: list[StagedProposal] = field(default_factory=list)
    version: str = "skill-adoption-stage/v1"

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "runId": self.run_id,
            "stagedProposals": [item.to_dict() for item in self.staged_proposals],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AdoptionStage:
        return cls(
            version=data.get("version", "skill-adoption-stage/v1"),
            run_id=data["runId"],
            staged_proposals=[
                StagedProposal.from_dict(item)
                for item in data.get("stagedProposals", [])
            ],
        )


# ---------------------------------------------------------------------------
# Proposal decisions
# ---------------------------------------------------------------------------


@dataclass
class FailedGate:
    """提案决策记录中失败的 gate。"""

    gate: str
    output: str

    def to_dict(self) -> dict[str, Any]:
        return {"gate": self.gate, "output": self.output}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FailedGate:
        return cls(gate=data["gate"], output=data["output"])


@dataclass
class ProposalDecision:
    """单个提案的最终决策。"""

    proposal_id: str
    status: str  # accepted | rejected | skipped
    reason: str
    target_path: str | None = None
    target_metric: str | None = None
    failed_gates: list[FailedGate] | None = None

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "proposalId": self.proposal_id,
            "status": self.status,
            "reason": self.reason,
        }
        _opt(data, "targetPath", self.target_path)
        _opt(data, "targetMetric", self.target_metric)
        if self.failed_gates is not None:
            data["failedGates"] = [gate.to_dict() for gate in self.failed_gates]
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ProposalDecision:
        failed_gates = data.get("failedGates")
        return cls(
            proposal_id=data["proposalId"],
            status=data["status"],
            reason=data["reason"],
            target_path=data.get("targetPath"),
            target_metric=data.get("targetMetric"),
            failed_gates=[FailedGate.from_dict(item) for item in failed_gates]
            if failed_gates is not None
            else None,
        )


@dataclass
class ProposalDecisions:
    """一次 Optimization_Run 的全部提案决策记录。"""

    SCHEMA_ID = "skill-proposal-decisions/v1"

    run_id: str
    decisions: list[ProposalDecision] = field(default_factory=list)
    version: str = "skill-proposal-decisions/v1"

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "runId": self.run_id,
            "decisions": [decision.to_dict() for decision in self.decisions],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ProposalDecisions:
        return cls(
            version=data.get("version", "skill-proposal-decisions/v1"),
            run_id=data["runId"],
            decisions=[
                ProposalDecision.from_dict(item) for item in data.get("decisions", [])
            ],
        )


# ---------------------------------------------------------------------------
# Validation / IO helpers
# ---------------------------------------------------------------------------

# 支持 to_dict()/SCHEMA_ID 协议的 skill 模型类型联合。
SkillModel = (
    Signal
    | SignalLedger
    | MetricsReport
    | EditProposal
    | OptimizerConfig
    | AdoptionStage
    | ProposalDecisions
)


def validate(project_root: Path, model: SkillModel) -> None:
    """用对应的 JSON schema 校验模型的 to_dict() 输出。

    复用 ``forai/schemas.py`` 的校验入口；schema 不合法时抛
    ``SchemaValidationError``。
    """
    schema = load_schema(project_root, model.SCHEMA_ID)
    validate_payload(schema, model.to_dict())


def write_model(path: Path, model: SkillModel) -> None:
    """将模型序列化并写入磁盘（复用 json_io 约定）。"""
    write_json(path, model.to_dict())


def read_model(path: Path, model_cls: type[SkillModel]) -> SkillModel:
    """从磁盘读取并反序列化为指定模型类型。"""
    return model_cls.from_dict(read_json(path))
