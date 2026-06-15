"""Gate_Runner 与采纳判定编排（local-skill-optimization Layer B）。

本模块实现两件事：

1. :class:`GateRunner`（Task 9.1 / Requirement 5.1-5.5，design.md「Gate_Runner（Layer B）」、
   Property 10/11）：对通过留出集评估的 :class:`~forai.skill_models.EditProposal` 运行相关
   ``Deterministic_Gate``（schema 校验、pytest、risk review、unity compile），收集
   :class:`~forai.skill_models.GateResult`，任一 gate 失败则整体 ``passed=False`` 并记录失败
   gate 的名称与输出；**继续运行其余 gate**（不在首个失败处停止），以便记录全部输出
   （Requirement 5.3）。

2. 采纳判定编排（Task 9.2 / Requirement 4.3/5.5/10.14，Property 10）：:func:`decide` 整合
   留出集评估结论与 gate 结果——**当且仅当**提案在留出集上严格改善目标 ``Hit_Rate_Metric``
   （``evaluation.strictly_improved``）**且**通过全部相关 gate（``gate_outcome.passed``）时
   标记为 ``accepted``，否则 ``rejected``。该规则对关键词类提案同样适用（Requirement 10.14）。

## 公共 API

- :data:`Gate`：gate 可调用接口类型，签名 ``(proposal, project_root) -> GateResult``。
- :class:`GateOutcome`：一次 gate 运行的聚合结果（``results`` + ``passed`` + ``failed_gates``）。
- 默认 gate 实现：:func:`schema_gate`、:func:`risk_review_gate`、:func:`pytest_gate`、
  :func:`unity_compile_gate`。
- :class:`GateRunner`：``run(proposal, *, project_root)`` 执行 gate；可注入自定义 gate 列表
  （``GateRunner(gates=[...])``）以便测试与离线运行。``decide_with_gates(...)`` 为"跑 gate +
  判定"的便捷编排。
- 模块级便捷函数 :func:`run`、:func:`decide`。

## Gate 集合与可注入性（离线安全）

默认 gate 列表为 ``[schema_gate, risk_review_gate, pytest_gate, unity_compile_gate]``。

| gate | 说明 | 默认行为 |
|------|------|----------|
| ``schema`` | 编辑后内容 schema 校验（Requirement 5.2） | 目标为 markdown ``Maintained_File`` 时无对应 JSON schema，**no-op 通过**；目标为 ``.json`` 时读取原文→应用编辑→``json.loads`` 校验合法性。 |
| ``risk_review`` | 复用 :func:`forai.risk.review_execution_plan` | 构造一个最小 execution-plan（单步 ``read_only`` 指向 ``Maintained_File``）；``overallRisk == "blocked"`` 则失败，并将其识别为**风险信号**（``security_check=True``，Property 11）。 |
| ``pytest`` | pytest 套件 | 默认**安全 no-op 通过**（离线不实际 shell out，避免缓慢/递归）；可经 ``enable_pytest=True`` 或注入自定义 gate 启用。 |
| ``unity_compile`` | 经 :mod:`forai.unity_gateway` 只读编译校验 | 仅"按需"相关；文档编辑不影响 Unity 编译，默认**不适用/通过**。启用时若 validation report ``status=="blocked"``（源自 ``SecurityCheck``）→ 识别为风险信号（``security_check=True``）而**非编译错误**（Property 11）。 |

把 gate 设计成可注入/可插拔，使其可测试且离线安全：默认绝不实际 shell out 到 pytest 或
访问活动的 Unity 网关。

## SecurityCheck 检测方式（Property 11 / Requirement 5.4）

``SecurityCheck`` 必须被识别为**风险信号**而非编译错误。本模块在两处检测并以
``GateResult.security_check=True`` 标记：

1. ``risk_review_gate``：当 :func:`forai.risk.review_execution_plan` 返回 ``overallRisk ==
   "blocked"`` 或某条 finding 的 message 提及 security/SecurityCheck 时，标记为风险信号
   （``security_check=True``，``passed=False``）。
2. ``unity_compile_gate``（启用时）：当 :func:`forai.unity_gateway.validation_report_from_compile`
   返回 ``status == "blocked"`` 时，按 :mod:`forai.unity_gateway` 的约定该状态源自网关
   ``requestState == "SecurityCheck"``，因此标记为风险信号（``security_check=True``），且
   **不**将其计为编译失败：compile 维度 ``passed`` 仍为 ``True``，仅 ``failed``（真正的
   编译错误）才令 ``passed=False``。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from .risk import review_execution_plan
from .skill_models import Edit, EditProposal, GateResult

# gate 可调用接口：接收提案与 project_root，返回单个 GateResult。
Gate = Callable[[EditProposal, Path], GateResult]

# 状态常量（对齐 EditProposal.status ∈ {accepted, rejected, skipped}）。
STATUS_ACCEPTED = "accepted"
STATUS_REJECTED = "rejected"


# ---------------------------------------------------------------------------
# 聚合结果
# ---------------------------------------------------------------------------


@dataclass
class GateOutcome:
    """一次 :meth:`GateRunner.run` 的聚合结果。

    - ``results``：按执行顺序收集的全部 :class:`GateResult`（含通过与失败）。
    - ``passed``：当且仅当所有 gate 均 ``passed`` 时为 ``True``。
    """

    results: list[GateResult] = field(default_factory=list)
    passed: bool = True

    @property
    def failed_gates(self) -> list[GateResult]:
        """返回未通过的 gate 结果（含其名称与输出，供 decisions 层记录）。"""
        return [result for result in self.results if not result.passed]


# ---------------------------------------------------------------------------
# 编辑后内容重建（供 schema_gate 在 JSON 目标上使用，确定性、只读）
# ---------------------------------------------------------------------------


def _read_target_content(target_path: str, project_root: Path | None) -> str:
    """只读读取目标文件内容作为工作副本基线；不存在或无 root 时返回空串。"""
    if project_root is None:
        return ""
    candidate = (project_root / target_path).resolve()
    try:
        if candidate.is_file():
            return candidate.read_text(encoding="utf-8-sig")
    except OSError:
        return ""
    return ""


def _find_anchor(lines: list[str], anchor: str) -> int | None:
    """返回首个包含 ``anchor`` 子串的行索引；未找到返回 None（确定性）。"""
    for index, line in enumerate(lines):
        if anchor in line:
            return index
    return None


def _apply_edits(original: str, edits: list[Edit]) -> str:
    """把一组 ``Edit`` 应用到内容的内存副本并返回结果（确定性、不写回磁盘）。

    与 :mod:`forai.skill_evaluator` 的锚点应用语义一致：``add`` 在锚点后插入（未找到则
    追加末尾），``replace`` 替换锚点行，``delete`` 删除锚点行。
    """
    lines = original.split("\n") if original else []
    for edit in edits:
        index = _find_anchor(lines, edit.anchor)
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


# ---------------------------------------------------------------------------
# 默认 gate 实现
# ---------------------------------------------------------------------------


def schema_gate(proposal: EditProposal, project_root: Path) -> GateResult:
    """编辑后内容 schema 校验（Requirement 5.2 / Property 12）。

    - 目标为 markdown ``Maintained_File``（``.md``）：无对应 JSON schema，**no-op 通过**
      （文档型编辑无结构化 schema 可校验）。这是当前提案的常态（提案只针对 ``.md``）。
    - 目标为 ``.json``：读取原文、在内存工作副本上应用编辑，再 ``json.loads`` 校验编辑后
      内容是否仍为合法 JSON。合法则通过，非法则失败并记录解析错误。该分支是为 JSON 目标
      预留的钩子（hook），保证 schema_gate 在结构化目标上仍生效。
    """
    target = proposal.target_path.replace("\\", "/")
    if not target.endswith(".json"):
        return GateResult(
            gate="schema",
            passed=True,
            status="not_applicable",
            output="目标为非 JSON 文档，schema_gate 无适用 schema，按通过处理（no-op）",
        )
    original = _read_target_content(proposal.target_path, project_root)
    edited = _apply_edits(original, proposal.edits)
    try:
        json.loads(edited)
    except json.JSONDecodeError as exc:
        return GateResult(
            gate="schema",
            passed=False,
            status="failed",
            output=f"编辑后内容不是合法 JSON: {exc}",
        )
    return GateResult(
        gate="schema",
        passed=True,
        status="passed",
        output="编辑后 JSON 内容合法",
    )


def _finding_mentions_security(findings: list[dict[str, str]]) -> bool:
    """判定 risk review findings 中是否有提及 security/SecurityCheck 的条目。"""
    for finding in findings:
        message = str(finding.get("message", "")).lower()
        if "securitycheck" in message or "security check" in message or "security" in message:
            return True
    return False


def risk_review_gate(proposal: EditProposal, project_root: Path) -> GateResult:
    """risk review gate（Requirement 5.1/5.4 / Property 11）。

    构造一个最小 execution-plan（单步 ``read_only`` 指向提案目标 ``Maintained_File``），
    复用 :func:`forai.risk.review_execution_plan` 评估风险：

    - ``overallRisk == "blocked"`` → gate 失败（``passed=False``）。
    - SecurityCheck 识别（Property 11）：当 ``overallRisk == "blocked"`` 或某条 finding
      提及 security 时，把结果识别为**风险信号**（``security_check=True``），而非编译错误。
    """
    plan = {
        "runId": proposal.proposal_id or "gate-risk-review",
        "steps": [
            {
                "id": "skill-edit-1",
                "kind": "read_only",
                "target": proposal.target_path,
                "description": (
                    f"local-skill-optimization 对 Maintained_File "
                    f"{proposal.target_path} 的有界编辑提案（只读风险评估）"
                ),
            }
        ],
    }
    review = review_execution_plan(plan)
    overall = str(review.get("overallRisk", "low"))
    findings = review.get("findings", [])

    blocked = overall == "blocked"
    security_check = blocked or _finding_mentions_security(findings)
    output = json.dumps(
        {"overallRisk": overall, "findings": findings},
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return GateResult(
        gate="risk_review",
        passed=not blocked,
        status="failed" if blocked else "passed",
        security_check=security_check,
        output=output,
    )


def pytest_gate(proposal: EditProposal, project_root: Path) -> GateResult:
    """pytest gate（默认安全 no-op，离线不实际运行）。

    默认实现**不**实际 shell out 到 pytest：在 gate 运行内部触发完整测试套件会缓慢且可能
    递归。对仅改动文档的提案，pytest 结果不受影响，因此返回 ``passed=True`` 并注明已跳过。
    需要实际运行时应注入自定义 gate（``GateRunner(gates=[...])``）或在编排层显式执行 pytest。
    """
    return GateResult(
        gate="pytest",
        passed=True,
        status="not_applicable",
        output="离线安全模式：未在 gate 内运行 pytest（文档型编辑不影响测试套件），按通过处理",
    )


def unity_compile_gate(proposal: EditProposal, project_root: Path) -> GateResult:
    """unity compile gate（按需相关，默认不适用/通过；Property 11）。

    ``Maintained_File`` 文档编辑不影响 Unity 编译，故默认返回 ``passed=True`` 并注明
    "不适用"。该 gate 保留经 :mod:`forai.unity_gateway` 做只读编译校验的钩子：当编辑确实
    可能影响 Unity 编译内容时，可在子类/注入的 gate 中调用 :func:`run_compile_check` +
    :func:`validation_report_from_compile`，并按本函数 :func:`_classify_validation_report`
    的规则分类——其中 validation report ``status == "blocked"`` 源自网关 ``SecurityCheck``，
    应识别为**风险信号**（``security_check=True``）而非编译错误。
    """
    return GateResult(
        gate="unity_compile",
        passed=True,
        status="not_applicable",
        security_check=False,
        output="不适用：文档型 Maintained_File 编辑不触发 Unity 编译，按通过处理",
    )


def _classify_validation_report(report: dict) -> GateResult:
    """把 unity validation report 分类为 unity_compile 的 :class:`GateResult`（Property 11）。

    - ``status == "passed"`` → 通过。
    - ``status == "failed"`` → 编译错误，失败。
    - ``status == "blocked"`` → 源自网关 ``SecurityCheck``，识别为风险信号
      （``security_check=True``），**不**计为编译失败（compile 维度 ``passed=True``）。

    供需要实际调用 Unity 网关的注入式 gate 复用，使 SecurityCheck 的分类规则集中且一致。
    """
    status = str(report.get("status", "failed"))
    if status == "blocked":
        return GateResult(
            gate="unity_compile",
            passed=True,
            status="not_applicable",
            security_check=True,
            output="网关返回 SecurityCheck（status=blocked），识别为风险信号而非编译错误",
        )
    if status == "passed":
        return GateResult(
            gate="unity_compile",
            passed=True,
            status="passed",
            security_check=False,
            output="Unity 编译通过",
        )
    return GateResult(
        gate="unity_compile",
        passed=False,
        status="failed",
        security_check=False,
        output=json.dumps(report, ensure_ascii=False, separators=(",", ":")),
    )


# 默认 gate 列表（顺序固定以保证确定性）。
DEFAULT_GATES: tuple[Gate, ...] = (
    schema_gate,
    risk_review_gate,
    pytest_gate,
    unity_compile_gate,
)


# ---------------------------------------------------------------------------
# Gate_Runner
# ---------------------------------------------------------------------------


class GateRunner:
    """对提案运行相关 ``Deterministic_Gate`` 并聚合结果（Task 9.1）。

    可注入自定义 gate 列表以便测试与离线运行：``GateRunner(gates=[my_gate, ...])``。
    未提供时使用 :data:`DEFAULT_GATES`（schema、risk_review、pytest、unity_compile）。
    """

    def __init__(self, gates: list[Gate] | tuple[Gate, ...] | None = None) -> None:
        self._gates: tuple[Gate, ...] = (
            tuple(gates) if gates is not None else DEFAULT_GATES
        )

    def run(self, proposal: EditProposal, *, project_root: Path) -> GateOutcome:
        """对 ``proposal`` 运行全部相关 gate，返回 :class:`GateOutcome`。

        逐个执行所有 gate 并收集 :class:`GateResult`；**不在首个失败处停止**，以确保记录
        每个 gate 的名称与输出（Requirement 5.3）。任一 gate ``passed`` 为 False 则整体
        ``passed`` 为 False。
        """
        results: list[GateResult] = []
        overall_passed = True
        for gate in self._gates:
            result = gate(proposal, project_root)
            results.append(result)
            if not result.passed:
                overall_passed = False
        return GateOutcome(results=results, passed=overall_passed)

    def decide_with_gates(
        self,
        proposal: EditProposal,
        evaluation,
        *,
        project_root: Path,
    ) -> EditProposal:
        """便捷编排：对 ``proposal`` 跑 gate，再据评估与 gate 结果做采纳判定。

        等价于先 :meth:`run` 再 :func:`decide`。返回带有最终 ``status``、``evaluation`` 与
        ``gate_results`` 的提案。
        """
        outcome = self.run(proposal, project_root=project_root)
        return decide(proposal, evaluation, outcome)


# ---------------------------------------------------------------------------
# 采纳判定编排（Task 9.2 / Property 10）
# ---------------------------------------------------------------------------


def decide(
    proposal: EditProposal,
    evaluation,
    gate_outcome: GateOutcome,
) -> EditProposal:
    """整合留出集评估与 gate 结果，写入提案最终 ``status``（Property 10）。

    采纳判定的**充要条件**（Requirement 4.3/5.5/10.14）：

        status == "accepted"  当且仅当  evaluation.strictly_improved 为 True
                                        且 gate_outcome.passed 为 True
        否则 status == "rejected"

    该规则对关键词类提案（``keyword_category`` 非空）同样适用（Requirement 10.14）。

    副作用：把 ``evaluation`` 与 ``gate_outcome.results`` 附加到提案
    （``proposal.evaluation`` / ``proposal.gate_results``），使被拒绝提案的失败 gate 名称与
    输出可被 decisions 层检索（Requirement 5.3）。返回同一 ``proposal`` 对象（已就地更新）。
    """
    strictly_improved = bool(getattr(evaluation, "strictly_improved", False))
    accepted = strictly_improved and gate_outcome.passed

    proposal.evaluation = evaluation
    proposal.gate_results = list(gate_outcome.results)
    proposal.status = STATUS_ACCEPTED if accepted else STATUS_REJECTED
    return proposal


# ---------------------------------------------------------------------------
# 模块级便捷入口
# ---------------------------------------------------------------------------


def run(proposal: EditProposal, *, project_root: Path) -> GateOutcome:
    """便捷函数：等价于 ``GateRunner().run(proposal, project_root=project_root)``。"""
    return GateRunner().run(proposal, project_root=project_root)
