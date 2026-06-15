"""Adoption_Stager 与运行证据产出（local-skill-optimization Layer B）。

本模块实现 ``local-skill-optimization`` 闭环的最后一段：把经留出集评估与
``Deterministic_Gate`` 校验判定为 ``accepted`` 的 :class:`~forai.skill_models.EditProposal`
**暂存**（stage）到 ``Adoption_Stage``，并在人工显式确认后将其 diff **应用**（apply）到对应
``Maintained_File``；同时在一次 ``Optimization_Run`` 完成时产出 schema 可校验的运行证据
（``metrics-report.json`` 与 ``proposal-decisions.json``）。

涵盖任务：

- **Task 10.1 暂存与采纳应用**（Requirements 6.1-6.5、7.1、7.2、7.4、8.2；Property 13/14/15/16/17、
  Property 9 采纳阶段）。
- **Task 10.2 提案决策记录与运行证据产出**（Requirements 8.1-8.3；Property 12/14）。

## 公共 API

- :class:`AdoptionStager`（绑定 ``project_root``）：
  - :meth:`AdoptionStager.stage` —— 把 accepted 提案写入
    ``artifacts/ai-runs/<run-id>/adoption-stage.json``，**不修改** ``Maintained_File``（Property 13）。
  - :meth:`AdoptionStager.apply` —— 仅在 ``confirm=True`` 时应用 diff 到 ``Maintained_File``
    （Property 15）；锚点 checksum 失配则拒绝并提示重新生成（Property 16）；``Protected_Path``
    二次拦截（Property 9）；写目标限定 workspace 内（Property 17）。
- :class:`ApplyResult` —— :meth:`AdoptionStager.apply` 的结果（``applied`` / ``path`` / ``message``）。
- :class:`AdoptionError` —— 暂存/采纳阶段的拒绝与错误。
- 模块级 :func:`render_diff` —— 由一组 :class:`~forai.skill_models.Edit` 生成确定性 diff 文本。
- 模块级 :func:`compute_anchor_checksum` —— 计算目标文件当前内容的锚点 checksum。
- 模块级 :func:`build_decisions` —— 由提案列表构建 :class:`~forai.skill_models.ProposalDecisions`。
- 模块级 :func:`write_run_evidence` —— 写出并 schema 校验 ``metrics-report.json`` 与
  ``proposal-decisions.json``。

## diff 文本格式（确定性，:func:`render_diff`）

为每个提案生成一段人类可读、确定性的"类 unified diff"文本（不依赖磁盘原文，纯由编辑列表
渲染，便于审阅与 round-trip）。整体形如::

    --- a/<targetPath>
    +++ b/<targetPath>
    @@ <type> @@ anchor: <anchor>
    +<newText 行>            # add：在锚点后新增的行（每行前缀 "+"）
    @@ <type> @@ anchor: <anchor>
    -<anchor>                # delete：删除锚点行（前缀 "-"）
    @@ <type> @@ anchor: <anchor>
    -<anchor>                # replace：先删旧锚点行
    +<newText 行>            # replace：再加新行

约定：
- 每个编辑产生一个 ``@@ <type> @@ anchor: <anchor>`` 头，``<type> ∈ {add, delete, replace}``。
- ``add``：``newText`` 的每一行以 ``+`` 前缀输出（语义：插入到锚点之后）。
- ``delete``：以 ``-`` 前缀输出锚点行（语义：删除该锚点行）。
- ``replace``：先以 ``-`` 前缀输出锚点行，再以 ``+`` 前缀输出 ``newText`` 的每一行。
- 行分隔统一用 ``\n``；相同输入恒产生相同 diff（确定性，支撑 Property 14 的"完整 diff"要求）。

该 diff 仅用于 ``Adoption_Stage`` 的审阅展示；真正落盘由 :meth:`AdoptionStager.apply` 基于
``staged proposal`` 对应的原始 :class:`EditProposal` 编辑做**锚点应用**完成（与
:mod:`forai.skill_evaluator` / :mod:`forai.skill_gates` 的锚点语义一致）。

## anchorChecksum 定义（:func:`compute_anchor_checksum`，Property 16 / Requirement 6.5）

``anchorChecksum`` 取目标 ``Maintained_File`` **当前完整内容**的 SHA-256 十六进制摘要
（``sha256(content.encode("utf-8"))``）。选择**整文件内容**而非单一锚点行，原因：

- 最简单、最稳健：任何对目标文件的改动（无论是否恰好触及锚点行）都会改变 checksum，从而在
  :meth:`AdoptionStager.apply` 时被检出（避免把过期 diff 应用到已变更文件）。
- 文件不存在时，内容视为空字符串 ``""``，其 sha256 为固定常量，使行为对"目标尚不存在"的场景
  仍然确定。

``apply`` 时重新计算目标当前内容的 checksum，与暂存记录的 ``anchorChecksum`` 比较：相等才应用，
否则拒绝并提示重新生成（Property 16）。

## 安全与边界强制点（集中说明）

- **暂存不落盘**（Property 13 / Requirement 6.1/6.3）：:meth:`AdoptionStager.stage` 只写
  ``adoption-stage.json``，不触碰任何 ``Maintained_File`` 字节。
- **人工确认才应用**（Property 15 / Requirement 6.4）：:meth:`AdoptionStager.apply` 在
  ``confirm`` 非真时直接抛 :class:`AdoptionError` 拒绝，不做任何写操作。
- **锚点失配拒绝**（Property 16 / Requirement 6.5）：当前 checksum 与暂存 checksum 不等时拒绝。
- **Protected_Path 二次拦截**（Property 9 / Requirement 7.2）：apply 前再次用
  :func:`forai.skill_proposals.is_protected_path` / :func:`~forai.skill_proposals.is_maintained_file`
  校验目标，命中受保护路径或非 Maintained_File 则拒绝。
- **写目标限定 workspace**（Property 17 / Requirement 7.4）：stage 与 apply 的写目标都经
  :func:`_resolve_write_target` 解析并校验位于 ``project_root`` 内，否则抛
  :class:`AdoptionError`。
- **不调用 Unity API**（Requirement 7.1）：本模块仅读写文本 ``Maintained_File`` 与 JSON 证据，
  绝不触碰 Unity 资产或网关。
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from .artifacts import artifact_dir
from .skill_models import (
    AdoptionStage,
    Edit,
    EditProposal,
    ExpectedGain,
    FailedGate,
    MetricsReport,
    ProposalDecision,
    ProposalDecisions,
    StagedProposal,
    read_model,
    validate,
    write_model,
)
from .skill_proposals import is_maintained_file, is_protected_path

# Adoption_Stage 的产物文件名（位于 artifacts/ai-runs/<run-id>/ 下）。
ADOPTION_STAGE_FILENAME = "adoption-stage.json"
METRICS_REPORT_FILENAME = "metrics-report.json"
PROPOSAL_DECISIONS_FILENAME = "proposal-decisions.json"

# 已采纳状态常量（对齐 EditProposal.status）。
STATUS_ACCEPTED = "accepted"


class AdoptionError(RuntimeError):
    """暂存/采纳阶段的拒绝或错误（缺确认、锚点失配、越界、Protected_Path 等）。"""


@dataclass
class ApplyResult:
    """:meth:`AdoptionStager.apply` 的结果。

    - ``applied``：是否真正把 diff 应用到 ``Maintained_File``。
    - ``proposal_id``：被采纳的提案标识。
    - ``path``：目标 ``Maintained_File`` 的相对路径。
    - ``message``：人类可读的结果说明。
    """

    applied: bool
    proposal_id: str
    path: str
    message: str


# ---------------------------------------------------------------------------
# diff 渲染（确定性，纯函数）
# ---------------------------------------------------------------------------


def render_diff(target_path: str, edits: list[Edit]) -> str:
    """由一组 :class:`Edit` 生成确定性的"类 unified diff"文本。

    格式见模块 docstring「diff 文本格式」。相同 ``target_path`` 与 ``edits`` 恒产生相同文本。
    """
    lines: list[str] = [f"--- a/{target_path}", f"+++ b/{target_path}"]
    for edit in edits:
        lines.append(f"@@ {edit.type} @@ anchor: {edit.anchor}")
        if edit.type == "add":
            lines.extend(f"+{line}" for line in edit.new_text.split("\n"))
        elif edit.type == "delete":
            lines.append(f"-{edit.anchor}")
        elif edit.type == "replace":
            lines.append(f"-{edit.anchor}")
            lines.extend(f"+{line}" for line in edit.new_text.split("\n"))
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 锚点 checksum 与内容读取（只读）
# ---------------------------------------------------------------------------


def _read_target_content(project_root: Path, target_path: str) -> str:
    """只读读取目标 ``Maintained_File`` 当前内容；不存在则返回空串（不创建文件）。"""
    candidate = (project_root / target_path).resolve()
    try:
        if candidate.is_file():
            return candidate.read_text(encoding="utf-8-sig")
    except OSError:
        return ""
    return ""


def compute_anchor_checksum(content: str) -> str:
    """计算目标文件当前完整内容的 SHA-256 十六进制摘要（见模块 docstring 定义）。"""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# 锚点编辑应用（与 skill_evaluator / skill_gates 语义一致，确定性）
# ---------------------------------------------------------------------------


def _find_anchor(lines: list[str], anchor: str) -> int | None:
    """返回首个包含 ``anchor`` 子串的行索引；未找到返回 None（确定性）。"""
    for index, line in enumerate(lines):
        if anchor in line:
            return index
    return None


def _apply_edits(original: str, edits: list[Edit]) -> str:
    """把一组 ``Edit`` 应用到内容副本并返回结果（确定性）。

    锚点语义与 :mod:`forai.skill_evaluator` / :mod:`forai.skill_gates` 一致：
    - ``add``：在匹配 ``anchor`` 的行之后插入 ``new_text``；锚点未找到时追加到末尾。
    - ``replace``：把匹配 ``anchor`` 的行替换为 ``new_text``；锚点未找到时不变。
    - ``delete``：删除匹配 ``anchor`` 的行；锚点未找到时不变。
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
# Adoption_Stager
# ---------------------------------------------------------------------------


