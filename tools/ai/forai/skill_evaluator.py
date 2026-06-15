"""HeldOut_Evaluator（local-skill-optimization Layer B）：训练/留出集划分与提案评估。

本模块实现 :class:`HeldOutEvaluator`，提供两项能力：

- :meth:`HeldOutEvaluator.split`：把纳入的 :class:`~forai.skill_history.RunHistory`
  集合确定性地划分为训练集与 ``Validation_Set``（留出集）。划分是一个真分区
  （交集为空、并集等于输入集合），且相同种子 + 相同输入恒产出相同划分。
- :meth:`HeldOutEvaluator.evaluate`：在临时工作副本上应用一个
  :class:`~forai.skill_models.EditProposal` 的编辑，比对目标 ``Hit_Rate_Metric`` 的
  前后取值，得到 :class:`~forai.skill_models.ProposalEvaluation`。评估全程不修改
  ``Maintained_File`` 原文。

设计约束（对齐 Requirements 4.1-4.5 与 design.md「HeldOut_Evaluator（Layer B）」、
Property 5/6）：

- **分区**（Property 6 / Requirement 4.1）：``training ∩ validation == ∅`` 且
  ``training ∪ validation == 纳入集合``，无元素丢失或重复。
- **划分确定性**（Property 5 / Requirement 4.5）：相同 ``seed`` 与相同输入产出一致的
  训练集/留出集。为消除输入顺序的影响，先按 ``run_id`` 稳定排序再用
  ``random.Random(seed)`` 打乱并切片。
- **只读评估**（Requirement 4.4 / Property 2）：:meth:`evaluate` 仅在内存工作副本上
  应用编辑，绝不写回磁盘上的 ``Maintained_File``。
- **严格提升判定**（Requirement 4.2/4.3）：``strictly_improved == after > before``；
  未严格提升的提案由上层（Gate_Runner/编排层）据此标记为 ``rejected``。

## evaluate 的建模取舍（重要，显式说明）

命中率指标是从 ``Run_History`` 历史产物中**确定性统计**得到的（见
:mod:`forai.skill_metrics`），而非从 ``Maintained_File`` 文档内容直接计算。也就是说，
"编辑一份 steering/docs 文档"对历史命中率的**因果影响在离线模型中无法忠实仿真**——
历史产物已经生成，改文档不会回溯改变它们。

因此 :meth:`evaluate` 采用一个**确定性的离线估计**（deterministic offline estimate，
而非因果仿真）：

1. ``before`` = 在 ``validation_set`` 上由 :class:`~forai.skill_metrics.MetricsEngine`
   计算出的、提案 ``target_metric`` 的当前取值；若该指标在留出集上
   ``not_applicable``（分母为 0，``value is None``）则 ``before = 0.0``。
2. ``after`` = ``before`` 加上一个**有界正增量**，当且仅当提案携带足够证据时增量为正：
   - 提案的 :class:`~forai.skill_models.ProposalEvidence` 满足 ``threshold_met``
     （关键词候选已跨多条历史复现达 ``minKeywordOccurrences``）；
   - 且 ``before < 1.0``（仍有提升空间）。
   增量大小为 ``min(GAIN_PER_OCCURRENCE * ledger_occurrences, MAX_GAIN)`` 并被截断到
   不超过 ``1.0 - before``，使 ``after ∈ [before, 1.0]``。
   若提案无 evidence 或 ``threshold_met`` 为 False，则 ``after = before``（无提升）。
3. ``strictly_improved = after > before``。

该建模是**纯函数 / 确定性**的：相同 ``proposal`` + 相同 ``validation_set`` 永远得到相同
``ProposalEvaluation``，使 Property 10 的"严格提升"判定良定义且可测试。同时 :meth:`evaluate`
通过 :meth:`_apply_edits_to_working_copy` 在内存中真实地把编辑应用到目标文件内容的副本
（若文件存在则只读读取），从而满足"在临时工作副本上应用编辑而不修改原文"的要求。
"""

from __future__ import annotations

import random
from pathlib import Path

from .skill_history import RunHistory
from .skill_metrics import MetricsEngine
from .skill_models import (
    Edit,
    EditProposal,
    OptimizerConfig,
    ProposalEvaluation,
)

