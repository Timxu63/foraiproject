"""Signal_Ledger 的 append-only 持久化与查询（local-skill-optimization Layer A 存储）。

本模块提供 :class:`LedgerStore`：一个绑定到 ``project_root`` 的账本管理器，负责
加载、append-only 追加并持久化 :class:`~forai.skill_models.SignalLedger` 模型，
持久化路径固定为 ``artifacts/ai-runs/skill-ledger/signal-ledger.json``（独立于单次
run 目录，跨多条 ``Run_History`` 累积）。

命名说明（避免名称冲突）：
- ``skill_models.SignalLedger`` 是**可序列化的数据模型**（entries + aggregate）。
- 本模块的 :class:`LedgerStore` 是**有行为的账本存储**，负责对该模型做加载/追加/持久化
  与聚合查询。两者职责分离，故不复用同名类。

设计约束（对齐 design.md「Signal_Ledger」与 Requirements 10.3、10.11、7.4）：

- **append-only**（Property 22）：:meth:`LedgerStore.append` 只在 ``entries`` 末尾追加新
  ``Signal``，绝不修改或删除已有条目；append 后账本长度按新增数量增长。
- **跨历史聚合**（Property 24）：:meth:`LedgerStore.candidate_keyword_counts` 跨多条
  ``Run_History`` 聚合每个 ``Candidate_Keyword`` 的复现次数与出现的 ``runIds``。
- **阈值充要条件**（Property 26）：:meth:`LedgerStore.progress` 报告相对
  ``Sample_Threshold`` 的进度，当且仅当累计达到阈值才标记 ``threshold_met``。
- **写操作限定 workspace**（Property 17 / Requirement 7.4）：持久化前解析目标路径并校验
  其位于 ``project_root`` 内，否则抛出 :class:`LedgerWriteError`。

关键词复现计数规则（在此明确并固定）：
- 某个 ``term`` 的 **occurrences 定义为「观察到该 term 的不同 ``runId`` 数量」**，即跨历史
  复现次数；同一条 ``Run_History`` 内多次出现同一 term 只计 1 次。
- ``runIds`` 为这些不同 ``runId`` 的去重、排序列表，保证确定性。
- 某个 term 若在不同类别下被观察到，``category`` 取其首次（按 entries 顺序）观察到的类别，
  并保持稳定。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .skill_models import (
    KeywordCount,
    LedgerAggregate,
    SampleThreshold,
    Signal,
    SignalLedger,
    read_model,
    write_model,
)

# Signal_Ledger 的相对持久化路径（独立于单次 run 目录，跨运行累积）。
LEDGER_REL_PATH = ("artifacts", "ai-runs", "skill-ledger", "signal-ledger.json")

# 跨模型对齐的关键词类别中立集合（与 skill-signal schema 的 enum 一致）。
KEYWORD_CATEGORIES = ("steering_match", "capability_registry", "intent_classification")

# 候选关键词的跨历史复现统计；语义与可序列化模型 KeywordCount 一致，
# 此处用类型别名让 design.md 的命名（KeywordStat）得以保留。
KeywordStat = KeywordCount


class LedgerWriteError(RuntimeError):
    """持久化目标越出 workspace 边界时抛出（Property 17 / Requirement 7.4）。"""


@dataclass
class LedgerProgress:
    """``Signal_Ledger`` 相对 ``Sample_Threshold`` 的进度快照。

    字段：
    - ``total_runs``：账本累计的 ``Signal`` 条数（每条对应一次 ``Harvest``）。
    - ``category_counts``：各 ``Candidate_Keyword`` 类别的样本计数，定义为「在该类别下
      至少观察到一个候选关键词的不同 ``runId`` 数量」；键覆盖全部
      :data:`KEYWORD_CATEGORIES`（无样本则为 0）。
    - ``keyword_counts``：每个候选关键词的跨历史复现统计（见
      :meth:`LedgerStore.candidate_keyword_counts`）。
    - ``meets_min_total_runs``：``total_runs >= threshold.min_total_runs``。
    - ``has_recurring_keyword``：是否存在某关键词复现次数达到
      ``threshold.min_keyword_occurrences``。
    - ``threshold_met``：当且仅当上述两项同时满足时为 ``True``（Property 26，
      Sample_Threshold 两个分量均达成才报告具备批量 ``Optimization_Run`` 自动触发条件）。
    """

    total_runs: int
    category_counts: dict[str, int]
    keyword_counts: dict[str, KeywordStat]
    meets_min_total_runs: bool
    has_recurring_keyword: bool
    threshold_met: bool


@dataclass
class LedgerStore:
    """绑定到 ``project_root`` 的 append-only ``Signal_Ledger`` 存储与查询器。

    生命周期：构造后调用 :meth:`load`（或直接使用 :meth:`append`，其内部会先确保账本
    已加载），通过 :meth:`append` 追加 ``Signal`` 并立即持久化，使用 :meth:`progress`
    与 :meth:`candidate_keyword_counts` 做只读查询。
    """

    project_root: Path
    _ledger: SignalLedger | None = field(default=None, init=False, repr=False)
    _read_only: bool = field(default=False, init=False, repr=False)

    # ------------------------------------------------------------------
    # 路径与加载
    # ------------------------------------------------------------------
    @property
    def path(self) -> Path:
        """``Signal_Ledger`` 的持久化绝对路径（未做存在性保证）。"""
        return self.project_root.joinpath(*LEDGER_REL_PATH)

    def _resolve_write_target(self) -> Path:
        """解析持久化目标并校验其位于 workspace 内（Property 17 / Requirement 7.4）。

        通过比较已解析的 ``project_root`` 与目标路径的公共前缀来判定边界；越界时抛
        :class:`LedgerWriteError`，避免任何 workspace 之外的写操作。
        """
        root = self.project_root.resolve()
        target = self.path.resolve()
        if root != target and root not in target.parents:
            raise LedgerWriteError(
                f"Refusing to write Signal_Ledger outside workspace: {target} not under {root}"
            )
        return target

    def load(self) -> SignalLedger:
        """加载账本；文件不存在时返回空 :class:`SignalLedger` 并缓存。"""
        if self._read_only and self._ledger is not None:
            return self._ledger
        if self.path.exists():
            self._ledger = read_model(self.path, SignalLedger)  # type: ignore[assignment]
        else:
            self._ledger = SignalLedger()
        return self._ledger

    def _ensure_loaded(self) -> SignalLedger:
        if self._ledger is None:
            return self.load()
        return self._ledger

    # ------------------------------------------------------------------
    # append-only 写入
    # ------------------------------------------------------------------
    def append(self, signals: list[Signal]) -> SignalLedger:
        """append-only 地追加 ``signals``，重建聚合并持久化（Property 22）。

        仅在 ``entries`` 末尾追加，不修改或删除任何已有条目；空输入为无操作但仍返回当前
        账本。追加后基于完整 ``entries`` 确定性重建 ``aggregate``，并将目标路径校验在
        workspace 内后写盘。
        """
        if self._read_only:
            raise LedgerWriteError("Refusing to append to a read-only Signal_Ledger view.")
        ledger = self._ensure_loaded()
        if signals:
            ledger.entries.extend(signals)
            ledger.aggregate = _rebuild_aggregate(ledger.entries)
            target = self._resolve_write_target()
            write_model(target, ledger)
        return ledger

    # ------------------------------------------------------------------
    # 查询
    # ------------------------------------------------------------------
    def candidate_keyword_counts(self) -> dict[str, KeywordStat]:
        """跨多条 ``Run_History`` 聚合每个候选关键词的复现统计（Property 24）。

        返回以 ``term`` 为键、:class:`KeywordStat`（=``KeywordCount``）为值的字典，其中
        ``occurrences`` 为观察到该 term 的不同 ``runId`` 数、``run_ids`` 为对应去重排序列表。
        """
        return _rebuild_aggregate(self._ensure_loaded().entries).keyword_counts

    def filtered_by_run_ids(self, run_ids: set[str]) -> LedgerStore:
        """返回只读训练集账本视图，不写磁盘、不修改原账本。

        该视图复制当前已加载 entries 中 ``run_id`` 位于 ``run_ids`` 的信号，并重建聚合。
        返回对象的 ``project_root`` 与原 store 一致，但其 ``_ledger`` 已在内存中设置；
        调用只读查询方法不会触碰磁盘。调用方不应对该视图执行 ``append``。
        """
        source = self._ensure_loaded()
        filtered_entries = [entry for entry in source.entries if entry.run_id in run_ids]
        filtered = LedgerStore(project_root=self.project_root)
        filtered._read_only = True
        filtered._ledger = SignalLedger(
            entries=list(filtered_entries),
            aggregate=_rebuild_aggregate(filtered_entries),
        )
        return filtered

    def progress(self, threshold: SampleThreshold) -> LedgerProgress:
        """计算相对 ``Sample_Threshold`` 的进度（Property 26）。"""
        ledger = self._ensure_loaded()
        keyword_counts = _rebuild_aggregate(ledger.entries).keyword_counts

        category_counts = {category: set() for category in KEYWORD_CATEGORIES}
        for entry in ledger.entries:
            for keyword in entry.candidate_keywords:
                bucket = category_counts.setdefault(keyword.category, set())
                bucket.add(entry.run_id)
        category_run_counts = {
            category: len(run_ids) for category, run_ids in category_counts.items()
        }

        total_runs = len(ledger.entries)
        meets_min_total_runs = total_runs >= threshold.min_total_runs
        has_recurring_keyword = any(
            stat.occurrences >= threshold.min_keyword_occurrences
            for stat in keyword_counts.values()
        )
        return LedgerProgress(
            total_runs=total_runs,
            category_counts=category_run_counts,
            keyword_counts=keyword_counts,
            meets_min_total_runs=meets_min_total_runs,
            has_recurring_keyword=has_recurring_keyword,
            threshold_met=meets_min_total_runs and has_recurring_keyword,
        )


def _rebuild_aggregate(entries: list[Signal]) -> LedgerAggregate:
    """从完整 ``entries`` 确定性重建 :class:`LedgerAggregate`。

    ``total_runs`` 为 entries 数量；``keyword_counts`` 中每个 term 的 ``occurrences``
    为观察到该 term 的不同 ``runId`` 数（跨历史复现，单条历史内多次只计 1），
    ``run_ids`` 为去重排序后的 ``runId`` 列表，``category`` 取首次观察到的类别。
    """
    # 保留插入顺序，使输出对相同输入稳定。
    seen_run_ids: dict[str, set[str]] = {}
    categories: dict[str, str] = {}
    for entry in entries:
        for keyword in entry.candidate_keywords:
            term = keyword.term
            if term not in seen_run_ids:
                seen_run_ids[term] = set()
                categories[term] = keyword.category
            seen_run_ids[term].add(entry.run_id)

    keyword_counts = {
        term: KeywordCount(
            category=categories[term],
            occurrences=len(run_ids),
            run_ids=sorted(run_ids),
        )
        for term, run_ids in seen_run_ids.items()
    }
    return LedgerAggregate(total_runs=len(entries), keyword_counts=keyword_counts)