@dataclass
class AdoptionStager:
    """暂存 accepted 提案并在人工确认后应用其 diff 到 ``Maintained_File``。

    绑定到 ``project_root``。所有写操作（暂存 JSON、落盘 ``Maintained_File``）都被限定在
    ``project_root`` 内（Property 17）。``stage`` 需要原始 :class:`EditProposal`（含编辑列表与
    评估结论）；``apply`` 在 ``adoption-stage.json`` 之外还需提供同名提案的原始编辑，
    因此 :meth:`stage` 会把每个提案的编辑缓存到对象上，:meth:`apply` 也支持显式传入
    ``proposals`` 以便跨进程复用。
    """

    project_root: Path

    # ------------------------------------------------------------------
    # 路径与边界
    # ------------------------------------------------------------------
    def _stage_path(self, run_id: str) -> Path:
        """返回 ``artifacts/ai-runs/<run-id>/adoption-stage.json`` 路径。"""
        return artifact_dir(self.project_root, run_id) / ADOPTION_STAGE_FILENAME

    def _resolve_write_target(self, target_path: str) -> Path:
        """解析写目标并校验位于 workspace 内（Property 17 / Requirement 7.4）。"""
        root = self.project_root.resolve()
        target = (self.project_root / target_path).resolve()
        if root != target and root not in target.parents:
            raise AdoptionError(
                f"拒绝写入 workspace 之外的目标：{target} 不在 {root} 范围内"
            )
        return target

    # ------------------------------------------------------------------
    # 暂存（Property 13/14 / Requirement 6.1/6.2/6.3/8.2）
    # ------------------------------------------------------------------
    def stage(
        self,
        proposals: list[EditProposal],
        *,
        run_id: str,
    ) -> AdoptionStage:
        """把 ``accepted`` 提案写入 ``adoption-stage.json``，不修改任何 ``Maintained_File``。

        仅纳入 ``status == "accepted"`` 的提案；为每个提案记录 ``proposalId``、``targetPath``、
        完整 ``diff``（:func:`render_diff`）、``expectedGain``（目标指标 + 评估的 after-before
        增量）、``rationale`` 与 ``anchorChecksum``（目标文件当前内容的 sha256）。

        本方法**只**写 ``adoption-stage.json``，绝不写 ``Maintained_File``（Property 13）。
        写目标经 workspace 边界校验（Property 17）。返回写入的 :class:`AdoptionStage` 模型。
        """
        staged: list[StagedProposal] = []
        for proposal in proposals:
            if proposal.status != STATUS_ACCEPTED:
                continue
            content = _read_target_content(self.project_root, proposal.target_path)
            checksum = compute_anchor_checksum(content)
            staged.append(
                StagedProposal(
                    proposal_id=proposal.proposal_id,
                    target_path=proposal.target_path,
                    diff=render_diff(proposal.target_path, proposal.edits),
                    expected_gain=_expected_gain(proposal),
                    rationale=proposal.rationale,
                    anchor_checksum=checksum,
                )
            )

        stage = AdoptionStage(run_id=run_id, staged_proposals=staged)
        # 写目标边界校验（adoption-stage.json 本身限定在 workspace 内）。
        stage_path = self._stage_path(run_id)
        root = self.project_root.resolve()
        resolved = stage_path.resolve()
        if root != resolved and root not in resolved.parents:
            raise AdoptionError(
                f"拒绝写入 workspace 之外的 Adoption_Stage：{resolved} 不在 {root} 范围内"
            )
        validate(self.project_root, stage)
        write_model(stage_path, stage)
        return stage

    # ------------------------------------------------------------------
    # 采纳应用（Property 15/16/17 / Property 9 / Requirement 6.4/6.5/7.1/7.2/7.4）
    # ------------------------------------------------------------------
    def apply(
        self,
        proposal_id: str,
        *,
        run_id: str,
        confirm: bool,
        proposals: list[EditProposal] | None = None,
    ) -> ApplyResult:
        """仅在显式确认时把指定暂存提案的 diff 应用到 ``Maintained_File``。

        强制顺序（任一未满足即抛 :class:`AdoptionError`，不做任何写操作）：

        1. **人工确认**（Property 15 / Requirement 6.4）：``confirm`` 必须为真。
        2. **定位暂存提案**：从 ``adoption-stage.json`` 按 ``proposal_id`` 查找；找不到则报错。
        3. **Protected_Path / Maintained_File 二次拦截**（Property 9 / Requirement 7.2）。
        4. **workspace 边界**（Property 17 / Requirement 7.4）：写目标解析后须在 ``project_root`` 内。
        5. **锚点 checksum 匹配**（Property 16 / Requirement 6.5）：重算目标当前内容 checksum，
           与暂存 ``anchorChecksum`` 不等则拒绝并提示重新生成。
        6. 全部通过后，应用编辑并写回 ``Maintained_File``（这是**唯一**写 ``Maintained_File`` 的
           位置，且仅在 ``confirm`` 之后）。

        编辑来源：优先使用调用方传入的 ``proposals`` 中同 ``proposal_id`` 的原始 :class:`EditProposal`
        编辑；若未提供，则从暂存 ``diff`` 解析出编辑（见 :func:`_edits_from_diff`），保证跨进程
        （仅有 ``adoption-stage.json``）也能落盘。
        """
        if not confirm:
            raise AdoptionError(
                "采纳操作需要人工显式确认（confirm=True）；未确认，拒绝执行"
            )

        stage_path = self._stage_path(run_id)
        if not stage_path.exists():
            raise AdoptionError(
                f"未找到 Adoption_Stage：{stage_path}（请先运行 skill optimize 生成暂存）"
            )
        stage: AdoptionStage = read_model(stage_path, AdoptionStage)  # type: ignore[assignment]

        staged = next(
            (item for item in stage.staged_proposals if item.proposal_id == proposal_id),
            None,
        )
        if staged is None:
            raise AdoptionError(
                f"暂存中不存在 proposalId={proposal_id!r}，无法采纳"
            )

        target_path = staged.target_path
        # 3) Protected_Path / Maintained_File 二次拦截。
        if is_protected_path(target_path):
            raise AdoptionError(
                f"目标路径 {target_path} 匹配 Protected_Path，拒绝采纳落盘"
            )
        if not is_maintained_file(target_path):
            raise AdoptionError(
                f"目标路径 {target_path} 不是 Maintained_File，拒绝采纳落盘"
            )

        # 4) workspace 边界。
        target = self._resolve_write_target(target_path)

        # 5) 锚点 checksum 匹配校验。
        current_content = _read_target_content(self.project_root, target_path)
        current_checksum = compute_anchor_checksum(current_content)
        if current_checksum != staged.anchor_checksum:
            raise AdoptionError(
                f"目标 {target_path} 内容已变更（锚点 checksum 失配），"
                "拒绝应用过期 diff，请重新生成提案（skill optimize）"
            )

        # 6) 应用编辑并落盘（唯一写 Maintained_File 的位置）。
        edits = self._resolve_edits(staged, proposals)
        updated = _apply_edits(current_content, edits)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(updated, encoding="utf-8")
        return ApplyResult(
            applied=True,
            proposal_id=proposal_id,
            path=target_path,
            message=f"已将提案 {proposal_id} 的 diff 应用到 {target_path}",
        )

    @staticmethod
    def _resolve_edits(
        staged: StagedProposal, proposals: list[EditProposal] | None
    ) -> list[Edit]:
        """确定本次落盘要应用的编辑：优先用原始提案，否则从暂存 diff 解析。"""
        if proposals is not None:
            match = next(
                (p for p in proposals if p.proposal_id == staged.proposal_id), None
            )
            if match is not None:
                return list(match.edits)
        return _edits_from_diff(staged.diff)


