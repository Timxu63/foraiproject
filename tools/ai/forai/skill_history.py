"""Run_History 只读扫描与读取（local-skill-optimization Layer B 地基）。

本模块负责离线、只读地枚举 ``artifacts/ai-runs/<run-id>/`` 下的运行历史，
按时间窗口或 ``runId`` 过滤，并读取每个 ``Run_History`` 中存在的结构化产物
（``workflow-state``、``risk-review``、``requirement-check``、``validation-report``、
``intent-analysis``、``execution-plan``、``context-pack``、``final-report`` 等）。

设计约束（对齐 Requirements 1.1-1.5 与 design.md「扫描覆盖与计数守恒」）：

- **只读**：仅读取文件，绝不写入、移动或删除任何 ``Run_History``（Requirement 1.3）。
- **容错**：缺失或非法 JSON 的产物被标记为 ``skipped`` 并附原因，继续处理其余记录
  （Requirement 1.2）；单条产物损坏不影响其它产物或其它 run。
- **计数守恒**：``included_run_count + skipped_run_count`` 恰好等于过滤后被考虑的 run
  目录总数（Property 1）。判定规则见 :func:`scan_run_histories` 文档。
- **排除 ledger**：``artifacts/ai-runs/skill-ledger/`` 是 Signal_Ledger 存储，不是
  run-history，枚举时被排除。

复用既有 ``forai/json_io.py`` 的 :func:`read_json`（处理 utf-8-sig）。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from .json_io import read_json

# Signal_Ledger 的存储目录名，枚举 run-history 时排除（见 design.md 数据流表）。
LEDGER_DIR_NAME = "skill-ledger"

# run-id 中嵌入的时间戳形如 ``prefix-YYYYMMDD-HHMMSS``（如 ``change-20260613-172243``）。
_TIMESTAMP_PATTERN = re.compile(r"(\d{8})-(\d{6})")

# 可选的日期窗口：(from, to)，任一端可为 None；日期字符串形如 ``2026-05-01``。
Window = tuple[str | None, str | None]


@dataclass
class RunHistory:
    """单条运行历史的只读读取结果。

    ``artifacts`` 以产物名（去掉 ``.json`` 后缀的文件名）为键，存放成功解析的
    JSON 内容。``skipped`` 记录无法解析的产物及原因，每项形如
    ``{"artifact": <name>, "reason": <str>}``。
    """

    run_id: str
    path: Path
    artifacts: dict[str, Any] = field(default_factory=dict)
    skipped: list[dict[str, str]] = field(default_factory=list)

    @property
    def timestamp(self) -> datetime | None:
        """从 ``run_id`` 解析出的时间戳；无法解析时为 ``None``。"""
        return parse_run_timestamp(self.run_id)


@dataclass
class ScanResult:
    """一次扫描的聚合结果。

    ``histories`` 仅包含「被纳入」的 :class:`RunHistory`（至少有一个可解析产物）。
    计数满足守恒：``included_run_count + skipped_run_count`` 等于过滤后被考虑的
    run 目录总数。
    """

    histories: list[RunHistory] = field(default_factory=list)
    included_run_count: int = 0
    skipped_run_count: int = 0
    # 因零个可解析产物而被整体跳过的 run 目录名及原因。
    skipped_runs: list[dict[str, str]] = field(default_factory=list)


def parse_run_timestamp(run_id: str) -> datetime | None:
    """从 ``run_id`` 中解析嵌入的 ``YYYYMMDD-HHMMSS`` 时间戳。

    形如 ``change-20260613-172243`` 返回对应 :class:`datetime`；
    形如 ``final-dry-run`` 等无可解析时间戳的名称返回 ``None``。
    """
    match = _TIMESTAMP_PATTERN.search(run_id)
    if match is None:
        return None
    try:
        return datetime.strptime(f"{match.group(1)}-{match.group(2)}", "%Y%m%d-%H%M%S")
    except ValueError:
        return None


def _parse_window_bound(value: str | None, *, is_end: bool) -> datetime | None:
    """把窗口端点（``YYYY-MM-DD`` 或完整时间戳）解析为 :class:`datetime`。

    仅给出日期时，``from`` 端取当天 00:00:00，``to`` 端取当天 23:59:59，
    使窗口对日期为闭区间。无法解析则返回 ``None``（视为该端无界）。
    """
    if not value:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            parsed = datetime.strptime(value, fmt)
        except ValueError:
            continue
        if fmt == "%Y-%m-%d" and is_end:
            return parsed.replace(hour=23, minute=59, second=59)
        return parsed
    return None


def _in_window(run_id: str, window: Window | None) -> bool:
    """判定 ``run_id`` 的时间戳是否落在窗口内。

    决策规则（确定性、在 docstring 中明确）：

    - ``window`` 为 ``None``：始终纳入（不做时间过滤）。
    - 给定窗口但 ``run_id`` 时间戳无法解析：**排除**该 run（无法证明其落在窗口内）。
    - 给定窗口且时间戳可解析：当且仅当时间戳落在 ``[from, to]`` 闭区间内才纳入；
      ``from``/``to`` 任一端为 ``None`` 时该端视为无界。
    """
    if window is None:
        return True
    timestamp = parse_run_timestamp(run_id)
    if timestamp is None:
        return False
    start = _parse_window_bound(window[0], is_end=False)
    end = _parse_window_bound(window[1], is_end=True)
    if start is not None and timestamp < start:
        return False
    if end is not None and timestamp > end:
        return False
    return True


def iter_run_dirs(project_root: Path) -> list[Path]:
    """确定性枚举 ``artifacts/ai-runs/`` 下的 run 目录（按名称排序）。

    排除 :data:`LEDGER_DIR_NAME`（Signal_Ledger 存储）。若 ``ai-runs`` 不存在，
    返回空列表。
    """
    runs_root = project_root / "artifacts" / "ai-runs"
    if not runs_root.is_dir():
        return []
    return sorted(
        (child for child in runs_root.iterdir() if child.is_dir() and child.name != LEDGER_DIR_NAME),
        key=lambda path: path.name,
    )


def read_run_history(run_dir: Path) -> RunHistory:
    """只读读取单个 run 目录下的全部 ``*.json`` 产物。

    每个产物按文件名 stem（去掉 ``.json``）作为键。缺失整目录或单个产物非法 JSON
    时不抛出异常：非法产物记入 ``skipped`` 并附原因，其余产物照常解析。
    """
    history = RunHistory(run_id=run_dir.name, path=run_dir)
    for artifact_path in sorted(run_dir.glob("*.json"), key=lambda path: path.name):
        name = artifact_path.name[: -len(".json")]
        try:
            history.artifacts[name] = read_json(artifact_path)
        except (OSError, ValueError) as error:
            history.skipped.append({"artifact": name, "reason": str(error)})
    return history


def scan_run_histories(
    project_root: Path,
    *,
    run_ids: list[str] | None = None,
    window: Window | None = None,
) -> ScanResult:
    """扫描并只读读取匹配过滤条件的全部 ``Run_History``。

    过滤：

    - ``run_ids`` 给定时，仅纳入名称在该集合中的 run 目录（Requirement 1.4）。
    - ``window`` 给定时，按 :func:`_in_window` 的规则做时间过滤（无法解析时间戳的
      run 被排除）。

    计数与纳入/跳过判定（Property 1，计数守恒）：

    - 「被考虑的总数」= 通过 ``run_ids`` 与 ``window`` 过滤后的 run 目录数。
    - 一个 run 目录**至少有一个**可解析产物 → 计入 ``included``，其内部无法解析的
      单个产物记入该 :class:`RunHistory` 的 ``skipped`` 列表。
    - 一个 run 目录**零个**可解析产物（目录为空、无 JSON、或全部产物非法）→ 整体
      计入 ``skipped``，并在 :attr:`ScanResult.skipped_runs` 记录原因。
    - 因此 ``included_run_count + skipped_run_count`` 恒等于被考虑的 run 目录总数。

    全程只读：不修改、移动或删除任何 ``Run_History``（Requirement 1.3）。
    """
    run_id_filter = set(run_ids) if run_ids is not None else None
    result = ScanResult()

    for run_dir in iter_run_dirs(project_root):
        run_id = run_dir.name
        if run_id_filter is not None and run_id not in run_id_filter:
            continue
        if not _in_window(run_id, window):
            continue

        history = read_run_history(run_dir)
        if history.artifacts:
            result.histories.append(history)
            result.included_run_count += 1
        else:
            if history.skipped:
                reason = "; ".join(
                    f"{item['artifact']}: {item['reason']}" for item in history.skipped
                )
            else:
                reason = "no readable JSON artifacts in run directory"
            result.skipped_runs.append({"runId": run_id, "reason": reason})
            result.skipped_run_count += 1

    return result
