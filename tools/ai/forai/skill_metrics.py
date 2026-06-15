"""Metrics_Engine（local-skill-optimization Layer B）：确定性命中率指标计算。

本模块实现 :class:`MetricsEngine`，从只读扫描得到的 :class:`~forai.skill_history.RunHistory`
集合确定性地计算四个 :class:`~forai.skill_models.HitRateMetric`，聚合为
:class:`~forai.skill_models.MetricsReport`，并提供 :meth:`MetricsEngine.diff_against`
计算与上一次运行同名指标的差值（``deltaFromPrevious``）。

设计约束（对齐 Requirements 2.1-2.7、8.5 与 design.md「Metrics_Engine（Layer B）」、
Property 4/5/19）：

- **按定义计算**（Property 4 / Requirements 2.1-2.4、2.6）：每个指标的 ``value`` 等于
  ``numerator / denominator``，并记录分子、分母、取值、状态与所依据的 ``runId`` 列表。
- **分母为 0 → not_applicable**（Requirement 2.5）：不输出除零结果，``value`` 置为
  ``None``、``status`` 置为 ``"not_applicable"``、``runIds`` 为空。
- **确定性**（Property 5 / Requirement 2.7）：相同输入产出完全一致的 ``MetricsReport``；
  按 ``run_id`` 排序迭代、``runIds`` 排序输出，不依赖墙钟（窗口在未显式给定时从历史
  时间戳确定性派生）。
- **指标差值**（Property 19 / Requirement 8.5）：同名指标的 ``deltaFromPrevious`` 等于
  本次 ``value`` 减去上一次 ``value``；无上一次或任一端为 ``None`` 时为 ``None``。

## 指标定义（已固定并在此说明）

四个指标的 ``id`` 与定义如下。每个指标的 ``runIds`` 为「构成分母」（即拥有相应产物）的
run-id 排序列表。

### ``preflight_first_pass_rate``（Requirement 2.1）

本项目无独立的 ``preflight`` 产物，故沿用 :mod:`forai.skill_harvester` 的同一启发式
确定性推断「preflight 是否一次通过」，保持两层一致：

- **分母**：拥有可解析 ``workflow-state.json`` 的 run（视为「发起了 preflight」）。
- **分子**：满足以下全部条件的 run —— ``workflow-state.status != "blocked"`` 且
  ``blockers`` 为空（工作流未被阻断）、risk-review 未阻断、需求澄清往返次数为 0。

### ``execution_plan_unblocked_rate``（Requirement 2.2）

- **分母**：拥有可解析 ``risk-review.json`` 的 run。
- **分子**：``risk-review.overallRisk != "blocked"`` 且无任一 finding 的 ``risk == "blocked"``
  的 run。

### ``unity_compile_first_pass_rate``（Requirement 2.3）

Unity 编译结果来自 ``validation-report.json``。``unity_gateway.validation_report_from_compile``
产出的报告含一个 ``name == "unity-compile"`` 的 check，据此确定性识别「包含 Unity 编译结果」：

- **分母**：拥有可解析 ``validation-report.json`` 且其中存在 ``name == "unity-compile"``
  的 check 的 run。该保守规则把 unity-compile 报告与一般 validation-report 区分开，
  不会把无 unity-compile check 的报告误计入分母。
- **分子**：上述 ``unity-compile`` check 的 ``status == "passed"`` 的 run（首次成功）。

### ``requirement_clarification_round_trips``（Requirements 2.4、2.6）

Requirement 2.4 将其定义为 ``requirement-check.status`` 为 ``needs_clarification`` 或
``blocked`` 的出现次数（一个 COUNT 量，而非天然的比率）。为与 Requirement 2.6「每个指标
记录 numerator/denominator/value/runIds」保持一致且确定性，本模块以如下方式表示：

- **numerator**：澄清往返出现次数 —— 即 ``requirement-check.status ∈
  {needs_clarification, blocked}`` 的 run 数（单条 Run_History 仅一份 requirement-check，
  故每个 run 贡献 0 或 1，与 Harvester 的 ``clarificationRoundTrips`` 表示一致）。
- **denominator**：拥有可解析 ``requirement-check.json`` 的 run 数。
- **value**：``numerator / denominator``（即澄清率），分母为 0 时为 ``None`` 且
  ``status == "not_applicable"``。
- **runIds**：构成分母（拥有 requirement-check）的 run-id 排序列表。

如此该 COUNT 量被一致地纳入与其它三个比率相同的 ``HitRateMetric`` 结构，``numerator``
仍保留原始出现次数以便追溯。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from .skill_history import RunHistory, ScanResult, parse_run_timestamp
from .skill_models import HitRateMetric, MetricsReport, MetricsWindow

# 指标 id 常量（与 design.md Data Models 节对齐，顺序固定以保证确定性输出）。
METRIC_PREFLIGHT_FIRST_PASS = "preflight_first_pass_rate"
METRIC_EXECUTION_PLAN_UNBLOCKED = "execution_plan_unblocked_rate"
METRIC_UNITY_COMPILE_FIRST_PASS = "unity_compile_first_pass_rate"
METRIC_REQUIREMENT_CLARIFICATION = "requirement_clarification_round_trips"

# 产物名（read_run_history 以文件名 stem 为键）。
_ARTIFACT_WORKFLOW_STATE = "workflow-state"
_ARTIFACT_RISK_REVIEW = "risk-review"
_ARTIFACT_REQUIREMENT_CHECK = "requirement-check"
_ARTIFACT_VALIDATION_REPORT = "validation-report"

# validation-report 中标识 Unity 编译结果的 check 名称（见 unity_gateway）。
_UNITY_COMPILE_CHECK = "unity-compile"


@dataclass
class _MetricTally:
    """单个指标的分子/分母累加器与构成分母的 run-id 集合。"""

    numerator: int = 0
    denominator: int = 0

    def __post_init__(self) -> None:
        self.run_ids: list[str] = []

    def add(self, run_id: str, *, hit: bool) -> None:
        """记录一个构成分母的 run；``hit`` 为 True 时同时计入分子。"""
        self.denominator += 1
        self.run_ids.append(run_id)
        if hit:
            self.numerator += 1

    def to_metric(self, metric_id: str) -> HitRateMetric:
        """转换为 :class:`HitRateMetric`；分母为 0 标记 ``not_applicable``。"""
        if self.denominator == 0:
            return HitRateMetric(
                id=metric_id,
                numerator=self.numerator,
                denominator=0,
                value=None,
                status="not_applicable",
                run_ids=[],
                delta_from_previous=None,
            )
        return HitRateMetric(
            id=metric_id,
            numerator=self.numerator,
            denominator=self.denominator,
            value=self.numerator / self.denominator,
            status="ok",
            run_ids=sorted(self.run_ids),
            delta_from_previous=None,
        )


class MetricsEngine:
    """确定性计算 ``Hit_Rate_Metric`` 并聚合为 ``Metrics_Report``。

    无状态：:meth:`compute` 与 :meth:`diff_against` 不依赖实例间共享状态，
    因此相同输入始终产出相同输出（Property 5）。
    """

    def compute(
        self,
        histories: list[RunHistory] | ScanResult,
        *,
        run_id: str,
        window: MetricsWindow | None = None,
        skipped_run_count: int = 0,
    ) -> MetricsReport:
        """从 ``Run_History`` 集合计算四个命中率指标并聚合为 ``MetricsReport``。

        参数：
        - ``histories``：已扫描的 :class:`RunHistory` 列表，或 :class:`ScanResult`。
          传入 ``ScanResult`` 时自动取其 ``histories`` 与 ``skipped_run_count``，
          ``skipped_run_count`` 参数被忽略。
        - ``run_id``：本次 ``Optimization_Run`` 的标识，写入报告。
        - ``window``：可选时间窗口；省略时从历史时间戳确定性派生（见
          :meth:`_derive_window`）。
        - ``skipped_run_count``：被整体跳过的 run 数（当 ``histories`` 为列表时使用）。

        ``includedRunCount`` 取 ``len(histories)``。指标顺序固定，``runIds`` 排序输出，
        计算具备确定性。
        """
        if isinstance(histories, ScanResult):
            run_histories = list(histories.histories)
            skipped = histories.skipped_run_count
        else:
            run_histories = list(histories)
            skipped = skipped_run_count

        # 按 run_id 排序以保证确定性迭代。
        ordered = sorted(run_histories, key=lambda h: h.run_id)

        preflight = _MetricTally()
        execution_plan = _MetricTally()
        unity_compile = _MetricTally()
        clarification = _MetricTally()

        for history in ordered:
            run_id_value = history.run_id
            artifacts = history.artifacts

            risk_blocked = _risk_review_blocked(artifacts.get(_ARTIFACT_RISK_REVIEW))
            clar_count = _clarification_count(
                artifacts.get(_ARTIFACT_REQUIREMENT_CHECK)
            )

            # preflight_first_pass_rate：分母 = 有 workflow-state 的 run。
            workflow_state = artifacts.get(_ARTIFACT_WORKFLOW_STATE)
            if isinstance(workflow_state, dict):
                workflow_blocked = _workflow_blocked(workflow_state)
                hit = (
                    not workflow_blocked
                    and not risk_blocked
                    and clar_count == 0
                )
                preflight.add(run_id_value, hit=hit)

            # execution_plan_unblocked_rate：分母 = 有 risk-review 的 run。
            risk_review = artifacts.get(_ARTIFACT_RISK_REVIEW)
            if isinstance(risk_review, dict):
                execution_plan.add(run_id_value, hit=not risk_blocked)

            # unity_compile_first_pass_rate：分母 = 含 unity-compile check 的 run。
            validation_report = artifacts.get(_ARTIFACT_VALIDATION_REPORT)
            unity_status = _unity_compile_status(validation_report)
            if unity_status is not None:
                unity_compile.add(run_id_value, hit=unity_status == "passed")

            # requirement_clarification_round_trips：分母 = 有 requirement-check 的 run。
            requirement_check = artifacts.get(_ARTIFACT_REQUIREMENT_CHECK)
            if isinstance(requirement_check, dict):
                clarification.add(run_id_value, hit=clar_count > 0)

        metrics = [
            preflight.to_metric(METRIC_PREFLIGHT_FIRST_PASS),
            execution_plan.to_metric(METRIC_EXECUTION_PLAN_UNBLOCKED),
            unity_compile.to_metric(METRIC_UNITY_COMPILE_FIRST_PASS),
            clarification.to_metric(METRIC_REQUIREMENT_CLARIFICATION),
        ]

        resolved_window = window if window is not None else _derive_window(ordered)

        return MetricsReport(
            run_id=run_id,
            window=resolved_window,
            included_run_count=len(run_histories),
            skipped_run_count=skipped,
            metrics=metrics,
        )

    def diff_against(
        self,
        current: MetricsReport,
        previous: MetricsReport | None,
    ) -> MetricsReport:
        """返回填入 ``deltaFromPrevious`` 的 ``current`` 报告（不修改入参）。

        对每个指标，``deltaFromPrevious = current.value - previous.value``（按指标 ``id``
        匹配）；当无 ``previous``、或当前/上一次任一 ``value`` 为 ``None``
        （``not_applicable``）、或上一次缺少同名指标时，置为 ``None``（Property 19）。
        """
        previous_values: dict[str, float | None] = {}
        if previous is not None:
            previous_values = {metric.id: metric.value for metric in previous.metrics}

        new_metrics: list[HitRateMetric] = []
        for metric in current.metrics:
            prev_value = previous_values.get(metric.id)
            if metric.value is None or prev_value is None:
                delta: float | None = None
            else:
                delta = metric.value - prev_value
            new_metrics.append(
                HitRateMetric(
                    id=metric.id,
                    numerator=metric.numerator,
                    denominator=metric.denominator,
                    value=metric.value,
                    status=metric.status,
                    run_ids=list(metric.run_ids),
                    delta_from_previous=delta,
                )
            )

        return MetricsReport(
            run_id=current.run_id,
            window=MetricsWindow(from_=current.window.from_, to=current.window.to),
            included_run_count=current.included_run_count,
            skipped_run_count=current.skipped_run_count,
            metrics=new_metrics,
            version=current.version,
        )


# ---------------------------------------------------------------------------
# 单 run 信号判定（确定性、容错）
# ---------------------------------------------------------------------------


def _workflow_blocked(artifact: dict[str, Any]) -> bool:
    """判定 ``workflow-state`` 是否阻断：``status == "blocked"`` 或 ``blockers`` 非空。"""
    status = str(artifact.get("status", "")).lower()
    blockers = artifact.get("blockers")
    return status == "blocked" or bool(blockers if isinstance(blockers, list) else False)


def _risk_review_blocked(artifact: Any) -> bool:
    """判定 ``risk-review`` 是否阻断；非 dict（缺失/非法）时视为未阻断。

    规则：``overallRisk == "blocked"`` 或任一 finding 的 ``risk == "blocked"``。
    """
    if not isinstance(artifact, dict):
        return False
    if str(artifact.get("overallRisk", "")).lower() == "blocked":
        return True
    findings = artifact.get("findings")
    if isinstance(findings, list):
        for finding in findings:
            if isinstance(finding, dict) and str(finding.get("risk", "")).lower() == "blocked":
                return True
    return False


def _clarification_count(artifact: Any) -> int:
    """从 ``requirement-check`` 计澄清往返：``status ∈ {needs_clarification, blocked}`` 计 1。

    非 dict（缺失/非法）时返回 0。
    """
    if not isinstance(artifact, dict):
        return 0
    status = str(artifact.get("status", "")).lower()
    return 1 if status in {"needs_clarification", "blocked"} else 0


def _unity_compile_status(artifact: Any) -> str | None:
    """返回 ``validation-report`` 中 ``unity-compile`` check 的 status；无则返回 None。

    返回 ``None`` 表示该 run 不计入 unity_compile 指标的分母（无 Unity 编译结果）。
    """
    if not isinstance(artifact, dict):
        return None
    checks = artifact.get("checks")
    if not isinstance(checks, list):
        return None
    for check in checks:
        if isinstance(check, dict) and check.get("name") == _UNITY_COMPILE_CHECK:
            status = check.get("status")
            if isinstance(status, str):
                return status
    return None


def _derive_window(histories: list[RunHistory]) -> MetricsWindow:
    """从历史时间戳确定性派生时间窗口（``YYYY-MM-DD``）。

    取所有可解析时间戳的最小/最大日期作为 ``from``/``to``；无任何可解析时间戳时
    两端均为空字符串（窗口未知，但仍是确定性的）。
    """
    timestamps: list[datetime] = []
    for history in histories:
        parsed = parse_run_timestamp(history.run_id)
        if parsed is not None:
            timestamps.append(parsed)
    if not timestamps:
        return MetricsWindow(from_="", to="")
    return MetricsWindow(
        from_=min(timestamps).strftime("%Y-%m-%d"),
        to=max(timestamps).strftime("%Y-%m-%d"),
    )