# ---------------------------------------------------------------------------
# diff → edits 解析（与 render_diff 互逆，确定性）
# ---------------------------------------------------------------------------


def _edits_from_diff(diff: str) -> list[Edit]:
    """从 :func:`render_diff` 生成的 diff 文本解析回 :class:`Edit` 列表（确定性）。

    解析 ``@@ <type> @@ anchor: <anchor>`` 头与随后的 ``+``/``-`` 行，重建编辑：
    - ``add``：收集所有 ``+`` 行（去前缀）作为 ``new_text``。
    - ``delete``：无 ``new_text``。
    - ``replace``：收集 ``+`` 行作为 ``new_text``（忽略 ``-`` 的旧锚点行）。

    ``changed_lines`` 取 ``new_text`` 的行数（delete 为 1，与 render 对称）。
    """
    edits: list[Edit] = []
    lines = diff.split("\n")
    index = 0
    header_prefix = "@@ "
    while index < len(lines):
        line = lines[index]
        if line.startswith(header_prefix) and " @@ anchor: " in line:
            # 解析头：@@ <type> @@ anchor: <anchor>
            body = line[len(header_prefix):]
            type_part, anchor_part = body.split(" @@ anchor: ", 1)
            edit_type = type_part.strip()
            anchor = anchor_part
            index += 1
            added: list[str] = []
            while index < len(lines) and not lines[index].startswith(header_prefix):
                content_line = lines[index]
                if content_line.startswith("+"):
                    added.append(content_line[1:])
                index += 1
            if edit_type == "delete":
                new_text = ""
                changed = 1
            else:
                new_text = "\n".join(added)
                changed = len(added) if added else 1
            edits.append(
                Edit(
                    type=edit_type,
                    anchor=anchor,
                    new_text=new_text,
                    changed_lines=changed,
                )
            )
        else:
            index += 1
    return edits