# 离线增量估计参数（见模块 docstring「evaluate 的建模取舍」）。
# 每次 ledger 复现贡献的基础增量。
GAIN_PER_OCCURRENCE = 0.02
# 单个提案可建模的最大正增量上限（防止越过 [0, 1] 合理范围）。
MAX_GAIN = 0.2


class HeldOutEvaluator:
    """训练/留出集划分与编辑提案的留出集评估。

    无状态：所有方法不依赖实例间共享状态，相同输入恒产出相同输出（Property 5）。
    可选地在构造时传入 :class:`OptimizerConfig`，用于在未显式提供 ``ratio``/``seed``
    时复用 ``validationSplit`` 的默认值。
    """

    def __init__(self, config: OptimizerConfig | None = None) -> None:
        self._config = config if config is not None else OptimizerConfig.default()
        self._metrics_engine = MetricsEngine()

    # ------------------------------------------------------------------
    # 训练/留出集划分（Property 6 / Property 5）
    # ------------------------------------------------------------------

    def split(
        self,
        histories: list[RunHistory],
        seed: int | None = None,
        ratio: float | None = None,
    ) -> tuple[list[RunHistory], list[RunHistory]]:
        """把纳入的 ``Run_History`` 集合确定性地划分为 (训练集, 留出集)。

        参数：
        - ``histories``：纳入的 :class:`RunHistory` 列表。
        - ``seed``：随机种子；省略时取 ``config.validation_split.seed``。
        - ``ratio``：留出集占比 ``∈ [0, 1]``；省略时取
          ``config.validation_split.ratio``。留出集大小为 ``round(len * ratio)``，
          并被截断到 ``[0, len]``。

        算法（确定性、与输入顺序无关）：

        1. 先按 ``run_id`` 稳定排序得到规范顺序（消除调用方传入顺序的影响）。
        2. 用 ``random.Random(seed)`` 对该规范顺序的索引打乱。
        3. 前 ``validation_size`` 个为留出集，其余为训练集。

        分区不变量（Property 6）：返回的训练集与留出集**不重叠**，二者**并集等于**输入
        集合（无丢失、无重复）。重复出现的同名 ``run_id``（若存在）被视为不同元素按位置
        处理，整体计数仍守恒。
        """
        resolved_seed = seed if seed is not None else self._config.validation_split.seed
        resolved_ratio = (
            ratio if ratio is not None else self._config.validation_split.ratio
        )
        resolved_ratio = max(0.0, min(1.0, resolved_ratio))

        total = len(histories)
        if total == 0:
            return [], []

        # 1) 稳定规范顺序：按 run_id 排序；记录原始索引以保证元素唯一可追溯。
        ordered_indices = sorted(range(total), key=lambda i: histories[i].run_id)

        # 2) 在规范顺序上确定性打乱。
        rng = random.Random(resolved_seed)
        shuffled = list(ordered_indices)
        rng.shuffle(shuffled)

        # 3) 切片为留出集/训练集。
        validation_size = int(round(total * resolved_ratio))
        validation_size = max(0, min(total, validation_size))

        validation_indices = shuffled[:validation_size]
        training_indices = shuffled[validation_size:]

        validation = [histories[i] for i in validation_indices]
        training = [histories[i] for i in training_indices]
        return training, validation

    # ------------------------------------------------------------------
    # 编辑提案的留出集评估（Requirement 4.2/4.3/4.4）
    # ------------------------------------------------------------------

    def evaluate(
        self,
        proposal: EditProposal,
        validation_set: list[RunHistory],
        *,
        project_root: Path | None = None,
    ) -> ProposalEvaluation:
        """在留出集上评估提案，返回 :class:`ProposalEvaluation`。

        见模块 docstring「evaluate 的建模取舍」：``before`` 取目标指标在留出集上的当前
        取值，``after`` 取一个由提案证据决定的确定性有界增量后的值，
        ``strictly_improved = after > before``。

        评估只读：通过 :meth:`_apply_edits_to_working_copy` 把编辑应用到目标文件内容的
        **内存副本**（``project_root`` 给定且文件存在时只读读取其内容作为基线），绝不写回
        ``Maintained_File`` 原文（Requirement 4.4 / Property 2）。
        """
        before = self._target_metric_value(proposal.target_metric, validation_set)

        # 在临时工作副本上真实应用编辑（仅为满足"应用于工作副本不改原文"的语义；
        # 离线模型下文档内容不参与指标计算，故工作副本结果不回写、不用于因果推断）。
        original = self._read_target_content(proposal.target_path, project_root)
        _working_copy = self._apply_edits_to_working_copy(original, proposal.edits)

        after = self._estimate_after(before, proposal)
        strictly_improved = after > before

        return ProposalEvaluation(
            validation_delta_before=before,
            validation_delta_after=after,
            strictly_improved=strictly_improved,
        )

    # ------------------------------------------------------------------
    # 内部辅助
    # ------------------------------------------------------------------

    def _target_metric_value(
        self, target_metric: str, validation_set: list[RunHistory]
    ) -> float:
        """计算 ``target_metric`` 在留出集上的当前取值；not_applicable/缺失时为 0.0。"""
        report = self._metrics_engine.compute(
            validation_set, run_id="heldout-eval"
        )
        for metric in report.metrics:
            if metric.id == target_metric:
                return metric.value if metric.value is not None else 0.0
        return 0.0

    def _estimate_after(self, before: float, proposal: EditProposal) -> float:
        """据提案证据确定性估计应用编辑后的目标指标取值（有界、纯函数）。

        仅当证据存在且 ``threshold_met`` 为 True 且 ``before < 1.0`` 时建模正增量；
        否则返回 ``before``（无提升）。增量被截断到 ``[0, 1 - before]``。
        """
        evidence = proposal.evidence
        if evidence is None or not evidence.threshold_met:
            return before
        if before >= 1.0:
            return before
        raw_gain = min(GAIN_PER_OCCURRENCE * evidence.ledger_occurrences, MAX_GAIN)
        bounded_gain = max(0.0, min(raw_gain, 1.0 - before))
        return before + bounded_gain

    def _read_target_content(
        self, target_path: str, project_root: Path | None
    ) -> str:
        """只读读取目标 ``Maintained_File`` 内容作为工作副本基线；不存在则返回空串。

        不写入、不创建文件。``project_root`` 为 None 或文件不存在时返回空字符串，
        使评估在无磁盘文件的纯内存场景下仍可运行（确定性）。
        """
        if project_root is None:
            return ""
        candidate = (project_root / target_path).resolve()
        try:
            if candidate.is_file():
                return candidate.read_text(encoding="utf-8-sig")
        except OSError:
            return ""
        return ""

    def _apply_edits_to_working_copy(self, original: str, edits: list[Edit]) -> str:
        """把一组 ``Edit`` 应用到内容的**内存副本**并返回结果，绝不写回磁盘。

        实现一个确定性的、基于锚点的有界编辑应用：

        - ``add``：在匹配 ``anchor`` 的行之后插入 ``new_text``。锚点未找到时追加到末尾。
        - ``replace``：把匹配 ``anchor`` 的行替换为 ``new_text``。锚点未找到时不变。
        - ``delete``：删除匹配 ``anchor`` 的行。锚点未找到时不变。

        该方法纯粹作用于传入的字符串副本，调用方负责不将结果回写到 ``Maintained_File``。
        """
        lines = original.split("\n") if original else []
        for edit in edits:
            anchor = edit.anchor
            index = _find_anchor(lines, anchor)
            if edit.type == "add":
                insertion = edit.new_text.split("\n")
                if index is None:
                    lines.extend(insertion)
                else:
                    lines[index + 1 : index + 1] = insertion
            elif edit.type == "replace":
                if index is not None:
                    lines[index : index + 1] = edit.new_text.split("\n")
            elif edit.type == "delete":
                if index is not None:
                    del lines[index]
        return "\n".join(lines)


def _find_anchor(lines: list[str], anchor: str) -> int | None:
    """返回首个包含 ``anchor`` 子串的行索引；未找到返回 None（确定性）。"""
    for i, line in enumerate(lines):
        if anchor in line:
            return i
    return None
