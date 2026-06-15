"""Harvester（local-skill-optimization Layer A）：单条 Run_History 的只读信号采集。

本模块实现 :func:`harvest`：对指定 ``run-id`` 的 ``Run_History`` 执行一次廉价、只读的
``Harvest``，确定性地提取一条 :class:`~forai.skill_models.Signal` 并以 append-only 方式
追加到 ``Signal_Ledger``（复用 :class:`~forai.skill_ledger.LedgerStore`）。

设计约束（对齐 Requirements 10.1、10.2、10.4、10.5、10.6、10.7、10.12、10.15，
以及 design.md「Harvester（Layer A）」与 Property 21/22/23/25）：

- **只读**（Property 2 / Requirement 10.5）：仅经
  :func:`~forai.skill_history.read_run_history` 读取产物，绝不修改/移动/删除任何
  ``Run_History``。唯一的写操作是把新 ``Signal`` 追加进 ``Signal_Ledger``。
- **无副作用**（Property 23 / Requirements 10.4、10.12）：不生成任何 ``Edit_Proposal``、
  不运行任何 ``Deterministic_Gate``、不修改任何 ``Maintained_File``；观察到的
  ``Candidate_Keyword`` 仅被采集进 ledger，不据单条记录直接成为提案。
- **确定性**：相同 ``Run_History`` 产出相同 ``Signal``（候选关键词稳定排序、去重；
  ``harvestedAt`` 优先从产物时间戳派生，避免依赖墙钟）。
- **容错**（Property 3 / Requirement 10.7）：缺失或非法 JSON 的产物使对应信号被跳过并附
  原因（记入 ``Signal.skipped``），但仍追加其余可提取信号。

### preflightFirstPass 启发式（已固定并在此说明）

本项目无独立的 ``preflight`` 产物，故从可用产物确定性推断「preflight 是否一次通过」：

``preflightFirstPass = True`` 当且仅当以下全部成立：

1. ``workflow-state.json`` 存在且可解析，其 ``status`` 不为 ``"blocked"`` 且 ``blockers``
   为空（工作流未被阻断）；
2. ``riskReviewBlocked`` 为 ``False``（risk-review 未阻断）；
3. ``clarificationRoundTrips == 0``（无需求澄清往返）。

若 ``workflow-state.json`` 缺失或非法，无法判定工作流是否被阻断，则为 ``preflightFirstPass``
记录一条 ``skipped`` 项并采用文档化默认值 ``False``（保守地视为未一次通过）。

### keywordCategory 映射（类别中立，覆盖三类，Property 25 / Requirement 10.15）

候选关键词从 ``intent-analysis.json`` 的 ``domain``、``goal``、``requestedChanges`` 提取，
按 term 命中下列中立提示集合分配类别，三类均可覆盖且不硬编码单一类别：

- 命中 :data:`_CAPABILITY_HINTS`（capability-registry 能力关键词，如 ``roslyn-gateway``）
  → ``capability_registry``；
- 命中 :data:`_STEERING_HINTS`（steering 触发/匹配关键词，如 ``filematchpattern``）
  → ``steering_match``；
- 其余意图词 → 默认 ``intent_classification``。

提示集合是可扩展的中立默认值；默认类别为 ``intent_classification``，以保证类别保持中立而
不偏向单一来源。

### harvestedAt 选择

为保证确定性，``harvestedAt`` 优先取 ``workflow-state.json`` 的 ``updatedAtUtc``，
其次 ``startedAtUtc``；两者均不可用时回退到当前 UTC 时间（注意：使用墙钟会破坏严格确定性，
仅作为缺省兜底）。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .skill_history import RunHistory, read_run_history
from .skill_ledger import LedgerProgress, LedgerStore
from .skill_models import (
    CandidateKeyword,
    OptimizerConfig,
    SampleThreshold,
    Signal,
    SkippedSignal,
)

# 提取候选关键词时单条 Signal 的上限，避免在超长文本上膨胀（保持开销可忽略）。
_MAX_KEYWORDS = 30

# 词形 token 的最小长度（短于此的 token 视为噪声丢弃）。
_MIN_TOKEN_LENGTH = 3

# 候选关键词 token 的匹配模式：字母起始，可含数字、连字符、下划线、斜杠。
_TOKEN_PATTERN = re.compile(r"[A-Za-z][A-Za-z0-9_/-]{2,}")

# 高频英文停用词（小写）；从候选关键词中剔除以聚焦有信息量的意图词。
_STOPWORDS = frozenset(
    {
        "the",
        "and",
        "for",
        "with",
        "without",
        "are",
        "not",
        "use",
        "using",
        "that",
        "this",
        "they",
        "them",
        "from",
        "into",
        "make",
        "made",
        "should",
        "shall",
        "must",
        "can",
        "could",
        "would",
        "will",
        "have",
        "has",
        "had",
        "its",
        "their",
        "than",
        "then",
        "when",
        "where",
        "which",
        "while",
        "such",
        "more",
        "most",
        "merely",
        "only",
        "keep",
        "kept",
        "adjust",
        "improve",
        "optimize",
        "change",
        "changes",
    }
)

# capability-registry 能力关键词的中立提示集合（小写）。命中即归类
# ``capability_registry``。可按项目扩展，默认覆盖当前 Unity 网关标识符。
_CAPABILITY_HINTS = frozenset(
    {
        "roslyn-gateway",
        "roslyn",
        "gateway",
        "unity",
        "adapter",
        "capability-registry",
    }
)

# steering 触发/匹配关键词的中立提示集合（小写）。命中即归类 ``steering_match``。
_STEERING_HINTS = frozenset(
    {
        "agents",
        "steering",
        "filematchpattern",
        "inclusion",
        "frontmatter",
    }
)

# 默认候选关键词类别（类别中立，不偏向单一来源）。
_DEFAULT_CATEGORY = "intent_classification"

# 信号名常量（用于 Signal.skipped 的 signal 字段）。
_SIGNAL_PREFLIGHT = "preflightFirstPass"
_SIGNAL_RISK_REVIEW = "riskReviewBlocked"
_SIGNAL_CLARIFICATION = "clarificationRoundTrips"
_SIGNAL_KEYWORDS = "candidateKeywords"

# 各信号依赖的产物名（read_run_history 以文件名 stem 为键）。
_ARTIFACT_WORKFLOW_STATE = "workflow-state"
_ARTIFACT_RISK_REVIEW = "risk-review"
_ARTIFACT_REQUIREMENT_CHECK = "requirement-check"
_ARTIFACT_INTENT_ANALYSIS = "intent-analysis"


@dataclass
class HarvestResult:
    """一次 :func:`harvest` 的结果。

    字段：
    - ``signal``：本次提取并已追加到 ``Signal_Ledger`` 的 :class:`Signal`。
    - ``skipped``：因产物缺失/非法 JSON 而被跳过的信号项（同时也内嵌于
      ``signal.skipped``，此处冗余暴露便于调用方直接消费）。
    - ``progress``：追加后的 ``Signal_Ledger`` 相对 ``Sample_Threshold`` 的进度快照。
    """

    signal: Signal
    skipped: list[SkippedSignal] = field(default_factory=list)
    progress: LedgerProgress | None = None


def harvest(project_root: Path, run_id: str) -> HarvestResult:
    """对单条 ``Run_History`` 执行只读 ``Harvest`` 并把 ``Signal`` 追加到 ``Signal_Ledger``。

    只读读取 ``artifacts/ai-runs/<run-id>/`` 的产物，确定性提取 preflight 是否一次通过、
    risk-review 是否阻断、需求澄清往返次数、候选关键词与意图词；缺失/非法 JSON 的信号被
    跳过并附原因，仍追加可提取信号。不生成提案、不跑 gate、不改 ``Maintained_File``。

    参数：
    - ``project_root``：工作区根目录。
    - ``run_id``：目标运行记录目录名。

    返回 :class:`HarvestResult`（新增 ``Signal``、skipped 项与追加后 ledger 进度）。
    """
    run_dir = project_root / "artifacts" / "ai-runs" / run_id
    history = read_run_history(run_dir)

    skipped: list[SkippedSignal] = []

    risk_review_blocked = _extract_risk_review_blocked(history, skipped)
    clarification_round_trips = _extract_clarification_round_trips(history, skipped)
    preflight_first_pass = _extract_preflight_first_pass(
        history,
        skipped,
        risk_review_blocked=risk_review_blocked,
        clarification_round_trips=clarification_round_trips,
    )
    candidate_keywords = _extract_candidate_keywords(history, skipped)

    profile = _safe_str(history.artifacts.get(_ARTIFACT_WORKFLOW_STATE), "profile")
    harvested_at = _derive_harvested_at(history)

    signal = Signal(
        run_id=run_id,
        harvested_at=harvested_at,
        preflight_first_pass=preflight_first_pass,
        risk_review_blocked=risk_review_blocked,
        clarification_round_trips=clarification_round_trips,
        candidate_keywords=candidate_keywords,
        skipped=list(skipped),
        profile=profile,
    )

    store = LedgerStore(project_root=project_root)
    store.append([signal])
    threshold = _default_sample_threshold()
    progress = store.progress(threshold)

    return HarvestResult(signal=signal, skipped=list(skipped), progress=progress)


# ---------------------------------------------------------------------------
# 信号提取（确定性）
# ---------------------------------------------------------------------------


def _extract_risk_review_blocked(
    history: RunHistory, skipped: list[SkippedSignal]
) -> bool:
    """从 ``risk-review.json`` 判定是否阻断；缺失/非法则 skip 并默认 ``False``。

    判定规则：``overallRisk == "blocked"`` 或任一 finding 的 ``risk == "blocked"``。
    """
    artifact = history.artifacts.get(_ARTIFACT_RISK_REVIEW)
    if not isinstance(artifact, dict):
        skipped.append(
            SkippedSignal(
                signal=_SIGNAL_RISK_REVIEW,
                reason=_artifact_reason(history, _ARTIFACT_RISK_REVIEW),
            )
        )
        return False

    if str(artifact.get("overallRisk", "")).lower() == "blocked":
        return True
    findings = artifact.get("findings")
    if isinstance(findings, list):
        for finding in findings:
            if isinstance(finding, dict) and str(finding.get("risk", "")).lower() == "blocked":
                return True
    return False


def _extract_clarification_round_trips(
    history: RunHistory, skipped: list[SkippedSignal]
) -> int:
    """从 ``requirement-check.json`` 统计澄清往返次数；缺失/非法则 skip 并默认 ``0``。

    单条 ``Run_History`` 仅有一份 requirement-check，故计数为 0 或 1：当 ``status`` 为
    ``needs_clarification`` 或 ``blocked`` 时计 1，否则计 0。
    """
    artifact = history.artifacts.get(_ARTIFACT_REQUIREMENT_CHECK)
    if not isinstance(artifact, dict):
        skipped.append(
            SkippedSignal(
                signal=_SIGNAL_CLARIFICATION,
                reason=_artifact_reason(history, _ARTIFACT_REQUIREMENT_CHECK),
            )
        )
        return 0

    status = str(artifact.get("status", "")).lower()
    return 1 if status in {"needs_clarification", "blocked"} else 0


def _extract_preflight_first_pass(
    history: RunHistory,
    skipped: list[SkippedSignal],
    *,
    risk_review_blocked: bool,
    clarification_round_trips: int,
) -> bool:
    """推断 preflight 是否一次通过（启发式见模块 docstring）。

    当 ``workflow-state.json`` 缺失/非法时无法判定工作流是否被阻断，记录 skip 并默认
    ``False``。否则 ``preflightFirstPass`` 为：工作流未阻断 且 risk-review 未阻断 且
    无澄清往返。
    """
    artifact = history.artifacts.get(_ARTIFACT_WORKFLOW_STATE)
    if not isinstance(artifact, dict):
        skipped.append(
            SkippedSignal(
                signal=_SIGNAL_PREFLIGHT,
                reason=_artifact_reason(history, _ARTIFACT_WORKFLOW_STATE),
            )
        )
        return False

    status = str(artifact.get("status", "")).lower()
    blockers = artifact.get("blockers")
    workflow_blocked = status == "blocked" or bool(
        blockers if isinstance(blockers, list) else False
    )
    return (
        not workflow_blocked
        and not risk_review_blocked
        and clarification_round_trips == 0
    )


def _extract_candidate_keywords(
    history: RunHistory, skipped: list[SkippedSignal]
) -> list[CandidateKeyword]:
    """从 ``intent-analysis.json`` 确定性提取候选关键词；缺失/非法则 skip。

    提取来源：``domain``（作为整体短语）、``goal`` 与 ``requestedChanges``（分词）。
    分词后小写、去停用词、按首次出现顺序去重，并按 :data:`_MAX_KEYWORDS` 截断。类别按
    :func:`_categorize` 分配（类别中立，默认 ``intent_classification``）。
    """
    artifact = history.artifacts.get(_ARTIFACT_INTENT_ANALYSIS)
    if not isinstance(artifact, dict):
        skipped.append(
            SkippedSignal(
                signal=_SIGNAL_KEYWORDS,
                reason=_artifact_reason(history, _ARTIFACT_INTENT_ANALYSIS),
            )
        )
        return []

    keywords: list[CandidateKeyword] = []
    seen: set[str] = set()

    def _add(term: str, context: str) -> None:
        normalized = term.strip().lower()
        if (
            len(normalized) < _MIN_TOKEN_LENGTH
            or normalized in _STOPWORDS
            or normalized in seen
            or len(keywords) >= _MAX_KEYWORDS
        ):
            return
        seen.add(normalized)
        keywords.append(
            CandidateKeyword(
                term=normalized,
                category=_categorize(normalized),
                context=context,
            )
        )

    # domain 作为整体短语优先纳入（若是有效短语）。
    domain = artifact.get("domain")
    if isinstance(domain, str) and domain.strip():
        _add(domain, context="domain")

    # goal 与 requestedChanges 分词。
    text_parts: list[str] = []
    goal = artifact.get("goal")
    if isinstance(goal, str):
        text_parts.append(goal)
    requested = artifact.get("requestedChanges")
    if isinstance(requested, list):
        text_parts.extend(item for item in requested if isinstance(item, str))

    for token in _tokenize(" ".join(text_parts)):
        _add(token, context="intent")

    return keywords


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------


def _tokenize(text: str) -> list[str]:
    """把文本切分为词形 token，保持首次出现顺序（小写、去重在调用方处理）。"""
    return [match.group(0) for match in _TOKEN_PATTERN.finditer(text)]


def _categorize(term: str) -> str:
    """按中立提示集合为候选关键词分配类别（默认 ``intent_classification``）。"""
    if term in _CAPABILITY_HINTS:
        return "capability_registry"
    if term in _STEERING_HINTS:
        return "steering_match"
    return _DEFAULT_CATEGORY


def _artifact_reason(history: RunHistory, artifact_name: str) -> str:
    """为缺失/非法产物生成 skip 原因。

    若该产物在 :attr:`RunHistory.skipped` 中（非法 JSON），复用其原因；否则报告缺失。
    """
    for item in history.skipped:
        if item.get("artifact") == artifact_name:
            return f"{artifact_name}.json invalid JSON: {item.get('reason', 'unknown')}"
    return f"{artifact_name}.json missing"


def _safe_str(artifact: Any, key: str) -> str | None:
    """从可能为非 dict 的产物中安全读取字符串字段。"""
    if isinstance(artifact, dict):
        value = artifact.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _derive_harvested_at(history: RunHistory) -> str:
    """确定性派生 ``harvestedAt``：优先 ``updatedAtUtc``，次 ``startedAtUtc``，否则当前 UTC。"""
    state = history.artifacts.get(_ARTIFACT_WORKFLOW_STATE)
    for key in ("updatedAtUtc", "startedAtUtc"):
        value = _safe_str(state, key)
        if value is not None:
            return value
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _default_sample_threshold() -> SampleThreshold:
    """返回用于进度报告的默认 ``Sample_Threshold``（复用 OptimizerConfig 默认值）。"""
    return OptimizerConfig.default().sample_threshold