# ---------------------------------------------------------------------------
# expectedGain 推导
# ---------------------------------------------------------------------------


def _expected_gain(proposal: EditProposal) -> ExpectedGain:
    """由提案的留出集评估推导预期收益（target metric + after-before 增量）。

    若提案无 ``evaluation``，则 ``delta`` 取 0.0（无可量化增量）。
    """
    if proposal.evaluation is not None:
        delta = (
            proposal.evaluation.validation_delta_after
            - proposal.evaluation.validation_delta_before
        )
    else:
        delta = 0.0
    return ExpectedGain(target_metric=proposal.target_metric, delta=delta)


# ---------------------------------------------------------------------------
# 提案决策记录构建（Task 10.2 / Property 14）
# ---------------------------------------------------------------------------


def build_decisions(
    run_id: str,
    proposals: list[EditProposal],
    rejected: list[EditProposal] | None = None,
) -> ProposalDecisions:
    """由提案列表构建 :class:`ProposalDecisions`，捕获每个提案最终状态及理由。

    参数：
    - ``proposals``：经评估/gate 判定的提案（``status ∈ {accepted, rejected, skipped}``）。
    - ``rejected``：可选的、在生成阶段即被拒（Protected_Path / 非 Maintained_File）的提案，
      其 ``status`` 一般已为 ``rejected``。

    对每个提案：
    - ``reason`` 取提案 ``rationale``；对 ``rejected`` 提案，若其携带失败 gate，则汇总失败 gate
      名称到理由并填充 ``failed_gates``（Requirement 5.3），否则按"留出集未严格改善/被拦截"说明。
    - ``failed_gates`` 取提案 ``gate_results`` 中 ``passed == False`` 的项（gate 名 + 输出）。

    每个提案恰好产生一条 :class:`ProposalDecision`，状态属于 ``{accepted, rejected, skipped}``
    （Property 14）。决策按 ``proposalId`` 排序以保证确定性。
    """
    all_proposals = list(proposals) + list(rejected or [])
    decisions: list[ProposalDecision] = [
        _decision_for(proposal) for proposal in all_proposals
    ]
    decisions.sort(key=lambda d: d.proposal_id)
    return ProposalDecisions(run_id=run_id, decisions=decisions)


