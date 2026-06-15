"""端到端集成测试：local-skill-optimization 完整闭环（Task 14.1）。

本测试在一个临时 workspace（``tmp_path``）中模拟两层闭环的完整链路：

1. 构造多条 ``Run_History``（5 条），其中候选关键词 ``roslyn-gateway`` 跨多条历史复现，
   且 risk-review 在每条历史中均被阻断，使 ``execution_plan_unblocked_rate`` 与
   ``preflight_first_pass_rate`` 低于配置阈值（触发提案生成）。
2. 逐条 ``skill harvest`` → 断言 ``Signal_Ledger`` append-only 累积、关键词复现达阈值。
3. ``skill optimize`` → 串联 Metrics_Engine→Proposal_Generator→HeldOut_Evaluator→
   Gate_Runner→Adoption_Stager，产出 ``metrics-report.json`` / ``proposal-decisions.json`` /
   ``adoption-stage.json``，并断言证据可被对应 JSON schema 校验（Requirement 8.1）。
4. ``skill proposals`` → 断言暂存提案被列出（Requirement 9.2）。
5. ``skill adopt``：无 ``--confirm`` 时拒绝且不改文件；带 ``--confirm`` 时把 diff 应用到临时
   ``Maintained_File`` 副本（Requirements 6.4, 9.3）。

通过子进程驱动 ``tools/ai/ai.py``（与 ``test_cli.py`` 约定一致），并用 ``--project-root``
指向临时 workspace，从而真实地行使 CLI 契约（Requirements 9.1, 9.2, 9.3）。schema 校验从
``<tmp>/tools/ai/schemas/`` 读取，故测试把真实 schema 目录整体复制到临时 workspace。

_Requirements: 9.1, 9.2, 9.3, 6.4, 8.1_
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from forai.paths import find_project_root, schema_dir
from forai.schemas import load_schema, validate_payload

# 候选关键词：命中 capability hints → category capability_registry，
# 映射目标 Maintained_File 为 docs/ai/capability-registry.md，锚点 "## 能力关键词"。
KEYWORD = "roslyn-gateway"
CAPABILITY_TARGET = "docs/ai/capability-registry.md"
CAPABILITY_ANCHOR = "## 能力关键词"

# 5 条 Run_History 的 run-id（含时间戳，供窗口/排序确定性派生）。
RUN_IDS = [
    "change-20260601-100000",
    "change-20260602-100000",
    "change-20260603-100000",
    "change-20260604-100000",
    "change-20260605-100000",
]

OPT_RUN_ID = "skill-opt-itest-001"


# ---------------------------------------------------------------------------
# CLI 驱动辅助（与 test_cli.py 约定一致）
# ---------------------------------------------------------------------------


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    """以子进程方式调用 tools/ai/ai.py，cwd 为真实 repo 根，PYTHONPATH 指向 forai 包。"""
    root = find_project_root()
    env = os.environ.copy()
    env["PYTHONPATH"] = str(root / "tools" / "ai")
    return subprocess.run(
        [sys.executable, str(root / "tools" / "ai" / "ai.py"), *args],
        cwd=str(root),
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def parse_stdout(completed: subprocess.CompletedProcess[str]) -> dict:
    assert completed.stdout.strip(), completed.stderr
    return json.loads(completed.stdout)


# ---------------------------------------------------------------------------
# 临时 workspace 搭建
# ---------------------------------------------------------------------------


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def setup_project(tmp_path: Path) -> Path:
    """在 tmp_path 下构建临时 workspace：ProjectVersion、复制 schema、写入 Maintained_File。"""
    project_root = tmp_path / "workspace"
    # Unity 项目标识文件（非必需，但贴近真实结构）。
    write_text(project_root / "ProjectSettings" / "ProjectVersion.txt", "m_EditorVersion: 2022.3.62f2\n")

    # 把真实 schema 目录整体复制到临时 workspace（schema 校验从此处读取）。
    real_schema_dir = schema_dir(find_project_root())
    target_schema_dir = schema_dir(project_root)
    target_schema_dir.mkdir(parents=True, exist_ok=True)
    for schema_file in real_schema_dir.glob("*.json"):
        shutil.copy2(schema_file, target_schema_dir / schema_file.name)

    # 创建目标 Maintained_File（含提案生成器使用的锚点），供 skill adopt 落盘。
    write_text(
        project_root / CAPABILITY_TARGET,
        "# 能力注册表\n\n## 能力关键词\n\n- existing-capability\n",
    )
    return project_root


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def seed_run_histories(project_root: Path) -> None:
    """写入 5 条 Run_History。

    每条历史：risk-review 阻断（使 execution_plan/preflight 命中率为 0），requirement-check
    ready（无澄清往返），validation-report 含 unity-compile passed，intent-analysis 的
    domain/goal 携带复现关键词 roslyn-gateway。
    """
    runs_root = project_root / "artifacts" / "ai-runs"
    for index, run_id in enumerate(RUN_IDS):
        run_dir = runs_root / run_id
        ts = f"2026-06-0{index + 1}T10:00:00Z"
        write_json(
            run_dir / "workflow-state.json",
            {
                "version": "workflow-state/v2",
                "runId": run_id,
                "profile": "change",
                "status": "initialized",
                "blockers": [],
                "startedAtUtc": ts,
                "updatedAtUtc": ts,
            },
        )
        write_json(
            run_dir / "risk-review.json",
            {
                "version": "risk-review/v1",
                "runId": run_id,
                "overallRisk": "blocked",
                "findings": [{"risk": "blocked", "message": "blocked for itest"}],
            },
        )
        write_json(
            run_dir / "requirement-check.json",
            {"version": "requirement-check/v1", "status": "ready"},
        )
        write_json(
            run_dir / "intent-analysis.json",
            {
                "version": "intent-analysis/v1",
                "domain": KEYWORD,
                "goal": KEYWORD,
                "requestedChanges": [],
            },
        )
        write_json(
            run_dir / "validation-report.json",
            {
                "version": "validation-report/v1",
                "runId": run_id,
                "status": "passed",
                "checks": [{"name": "unity-compile", "status": "passed"}],
            },
        )


# ---------------------------------------------------------------------------
# 端到端集成测试
# ---------------------------------------------------------------------------


def test_skill_optimization_end_to_end(tmp_path: Path) -> None:
    project_root = setup_project(tmp_path)
    seed_run_histories(project_root)
    root_arg = str(project_root)

    # --- 1. 多次 harvest：断言 ledger append-only 累积 ---
    ledger_path = (
        project_root / "artifacts" / "ai-runs" / "skill-ledger" / "signal-ledger.json"
    )
    for expected_total, run_id in enumerate(RUN_IDS, start=1):
        result = run_cli("skill", "harvest", "--run-id", run_id, "--project-root", root_arg)
        assert result.returncode == 0, result.stderr
        payload = parse_stdout(result)
        assert payload["status"] == "passed"
        # 候选关键词被采集（capability_registry 类别）。
        terms = {kw["term"] for kw in payload["signal"]["candidateKeywords"]}
        assert KEYWORD in terms
        # ledger append-only 增长：entries 数等于已 harvest 次数。
        ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
        assert len(ledger["entries"]) == expected_total
        assert payload["progress"]["totalRuns"] == expected_total

    # --- 2. skill ledger：达阈值，关键词跨历史复现 5 次 ---
    ledger_result = run_cli("skill", "ledger", "--project-root", root_arg)
    assert ledger_result.returncode == 0, ledger_result.stderr
    ledger_payload = parse_stdout(ledger_result)
    assert ledger_payload["progress"]["thresholdMet"] is True
    assert ledger_payload["keywordCounts"][KEYWORD]["occurrences"] == len(RUN_IDS)
    assert ledger_payload["keywordCounts"][KEYWORD]["category"] == "capability_registry"
    assert "triggerCondition" in ledger_payload

    # --- 3. skill optimize：产出证据，至少一个 accepted+staged 提案 ---
    # 固定 seed=1337 时训练集为 3 条、验证集为 2 条；提案证据应只来自训练集 ledger。
    optimize_result = run_cli(
        "skill", "optimize", "--run-id", OPT_RUN_ID, "--project-root", root_arg
    )
    assert optimize_result.returncode == 0, optimize_result.stderr
    optimize_payload = parse_stdout(optimize_result)
    assert optimize_payload["status"] == "passed"
    assert optimize_payload["runId"] == OPT_RUN_ID
    counts = optimize_payload["proposalCounts"]
    assert counts["accepted"] >= 1
    assert counts["staged"] >= 1

    # 证据文件存在且可被对应 schema 校验（Requirement 8.1 / 8.3）。
    opt_dir = project_root / "artifacts" / "ai-runs" / OPT_RUN_ID
    metrics_path = opt_dir / "metrics-report.json"
    decisions_path = opt_dir / "proposal-decisions.json"
    stage_path = opt_dir / "adoption-stage.json"
    assert metrics_path.is_file()
    assert decisions_path.is_file()
    assert stage_path.is_file()

    validate_payload(
        load_schema(project_root, "skill-metrics/v1"),
        json.loads(metrics_path.read_text(encoding="utf-8")),
    )
    validate_payload(
        load_schema(project_root, "skill-proposal-decisions/v1"),
        json.loads(decisions_path.read_text(encoding="utf-8")),
    )
    validate_payload(
        load_schema(project_root, "skill-adoption-stage/v1"),
        json.loads(stage_path.read_text(encoding="utf-8")),
    )

    # 至少一个低于阈值的指标（确认提案生成的前置条件成立）。
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    metric_values = {m["id"]: m["value"] for m in metrics["metrics"]}
    assert metric_values["execution_plan_unblocked_rate"] == 0.0

    # --- 4. skill proposals：列出暂存提案 ---
    proposals_result = run_cli(
        "skill", "proposals", "--run-id", OPT_RUN_ID, "--project-root", root_arg
    )
    assert proposals_result.returncode == 0, proposals_result.stderr
    proposals_payload = parse_stdout(proposals_result)
    staged = proposals_payload["stagedProposals"]
    assert len(staged) >= 1
    # 找到目标为 capability-registry 的暂存提案。
    capability_staged = next(
        (item for item in staged if item["targetPath"] == CAPABILITY_TARGET), None
    )
    assert capability_staged is not None, staged
    decisions = json.loads(decisions_path.read_text(encoding="utf-8"))
    capability_decision = next(
        item
        for item in decisions["decisions"]
        if item["targetPath"] == CAPABILITY_TARGET
    )
    assert "3 条历史中复现" in capability_decision["reason"]
    proposal_id = capability_staged["proposalId"]

    target_file = project_root / CAPABILITY_TARGET
    content_before = target_file.read_text(encoding="utf-8")

    # --- 5a. skill adopt 无 --confirm：拒绝，不改文件 ---
    refuse_result = run_cli(
        "skill",
        "adopt",
        "--run-id",
        OPT_RUN_ID,
        "--proposal-id",
        proposal_id,
        "--project-root",
        root_arg,
    )
    assert refuse_result.returncode == 1
    refuse_payload = parse_stdout(refuse_result)
    assert refuse_payload["status"] == "failed"
    assert target_file.read_text(encoding="utf-8") == content_before

    # --- 5b. skill adopt --confirm：落盘到临时 Maintained_File 副本 ---
    adopt_result = run_cli(
        "skill",
        "adopt",
        "--run-id",
        OPT_RUN_ID,
        "--proposal-id",
        proposal_id,
        "--confirm",
        "--project-root",
        root_arg,
    )
    assert adopt_result.returncode == 0, adopt_result.stderr
    adopt_payload = parse_stdout(adopt_result)
    assert adopt_payload["status"] == "passed"
    assert adopt_payload["applied"] is True
    assert adopt_payload["path"] == CAPABILITY_TARGET

    # diff 被应用：新关键词行插入到锚点之后，且原有内容保留。
    content_after = target_file.read_text(encoding="utf-8")
    assert content_after != content_before
    assert f"- {KEYWORD}" in content_after
    assert "- existing-capability" in content_after
    lines = content_after.split("\n")
    anchor_index = lines.index(CAPABILITY_ANCHOR)
    assert lines[anchor_index + 1] == f"- {KEYWORD}"
