"""Proposal_Generator（local-skill-optimization Layer B）：有界编辑提案生成。

本模块实现 :class:`ProposalGenerator`，在批量 ``Optimization_Run`` 中基于
:class:`~forai.skill_models.MetricsReport` 与 ``Signal_Ledger`` 的跨历史累积证据，针对
``Maintained_File`` 生成有界（bounded）的 :class:`~forai.skill_models.EditProposal`。

设计约束（对齐 Requirements 3.1-3.6、10.11、10.13、10.15 与 design.md
「Proposal_Generator（Layer B）」、Property 7/8/9）：

- **指标低于阈值触发**（Property 8 / Requirement 3.1）：当且仅当 ``MetricsReport`` 中至少有
  一个 ``Hit_Rate_Metric`` 的取值低于 ``config.metric_thresholds`` 中配置的阈值时，才生成
  提案；此时至少产出一个针对 ``Maintained_File`` 的 ``EditProposal``。
- **目标限定 Maintained_File**（Requirement 3.2）：每个提案的 ``targetPath`` 都是
  ``Maintained_File``（``.kiro/steering/*.md`` 或 ``docs/ai/*.md``，见
  :func:`is_maintained_file`）。
- **Protected_Path 拒绝**（Property 9 / Requirement 3.3）：任何目标解析为 ``Protected_Path``
  （见 :func:`is_protected_path`）或非 ``Maintained_File`` 的候选提案被**拒绝**并记录原因。
  由于生成器只针对 ``Maintained_File``，该拦截是防御性的第一道防线（采纳阶段还有第二道）。
- **有界编辑**（Property 7 / Requirement 3.4/3.6）：每个 :class:`~forai.skill_models.Edit`
  的 ``type ∈ {add, delete, replace}``，``changedLines <= config.max_lines_per_edit``，
  提案 ``totalChangedLines <= config.max_lines_per_proposal``；记录编辑类型、原文锚点、
  新文本、目标 ``Hit_Rate_Metric`` 与文字理由（Requirement 3.5）。
- **关键词跨历史复现门槛**（Requirement 10.13）：候选关键词当且仅当其在 ``Signal_Ledger``
  中跨多条 ``Run_History`` 的复现次数达到 ``config.sample_threshold.min_keyword_occurrences``
  时，才作为提案候选；证据写入 :class:`~forai.skill_models.ProposalEvidence`。
- **关键词类别中立**（Requirement 10.15）：候选携带 ``keywordCategory ∈ {steering_match,
  capability_registry, intent_classification}``（取自 ledger 聚合），并据此映射目标文件。
- **跨历史证据**（Requirement 10.11）：提案以 ``Signal_Ledger`` 累积证据为统计依据，而非
  单条 ``Run_History``。

## 公共 API

- :func:`is_maintained_file` / :func:`is_protected_path`：路径分类辅助。
- :class:`ProposalGenerator` 及其 :meth:`ProposalGenerator.generate`。
- 模块级便捷函数 :func:`generate`（等价于 ``ProposalGenerator().generate(...)``）。
- :class:`GenerateResult`（生成的提案 + 被拒绝的提案及原因）。

## 初始状态约定

新生成、尚未经留出集评估与 gate 校验的提案 ``status`` 置为 ``"skipped"``（设计文档
``EditProposal.status ∈ {accepted, rejected, skipped}`` 中表示"未决定"的占位状态）。最终的
``accepted``/``rejected`` 决策由后续 HeldOut_Evaluator + Gate_Runner 阶段做出。被
Protected_Path/非 Maintained_File 拦截的候选 ``status`` 直接置为 ``"rejected"``。

## 关键词类别 → 目标 Maintained_File 映射

| keywordCategory | 目标 Maintained_File | 锚点 |
|-----------------|----------------------|------|
| ``capability_registry`` | ``docs/ai/capability-registry.md`` | ``## 能力关键词`` |
| ``steering_match`` | ``.kiro/steering/unity-context.md`` | ``## 触发关键词`` |
| ``intent_classification`` | ``.kiro/steering/intent-routing.md`` | ``## 意图关键词`` |

无可用关键词候选但仍有指标低于阈值时，按每个低于阈值的指标生成一个**回退提案**
（无 ``keywordCategory``），目标为默认 steering 文件 :data:`_DEFAULT_FALLBACK_TARGET`，
建议人工复核（满足 Property 8 的"至少一个提案"）。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .skill_ledger import LedgerStore
from .skill_models import (
    Edit,
    EditProposal,
    HitRateMetric,
    MetricsReport,
    OptimizerConfig,
    ProposalEvidence,
)

# ---------------------------------------------------------------------------
# 路径分类常量与辅助
# ---------------------------------------------------------------------------

# Maintained_File 的两个根前缀（正斜杠规范化后）与统一后缀。
_MAINTAINED_PREFIXES = (".kiro/steering/", "docs/ai/")
_MAINTAINED_SUFFIX = ".md"

# Protected_Path：禁止直接编辑（对齐 AGENTS.md / requirements 术语表）。
_PROTECTED_SUFFIXES = (".unity", ".prefab", ".asset", ".meta")
_PROTECTED_EXACT = ("Packages/manifest.json", "Packages/packages-lock.json")

# 关键词类别 → 目标 Maintained_File 与锚点映射（见模块 docstring）。
_CATEGORY_TARGETS: dict[str, tuple[str, str]] = {
    "capability_registry": ("docs/ai/capability-registry.md", "## 能力关键词"),
    "steering_match": (".kiro/steering/unity-context.md", "## 触发关键词"),
    "intent_classification": (".kiro/steering/intent-routing.md", "## 意图关键词"),
}

# 无关键词候选时回退提案的默认目标与锚点。
_DEFAULT_FALLBACK_TARGET = ".kiro/steering/unity-context.md"
_DEFAULT_FALLBACK_ANCHOR = "## 优化建议"

# 未决定提案的初始状态占位（详见模块 docstring「初始状态约定」）。
STATUS_UNDECIDED = "skipped"
STATUS_REJECTED = "rejected"


def _normalize(path: str) -> str:
    """把路径分隔符规范化为正斜杠，便于稳定匹配（不解析符号链接）。"""
    return path.replace("\\", "/").strip()


def is_maintained_file(path: str) -> bool:
    """判定 ``path`` 是否为 ``Maintained_File``。

    ``Maintained_File`` 为 ``.kiro/steering/*.md`` 或 ``docs/ai/*.md``（含
    ``docs/ai/capability-registry.md``）。匹配前先把分隔符规范化为正斜杠。
    """
    normalized = _normalize(path)
    if not normalized.endswith(_MAINTAINED_SUFFIX):
        return False
    return any(normalized.startswith(prefix) for prefix in _MAINTAINED_PREFIXES)


def is_protected_path(path: str) -> bool:
    """判定 ``path`` 是否匹配 ``Protected_Path``（禁止直接编辑）。

    覆盖 ``*.unity``、``*.prefab``、``*.asset``（含 ``ProjectSettings/*.asset``）、
    ``*.meta``、``Packages/manifest.json``、``Packages/packages-lock.json``。
    """
    normalized = _normalize(path)
    if normalized.endswith(_PROTECTED_SUFFIXES):
        return True
    return normalized in _PROTECTED_EXACT


# ---------------------------------------------------------------------------
# 返回结构
# ---------------------------------------------------------------------------


@dataclass
class RejectedProposal:
    """一个被拒绝的候选提案及其原因（供 CLI/decisions 层记录）。"""

    proposal: EditProposal
    reason: str


@dataclass
class GenerateResult:
    """:meth:`ProposalGenerator.generate` 的结果。

    - ``proposals``：生成的、尚未决定的 :class:`EditProposal`（``status == "skipped"``），
      等待后续留出集评估与 gate 校验。
    - ``rejected``：因匹配 ``Protected_Path`` 或非 ``Maintained_File`` 而被拒绝的候选
      （``status == "rejected"``）及拒绝原因，便于 decisions 层记录（Property 9）。
    """

    proposals: list[EditProposal] = field(default_factory=list)
    rejected: list[RejectedProposal] = field(default_factory=list)


# ---------------------------------------------------------------------------
# 候选描述（内部）
# ---------------------------------------------------------------------------


@dataclass
class _Candidate:
    """一个待物化为 ``EditProposal`` 的内部候选描述。"""

    target_path: str
    anchor: str
    new_text: str
    edit_type: str
    target_metric: str
    rationale: str
    keyword_category: str | None = None
    evidence: ProposalEvidence | None = None


# ---------------------------------------------------------------------------
# Proposal_Generator
# ---------------------------------------------------------------------------


class ProposalGenerator:
    """基于指标与 ``Signal_Ledger`` 累积证据生成有界编辑提案。

    无状态：:meth:`generate` 不依赖实例间共享状态，相同输入恒产出相同输出（确定性）。
    """

    def generate(
        self,
        metrics: MetricsReport,
        ledger: LedgerStore,
        config: OptimizerConfig,
    ) -> GenerateResult:
        """生成有界编辑提案。

        流程：

        1. 找出 ``metrics`` 中低于配置阈值的 ``Hit_Rate_Metric``（``not_applicable`` /
           无阈值的指标跳过）。若没有任何低于阈值的指标，返回空结果（Requirement 3.1）。
        2. 从 ``ledger`` 取跨历史关键词复现统计，筛选复现次数达到
           ``config.sample_threshold.min_keyword_occurrences`` 的候选（Requirement 10.13）。
        3. 为每个合格关键词生成一个候选提案（目标文件由 ``keywordCategory`` 映射）；
           若无合格关键词，则为每个低于阈值的指标生成一个回退候选（Property 8）。
        4. 确定性地分配 ``proposalId``（``prop-0001`` …），物化为 :class:`EditProposal`，
           并对每个目标做 ``Protected_Path`` / ``Maintained_File`` 拦截（Property 9）。

        返回 :class:`GenerateResult`（生成的提案 + 被拒绝的提案及原因）。
        """
        below = self._metrics_below_threshold(metrics, config)
        if not below:
            return GenerateResult()

        primary_metric = below[0].id
        eligible = self._eligible_keywords(ledger, config)

        candidates: list[_Candidate] = []
        if eligible:
            for term, stat in eligible:
                candidates.append(
                    self._keyword_candidate(term, stat, primary_metric)
                )
        else:
            for metric in below:
                candidates.append(self._fallback_candidate(metric.id))

        return self._materialize(candidates, config)

    # ------------------------------------------------------------------
    # 步骤实现
    # ------------------------------------------------------------------

    def _metrics_below_threshold(
        self, metrics: MetricsReport, config: OptimizerConfig
    ) -> list[HitRateMetric]:
        """返回低于配置阈值的指标，按 ``id`` 排序以保证确定性。

        跳过 ``value is None``（``not_applicable``，分母为 0）与未在
        ``config.metric_thresholds`` 中配置阈值的指标。
        """
        result: list[HitRateMetric] = []
        for metric in metrics.metrics:
            if metric.value is None:
                continue
            threshold = config.metric_thresholds.get(metric.id)
            if threshold is None:
                continue
            if metric.value < threshold:
                result.append(metric)
        return sorted(result, key=lambda m: m.id)

    def _eligible_keywords(
        self, ledger: LedgerStore, config: OptimizerConfig
    ) -> list[tuple[str, object]]:
        """返回复现次数达阈值的关键词候选，按 (复现次数降序, term 升序) 确定性排序。"""
        min_occurrences = config.sample_threshold.min_keyword_occurrences
        counts = ledger.candidate_keyword_counts()
        eligible = [
            (term, stat)
            for term, stat in counts.items()
            if stat.occurrences >= min_occurrences
        ]
        eligible.sort(key=lambda item: (-item[1].occurrences, item[0]))
        return eligible

    def _keyword_candidate(
        self, term: str, stat: object, target_metric: str
    ) -> _Candidate:
        """据合格关键词构造一个 add 类型候选；目标文件由类别映射。"""
        category = getattr(stat, "category", "intent_classification")
        occurrences = getattr(stat, "occurrences", 0)
        target_path, anchor = _CATEGORY_TARGETS.get(
            category, _CATEGORY_TARGETS["intent_classification"]
        )
        return _Candidate(
            target_path=target_path,
            anchor=anchor,
            new_text=f"- {term}",
            edit_type="add",
            target_metric=target_metric,
            rationale=(
                f"{term} 在 {occurrences} 条历史中复现，预期提升 {target_metric}"
            ),
            keyword_category=category,
            evidence=ProposalEvidence(
                ledger_occurrences=occurrences, threshold_met=True
            ),
        )

    def _fallback_candidate(self, target_metric: str) -> _Candidate:
        """无合格关键词时，为低于阈值的指标构造一个回退复核候选。"""
        return _Candidate(
            target_path=_DEFAULT_FALLBACK_TARGET,
            anchor=_DEFAULT_FALLBACK_ANCHOR,
            new_text=f"- 复核 {target_metric}：命中率低于阈值，建议补充相关指引",
            edit_type="add",
            target_metric=target_metric,
            rationale=(
                f"{target_metric} 低于配置阈值，但暂无达复现门槛的关键词候选，"
                "建议人工复核对应 Maintained_File"
            ),
            keyword_category=None,
            evidence=None,
        )

    def _materialize(
        self, candidates: list[_Candidate], config: OptimizerConfig
    ) -> GenerateResult:
        """把候选物化为 :class:`EditProposal` 并做路径拦截，分配确定性 ``proposalId``。"""
        result = GenerateResult()
        for index, candidate in enumerate(candidates, start=1):
            proposal_id = f"prop-{index:04d}"
            edits = self._build_edits(candidate, config)
            total_changed = sum(edit.changed_lines for edit in edits)
            maintained = is_maintained_file(candidate.target_path)
            protected = is_protected_path(candidate.target_path)
            status = (
                STATUS_REJECTED if (protected or not maintained) else STATUS_UNDECIDED
            )
            proposal = EditProposal(
                proposal_id=proposal_id,
                target_path=candidate.target_path,
                is_maintained_file=maintained,
                edits=edits,
                total_changed_lines=total_changed,
                target_metric=candidate.target_metric,
                rationale=candidate.rationale,
                status=status,
                keyword_category=candidate.keyword_category,
                evidence=candidate.evidence,
            )
            if protected:
                result.rejected.append(
                    RejectedProposal(
                        proposal=proposal,
                        reason=(
                            f"目标路径 {candidate.target_path} 匹配 Protected_Path，"
                            "拒绝生成编辑提案"
                        ),
                    )
                )
            elif not maintained:
                result.rejected.append(
                    RejectedProposal(
                        proposal=proposal,
                        reason=(
                            f"目标路径 {candidate.target_path} 不是 Maintained_File，"
                            "拒绝生成编辑提案"
                        ),
                    )
                )
            else:
                result.proposals.append(proposal)
        return result

    def _build_edits(self, candidate: _Candidate, config: OptimizerConfig) -> list[Edit]:
        """构造单个有界编辑；``changedLines`` 为 ``newText`` 的行数（确定性）。

        ``newText`` 的行数被截断到 ``config.max_lines_per_edit`` 与
        ``config.max_lines_per_proposal``，确保满足有界编辑约束（Property 7）。
        """
        lines = candidate.new_text.split("\n")
        max_lines = max(1, min(config.max_lines_per_edit, config.max_lines_per_proposal))
        if len(lines) > max_lines:
            lines = lines[:max_lines]
        bounded_text = "\n".join(lines)
        return [
            Edit(
                type=candidate.edit_type,
                anchor=candidate.anchor,
                new_text=bounded_text,
                changed_lines=len(lines),
            )
        ]


# ---------------------------------------------------------------------------
# 模块级便捷入口
# ---------------------------------------------------------------------------


def generate(
    metrics: MetricsReport,
    ledger: LedgerStore,
    config: OptimizerConfig,
) -> GenerateResult:
    """便捷函数：等价于 ``ProposalGenerator().generate(metrics, ledger, config)``。"""
    return ProposalGenerator().generate(metrics, ledger, config)