def _decision_for(proposal: EditProposal) -> ProposalDecision:
    """把单个提案映射为 :class:`ProposalDecision`（含失败 gate 与理由）。"""
    failed_gates: list[FailedGate] | None = None
    if proposal.gate_results:
        failures = [
            FailedGate(gate=result.gate, output=result.output or "")
            for result in proposal.gate_results
            if not result.passed
        ]
        if failures:
            failed_gates = failures

    reason = proposal.rationale
    if proposal.status == "rejected" and failed_gates:
        gate_names = ", ".join(gate.gate for gate in failed_gates)
        reason = f"{proposal.rationale}（未通过 gate: {gate_names}）"

    return ProposalDecision(
        proposal_id=proposal.proposal_id,
        status=proposal.status,
        reason=reason,
        target_path=proposal.target_path,
        target_metric=proposal.target_metric,
        failed_gates=failed_gates,
    )


# ---------------------------------------------------------------------------
# 运行证据产出（Task 10.2 / Requirement 8.1/8.2/8.3 / Property 12/14）
# ---------------------------------------------------------------------------


def write_run_evidence(
    *,
    project_root: Path,
    run_id: str,
    metrics_report: MetricsReport,
    decisions: ProposalDecisions,
) -> tuple[Path, Path]:
    """在 ``artifacts/ai-runs/<run-id>/`` 写出并 schema 校验运行证据。

    写出 ``metrics-report.json`` 与 ``proposal-decisions.json``。两者在写盘前均经
    :func:`forai.skill_models.validate` 用各自 schema（``skill-metrics/v1`` /
    ``skill-proposal-decisions/v1``）校验，确保结构合法（Property 12 / Requirement 8.3）。

    返回 ``(metrics_path, decisions_path)``。
    """
    # 写前 schema 校验（结构不合法则抛 SchemaValidationError，不写盘）。
    validate(project_root, metrics_report)
    validate(project_root, decisions)

    base = artifact_dir(project_root, run_id)
    metrics_path = base / METRICS_REPORT_FILENAME
    decisions_path = base / PROPOSAL_DECISIONS_FILENAME
    write_model(metrics_path, metrics_report)
    write_model(decisions_path, decisions)
    return metrics_path, decisions_path
