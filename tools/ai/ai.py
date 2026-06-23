#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from forai.artifacts import artifact_dir, normalize_run_id
from forai.json_io import read_json, write_json
from forai.paths import find_project_root
from forai.request_guide import build_request_guide, validate_answers_run_id
from forai.risk import review_execution_plan
from forai.scanner import scan_context_pack
from forai.schemas import SchemaValidationError, load_schema, validate_payload
from forai.skill_adoption import (
    AdoptionError,
    AdoptionStager,
    build_decisions,
    write_run_evidence,
)
from forai.skill_evaluator import HeldOutEvaluator
from forai.skill_gates import GateRunner, decide
from forai.skill_harvester import harvest
from forai.skill_history import scan_run_histories
from forai.skill_ledger import LedgerStore
from forai.skill_metrics import MetricsEngine
from forai.skill_models import (
    AdoptionStage,
    MetricsReport,
    OptimizerConfig,
    read_model,
)
from forai.skill_proposals import ProposalGenerator
from forai.unity_gateway import gateway_status, run_compile_check, validation_report_from_compile
from forai.workflow_engine import (
    WorkflowPreflightError,
    apply_next_action,
    begin_or_resume_workflow,
    complete_workflow,
    ensure_workflow_state_v2,
    preflight_execution,
)
from forai.workflow_state import (
    add_artifact,
    create_initial_state,
    load_or_create_workflow_state,
    load_workflow_state,
    save_workflow_state,
    set_gate,
)


def print_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def resolve_project_root(value: str | None) -> Path:
    if value:
        return Path(value).resolve()
    return find_project_root()


def default_run_id(prefix: str) -> str:
    return normalize_run_id(f"{prefix}-{datetime.now().strftime('%Y%m%d-%H%M%S')}")


def validate_or_exit(project_root: Path, schema_id: str, payload: dict[str, Any]) -> None:
    validate_payload(load_schema(project_root, schema_id), payload)


def validate_workflow_state(project_root: Path, state: dict[str, Any]) -> None:
    schema_id = str(state.get("version", "workflow-state/v1"))
    validate_or_exit(project_root, schema_id, state)


def payload_run_id(payload: dict[str, Any]) -> str | None:
    run_id = payload.get("runId")
    return str(run_id) if run_id else None


def copy_artifact_to_run_dir(project_root: Path, run_id: str, name: str, source: Path) -> Path:
    suffix = source.suffix or ".json"
    destination = artifact_dir(project_root, run_id) / f"{name}{suffix}"
    if source.resolve() != destination.resolve():
        write_json(destination, read_json(source))
    return destination


def load_engine_state(project_root: Path, run_id: str) -> dict[str, Any]:
    state = load_or_create_workflow_state(project_root, run_id)
    return ensure_workflow_state_v2(project_root, state)


def handle_root(args: argparse.Namespace) -> int:
    root = find_project_root(Path(args.from_path) if args.from_path else None)
    print_json({"projectRoot": str(root)})
    return 0


def handle_workflow_init(args: argparse.Namespace) -> int:
    project_root = resolve_project_root(args.project_root)
    state = create_initial_state(project_root, args.run_id)
    validate_workflow_state(project_root, state)
    save_workflow_state(project_root, state)
    print_json(state)
    return 0


def handle_workflow_status(args: argparse.Namespace) -> int:
    project_root = resolve_project_root(args.project_root)
    state = load_workflow_state(project_root, args.run_id)
    validate_workflow_state(project_root, state)
    print_json(state)
    return 0


def handle_workflow_begin(args: argparse.Namespace) -> int:
    project_root = resolve_project_root(args.project_root)
    state = begin_or_resume_workflow(project_root, args.intent, args.profile, args.run_id)
    validate_or_exit(project_root, "workflow-state/v2", state)
    save_workflow_state(project_root, state)
    print_json(state)
    return 0


def handle_workflow_next(args: argparse.Namespace) -> int:
    project_root = resolve_project_root(args.project_root)
    state = apply_next_action(load_engine_state(project_root, args.run_id))
    validate_or_exit(project_root, "workflow-state/v2", state)
    save_workflow_state(project_root, state)
    print_json(state)
    return 0


def handle_workflow_preflight(args: argparse.Namespace) -> int:
    project_root = resolve_project_root(args.project_root)
    state = load_engine_state(project_root, args.run_id)
    try:
        payload = preflight_execution(state)
    except WorkflowPreflightError as exc:
        print_json({"status": "failed", "runId": args.run_id, "error": str(exc)})
        return 1
    print_json(payload)
    return 0


def handle_workflow_attach_artifact(args: argparse.Namespace) -> int:
    project_root = resolve_project_root(args.project_root)
    source = Path(args.input).resolve()
    payload = read_json(source)
    validate_or_exit(project_root, args.schema, payload)

    artifact_run_id = payload_run_id(payload)
    if artifact_run_id and artifact_run_id != args.run_id:
        raise ValueError(f"Artifact runId {artifact_run_id!r} does not match workflow runId {args.run_id!r}.")

    output_path = copy_artifact_to_run_dir(project_root, args.run_id, args.name, source)
    state = load_engine_state(project_root, args.run_id)
    state = add_artifact(
        state,
        args.name,
        output_path,
        args.producer,
        args.schema,
        run_id=artifact_run_id,
    )
    if state.get("version") == "workflow-state/v2":
        state = apply_next_action(state)
    validate_workflow_state(project_root, state)
    save_workflow_state(project_root, state)
    print_json(state)
    return 0


def handle_workflow_complete(args: argparse.Namespace) -> int:
    project_root = resolve_project_root(args.project_root)
    state = load_engine_state(project_root, args.run_id)
    report_path = artifact_dir(project_root, state["runId"]) / "final-report.json"
    write_json(report_path, {"runId": state["runId"], "summary": args.summary})
    state = complete_workflow(project_root, state, args.summary)
    validate_or_exit(project_root, "workflow-state/v2", state)
    save_workflow_state(project_root, state)
    print_json(state)
    return 0


def handle_validate_file(args: argparse.Namespace) -> int:
    project_root = resolve_project_root(args.project_root)
    payload = read_json(Path(args.input))
    try:
        validate_or_exit(project_root, args.schema, payload)
    except SchemaValidationError as exc:
        print_json(
            {
                "status": "failed",
                "schema": args.schema,
                "input": str(Path(args.input).resolve()),
                "error": str(exc),
            }
        )
        return 1

    print_json(
        {
            "status": "passed",
            "schema": args.schema,
            "input": str(Path(args.input).resolve()),
        }
    )
    return 0


def handle_requirements_check(args: argparse.Namespace) -> int:
    project_root = resolve_project_root(args.project_root)
    payload = read_json(Path(args.input))
    validate_or_exit(project_root, "requirement-check/v1", payload)
    print_json(
        {
            "status": payload["status"],
            "schema": "requirement-check/v1",
            "input": str(Path(args.input).resolve()),
            "questions": payload["questions"],
            "blockers": payload["blockers"],
        }
    )
    return 0


def handle_request_guide(args: argparse.Namespace) -> int:
    project_root = resolve_project_root(args.project_root)
    answers: dict[str, Any] = {}
    if args.answers:
        answers_payload = read_json(Path(args.answers))
        validate_or_exit(project_root, "request-guide-answers/v1", answers_payload)
        validate_answers_run_id(answers_payload, args.run_id)
        answers = dict(answers_payload.get("answers", {}))

    payload = build_request_guide(args.intent, answers=answers, run_id=args.run_id)
    validate_or_exit(project_root, "request-guide/v1", payload)
    print_json(payload)
    return 0


def handle_spec_validate(args: argparse.Namespace) -> int:
    project_root = resolve_project_root(args.project_root)
    payload = read_json(Path(args.input))
    validate_or_exit(project_root, "domain-spec/v1", payload)
    print_json({"status": "passed", "schema": "domain-spec/v1", "input": str(Path(args.input).resolve())})
    return 0


def handle_plan_validate(args: argparse.Namespace) -> int:
    project_root = resolve_project_root(args.project_root)
    payload = read_json(Path(args.input))
    validate_or_exit(project_root, "execution-plan/v1", payload)
    print_json({"status": "passed", "schema": "execution-plan/v1", "input": str(Path(args.input).resolve())})
    return 0


def handle_gate(args: argparse.Namespace) -> int:
    project_root = resolve_project_root(args.project_root)
    state = load_engine_state(project_root, args.run_id)
    if args.gate_status == "approved" and state.get("status") == "blocked":
        print_json(
            {
                "status": "failed",
                "error": "Cannot approve a blocked workflow. Revise the execution plan and run risk review again.",
            }
        )
        return 1
    state = set_gate(state, args.gate, args.gate_status, args.reason or "")
    if state.get("version") == "workflow-state/v2":
        state = apply_next_action(state)
    validate_workflow_state(project_root, state)
    save_workflow_state(project_root, state)
    print_json(state)
    return 0


def handle_scan_context(args: argparse.Namespace) -> int:
    project_root = resolve_project_root(args.project_root)
    payload = scan_context_pack(project_root)
    validate_or_exit(project_root, "context-pack/v1", payload)

    output_path = Path(args.out).resolve() if args.out else None
    if args.run_id and output_path is None:
        output_path = artifact_dir(project_root, args.run_id) / "context-pack.json"
    if output_path:
        write_json(output_path, payload)

    if args.run_id and output_path:
        state = load_engine_state(project_root, args.run_id)
        state = add_artifact(state, "context-pack", output_path, "scan context", "context-pack/v1")
        if state.get("version") == "workflow-state/v2":
            state = apply_next_action(state)
        validate_workflow_state(project_root, state)
        save_workflow_state(project_root, state)

    print_json(payload)
    return 0


def handle_risk_review(args: argparse.Namespace) -> int:
    project_root = resolve_project_root(args.project_root)
    plan = read_json(Path(args.plan))
    if args.run_id:
        plan["runId"] = args.run_id
    validate_or_exit(project_root, "execution-plan/v1", plan)

    review = review_execution_plan(plan)
    validate_or_exit(project_root, "risk-review/v1", review)

    output_path = Path(args.out).resolve() if args.out else None
    if args.run_id and output_path is None:
        output_path = artifact_dir(project_root, args.run_id) / "risk-review.json"
    if output_path:
        write_json(output_path, review)

    if args.run_id and output_path:
        state = load_engine_state(project_root, args.run_id)
        plan_output_path = artifact_dir(project_root, args.run_id) / "execution-plan.json"
        write_json(plan_output_path, plan)
        state = add_artifact(
            state,
            "execution-plan",
            plan_output_path,
            "risk review",
            "execution-plan/v1",
            run_id=plan["runId"],
        )
        state = add_artifact(
            state,
            "risk-review",
            output_path,
            "risk review",
            "risk-review/v1",
            run_id=review["runId"],
        )
        if review["overallRisk"] == "blocked":
            state["status"] = "blocked"
            state["blockers"] = [
                finding["message"]
                for finding in review["findings"]
                if finding["risk"] == "blocked"
            ]
        elif review["confirmationRequired"]:
            state = set_gate(state, "risk-review", "pending", "Risk review requires human approval.")
        if state.get("version") == "workflow-state/v2":
            state = apply_next_action(state)
        validate_workflow_state(project_root, state)
        save_workflow_state(project_root, state)

    print_json(review)
    return 0


def handle_unity_status(args: argparse.Namespace) -> int:
    project_root = resolve_project_root(args.project_root)
    exit_code, payload = gateway_status(project_root, timeout=args.timeout)
    print_json(payload)
    return exit_code


def handle_unity_compile(args: argparse.Namespace) -> int:
    project_root = resolve_project_root(args.project_root)
    run_id = args.run_id or default_run_id("unity-compile")
    completed = run_compile_check(project_root, timeout=args.timeout)
    report = validation_report_from_compile(run_id, completed)
    validate_or_exit(project_root, "validation-report/v1", report)

    output_path = artifact_dir(project_root, run_id) / "validation-report.json"
    write_json(output_path, report)
    state = load_or_create_workflow_state(project_root, run_id)
    state = ensure_workflow_state_v2(project_root, state, "Unity compile validation", "change")
    state = add_artifact(
        state,
        "validation-report",
        output_path,
        "unity compile",
        "validation-report/v1",
        report["status"],
        run_id=report["runId"],
    )
    if report["status"] == "blocked":
        state["status"] = "blocked"
        state["blockers"] = ["Unity compile returned SecurityCheck."]
    if state.get("version") == "workflow-state/v2":
        state = apply_next_action(state)
    validate_workflow_state(project_root, state)
    save_workflow_state(project_root, state)
    print_json(report)
    return 0 if report["status"] == "passed" else 1


def _parse_window(value: str | None) -> tuple[str | None, str | None] | None:
    """解析 ``--window`` 参数为 ``(from, to)`` 元组。

    支持格式 ``<from>:<to>``（如 ``2026-05-01:2026-06-08``）。任一端可留空表示该端
    无界（如 ``:2026-06-08`` 或 ``2026-05-01:``）。``value`` 为 None 时返回 None（不做
    时间过滤）。
    """
    if value is None:
        return None
    if ":" not in value:
        raise ValueError(
            "Invalid --window format. Expected '<from>:<to>' (e.g. 2026-05-01:2026-06-08)."
        )
    start, end = value.split(":", 1)
    start = start.strip() or None
    end = end.strip() or None
    return (start, end)


def handle_skill_harvest(args: argparse.Namespace) -> int:
    project_root = resolve_project_root(args.project_root)
    run_dir = project_root / "artifacts" / "ai-runs" / args.run_id
    if not run_dir.is_dir():
        print_json(
            {
                "status": "failed",
                "command": "skill harvest",
                "runId": args.run_id,
                "error": f"Run_History not found for runId {args.run_id!r}: {run_dir} does not exist.",
            }
        )
        return 1

    result = harvest(project_root, args.run_id)
    progress = result.progress
    payload: dict[str, Any] = {
        "status": "passed",
        "command": "skill harvest",
        "runId": args.run_id,
        "signal": result.signal.to_dict(),
        "skipped": [item.to_dict() for item in result.skipped],
    }
    if progress is not None:
        payload["progress"] = {
            "totalRuns": progress.total_runs,
            "categoryCounts": progress.category_counts,
            "meetsMinTotalRuns": progress.meets_min_total_runs,
            "hasRecurringKeyword": progress.has_recurring_keyword,
            "thresholdMet": progress.threshold_met,
        }
    print_json(payload)
    return 0


def handle_skill_ledger(args: argparse.Namespace) -> int:
    project_root = resolve_project_root(args.project_root)
    config = OptimizerConfig.default()
    store = LedgerStore(project_root=project_root)
    store.load()
    progress = store.progress(config.sample_threshold)

    keyword_counts = {
        term: stat.to_dict() for term, stat in progress.keyword_counts.items()
    }
    if args.category:
        keyword_counts = {
            term: stat
            for term, stat in keyword_counts.items()
            if stat.get("category") == args.category
        }

    payload: dict[str, Any] = {
        "status": "passed",
        "command": "skill ledger",
        "totalRuns": progress.total_runs,
        "categoryCounts": progress.category_counts,
        "keywordCounts": keyword_counts,
        "sampleThreshold": config.sample_threshold.to_dict(),
        "progress": {
            "meetsMinTotalRuns": progress.meets_min_total_runs,
            "hasRecurringKeyword": progress.has_recurring_keyword,
            "thresholdMet": progress.threshold_met,
        },
    }
    if args.category:
        payload["category"] = args.category
    if progress.threshold_met:
        payload["triggerCondition"] = "批量 Optimization_Run 已具备触发条件"
    print_json(payload)
    return 0


def handle_skill_optimize(args: argparse.Namespace) -> int:
    project_root = resolve_project_root(args.project_root)
    run_id = args.run_id or default_run_id("skill-opt")
    config = OptimizerConfig.default()
    window = _parse_window(args.window)
    seed = args.seed if args.seed is not None else config.validation_split.seed

    scan = scan_run_histories(project_root, window=window)

    engine = MetricsEngine()
    metrics_report = engine.compute(scan, run_id=run_id)

    # 可选：与上一次 skill-opt 运行的 metrics-report 对比，填充 deltaFromPrevious。
    previous_report = _load_previous_metrics(project_root, run_id)
    metrics_report = engine.diff_against(metrics_report, previous_report)

    evaluator = HeldOutEvaluator(config)
    training, validation = evaluator.split(scan.histories, seed=seed)

    ledger = LedgerStore(project_root=project_root)
    ledger.load()
    training_run_ids = {history.run_id for history in training}
    training_ledger = ledger.filtered_by_run_ids(training_run_ids)

    generator = ProposalGenerator()
    generate_result = generator.generate(metrics_report, training_ledger, config)
    gate_runner = GateRunner()

    decided: list = []
    for proposal in generate_result.proposals:
        evaluation = evaluator.evaluate(
            proposal, validation, project_root=project_root
        )
        outcome = gate_runner.run(proposal, project_root=project_root)
        decide(proposal, evaluation, outcome)
        decided.append(proposal)

    stager = AdoptionStager(project_root)
    stage = stager.stage(decided, run_id=run_id)

    rejected_proposals = [item.proposal for item in generate_result.rejected]
    decisions = build_decisions(run_id, decided, rejected_proposals)
    metrics_path, decisions_path = write_run_evidence(
        project_root=project_root,
        run_id=run_id,
        metrics_report=metrics_report,
        decisions=decisions,
    )
    stage_path = artifact_dir(project_root, run_id) / "adoption-stage.json"

    accepted = sum(1 for p in decided if p.status == "accepted")
    rejected = sum(1 for p in decided if p.status == "rejected") + len(
        rejected_proposals
    )
    payload = {
        "status": "passed",
        "command": "skill optimize",
        "runId": run_id,
        "seed": seed,
        "window": {"from": window[0], "to": window[1]} if window else None,
        "includedRunCount": scan.included_run_count,
        "skippedRunCount": scan.skipped_run_count,
        "proposalCounts": {
            "generated": len(generate_result.proposals),
            "accepted": accepted,
            "rejected": rejected,
            "staged": len(stage.staged_proposals),
        },
        "evidence": {
            "metricsReport": str(metrics_path),
            "proposalDecisions": str(decisions_path),
            "adoptionStage": str(stage_path),
        },
    }
    print_json(payload)
    return 0


def handle_skill_proposals(args: argparse.Namespace) -> int:
    project_root = resolve_project_root(args.project_root)
    stage_path = artifact_dir(project_root, args.run_id) / "adoption-stage.json"
    if not stage_path.exists():
        print_json(
            {
                "status": "failed",
                "command": "skill proposals",
                "runId": args.run_id,
                "error": (
                    f"Adoption_Stage not found for runId {args.run_id!r}: "
                    f"{stage_path} does not exist. Run 'skill optimize' first."
                ),
            }
        )
        return 1

    stage: AdoptionStage = read_model(stage_path, AdoptionStage)  # type: ignore[assignment]
    print_json(
        {
            "status": "passed",
            "command": "skill proposals",
            "runId": args.run_id,
            "stagedProposals": [item.to_dict() for item in stage.staged_proposals],
        }
    )
    return 0


def handle_skill_adopt(args: argparse.Namespace) -> int:
    project_root = resolve_project_root(args.project_root)
    stager = AdoptionStager(project_root)
    try:
        result = stager.apply(
            args.proposal_id,
            run_id=args.run_id,
            confirm=args.confirm,
        )
    except AdoptionError as exc:
        print_json(
            {
                "status": "failed",
                "command": "skill adopt",
                "runId": args.run_id,
                "proposalId": args.proposal_id,
                "error": str(exc),
            }
        )
        return 1

    print_json(
        {
            "status": "passed",
            "command": "skill adopt",
            "runId": args.run_id,
            "proposalId": result.proposal_id,
            "applied": result.applied,
            "path": result.path,
            "message": result.message,
        }
    )
    return 0


def _load_previous_metrics(project_root: Path, current_run_id: str):
    """查找上一次 ``skill-opt`` 运行的 metrics-report 以计算 deltaFromPrevious。

    扫描 ``artifacts/ai-runs/`` 下名称以 ``skill-opt`` 开头、且不等于当前 run 的目录，
    取按名称排序最大的（即最近的）一个的 ``metrics-report.json``。找不到时返回 None
    （deltaFromPrevious 将为 None）。
    """
    runs_root = project_root / "artifacts" / "ai-runs"
    if not runs_root.is_dir():
        return None
    candidates = sorted(
        (
            child
            for child in runs_root.iterdir()
            if child.is_dir()
            and child.name.startswith("skill-opt")
            and child.name != current_run_id
            and (child / "metrics-report.json").is_file()
        ),
        key=lambda path: path.name,
    )
    if not candidates:
        return None
    return read_model(candidates[-1] / "metrics-report.json", MetricsReport)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="ForAI deterministic AI workflow CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    root_parser = subparsers.add_parser("root", help="Print detected project root.")
    root_parser.add_argument("--from-path", help="Optional path used as project-root search start.")
    root_parser.set_defaults(handler=handle_root)

    workflow_parser = subparsers.add_parser("workflow", help="Manage workflow state.")
    workflow_subparsers = workflow_parser.add_subparsers(dest="workflow_command", required=True)
    workflow_init = workflow_subparsers.add_parser("init", help="Create workflow state.")
    workflow_init.add_argument("--run-id", required=True)
    workflow_init.add_argument("--project-root")
    workflow_init.set_defaults(handler=handle_workflow_init)
    workflow_status = workflow_subparsers.add_parser("status", help="Print workflow state.")
    workflow_status.add_argument("--run-id", required=True)
    workflow_status.add_argument("--project-root")
    workflow_status.set_defaults(handler=handle_workflow_status)
    workflow_begin = workflow_subparsers.add_parser("begin", help="Begin or resume a universal workflow.")
    workflow_begin.add_argument("--profile", choices=("auto", "question", "plan", "change"), default="auto")
    workflow_begin.add_argument("--intent", required=True)
    workflow_begin.add_argument("--run-id")
    workflow_begin.add_argument("--project-root")
    workflow_begin.set_defaults(handler=handle_workflow_begin)
    workflow_next = workflow_subparsers.add_parser("next", help="Evaluate next workflow action.")
    workflow_next.add_argument("--run-id", required=True)
    workflow_next.add_argument("--project-root")
    workflow_next.set_defaults(handler=handle_workflow_next)
    workflow_preflight = workflow_subparsers.add_parser("preflight", help="Check whether execution may proceed.")
    workflow_preflight.add_argument("--run-id", required=True)
    workflow_preflight.add_argument("--project-root")
    workflow_preflight.set_defaults(handler=handle_workflow_preflight)
    workflow_complete = workflow_subparsers.add_parser("complete", help="Mark workflow completed.")
    workflow_complete.add_argument("--run-id", required=True)
    workflow_complete.add_argument("--summary", required=True)
    workflow_complete.add_argument("--project-root")
    workflow_complete.set_defaults(handler=handle_workflow_complete)
    workflow_attach = workflow_subparsers.add_parser("attach-artifact", help="Validate and attach a workflow artifact.")
    workflow_attach.add_argument("--run-id", required=True)
    workflow_attach.add_argument("--name", required=True)
    workflow_attach.add_argument("--schema", required=True)
    workflow_attach.add_argument("--input", required=True)
    workflow_attach.add_argument("--producer", default="workflow attach-artifact")
    workflow_attach.add_argument("--project-root")
    workflow_attach.set_defaults(handler=handle_workflow_attach_artifact)

    validate_parser = subparsers.add_parser("validate", help="Validate artifacts.")
    validate_subparsers = validate_parser.add_subparsers(dest="validate_command", required=True)
    validate_file = validate_subparsers.add_parser("file", help="Validate one JSON file.")
    validate_file.add_argument("--schema", required=True)
    validate_file.add_argument("--input", required=True)
    validate_file.add_argument("--project-root")
    validate_file.set_defaults(handler=handle_validate_file)

    requirements_parser = subparsers.add_parser("requirements", help="Validate requirement artifacts.")
    requirements_subparsers = requirements_parser.add_subparsers(dest="requirements_command", required=True)
    requirements_check = requirements_subparsers.add_parser("check")
    requirements_check.add_argument("--input", required=True)
    requirements_check.add_argument("--project-root")
    requirements_check.set_defaults(handler=handle_requirements_check)

    request_parser = subparsers.add_parser("request", help="Guide non-engineering AI request clarification.")
    request_subparsers = request_parser.add_subparsers(dest="request_command", required=True)
    request_guide = request_subparsers.add_parser("guide", help="Return clarification questions for a user intent.")
    request_guide.add_argument("--intent", required=True)
    request_guide.add_argument("--answers")
    request_guide.add_argument("--run-id")
    request_guide.add_argument("--project-root")
    request_guide.set_defaults(handler=handle_request_guide)

    spec_parser = subparsers.add_parser("spec", help="Validate domain specs.")
    spec_subparsers = spec_parser.add_subparsers(dest="spec_command", required=True)
    spec_validate = spec_subparsers.add_parser("validate")
    spec_validate.add_argument("--input", required=True)
    spec_validate.add_argument("--project-root")
    spec_validate.set_defaults(handler=handle_spec_validate)

    plan_parser = subparsers.add_parser("plan", help="Validate execution plans.")
    plan_subparsers = plan_parser.add_subparsers(dest="plan_command", required=True)
    plan_validate = plan_subparsers.add_parser("validate")
    plan_validate.add_argument("--input", required=True)
    plan_validate.add_argument("--project-root")
    plan_validate.set_defaults(handler=handle_plan_validate)

    gate_parser = subparsers.add_parser("gate", help="Set human gate state.")
    gate_subparsers = gate_parser.add_subparsers(dest="gate_command", required=True)
    for status in ("approve", "reject"):
        gate_command = gate_subparsers.add_parser(status)
        gate_command.add_argument("--run-id", required=True)
        gate_command.add_argument("--gate", required=True)
        gate_command.add_argument("--reason", default="")
        gate_command.add_argument("--project-root")
        gate_command.set_defaults(
            handler=handle_gate,
            gate_status="approved" if status == "approve" else "rejected",
        )

    scan_parser = subparsers.add_parser("scan", help="Generate read-only context artifacts.")
    scan_subparsers = scan_parser.add_subparsers(dest="scan_command", required=True)
    scan_context = scan_subparsers.add_parser("context")
    scan_context.add_argument("--run-id")
    scan_context.add_argument("--project-root")
    scan_context.add_argument("--out")
    scan_context.set_defaults(handler=handle_scan_context)

    risk_parser = subparsers.add_parser("risk", help="Review execution plans.")
    risk_subparsers = risk_parser.add_subparsers(dest="risk_command", required=True)
    risk_review = risk_subparsers.add_parser("review")
    risk_review.add_argument("--plan", required=True)
    risk_review.add_argument("--run-id")
    risk_review.add_argument("--project-root")
    risk_review.add_argument("--out")
    risk_review.set_defaults(handler=handle_risk_review)

    unity_parser = subparsers.add_parser("unity", help="Read or validate Unity through gateway.")
    unity_subparsers = unity_parser.add_subparsers(dest="unity_command", required=True)
    unity_status = unity_subparsers.add_parser("status")
    unity_status.add_argument("--project-root")
    unity_status.add_argument("--timeout", type=int, default=10)
    unity_status.set_defaults(handler=handle_unity_status)
    unity_compile = unity_subparsers.add_parser("compile")
    unity_compile.add_argument("--project-root")
    unity_compile.add_argument("--timeout", type=int, default=180)
    unity_compile.add_argument("--run-id")
    unity_compile.set_defaults(handler=handle_unity_compile)

    skill_parser = subparsers.add_parser(
        "skill", help="Local skill optimization: harvest, ledger, optimize, adopt."
    )
    skill_subparsers = skill_parser.add_subparsers(dest="skill_command", required=True)

    skill_harvest = skill_subparsers.add_parser(
        "harvest", help="Read-only harvest of a single Run_History into Signal_Ledger."
    )
    skill_harvest.add_argument("--run-id", required=True)
    skill_harvest.add_argument("--project-root")
    skill_harvest.set_defaults(handler=handle_skill_harvest)

    skill_ledger = skill_subparsers.add_parser(
        "ledger", help="Show Signal_Ledger contents and Sample_Threshold progress."
    )
    skill_ledger.add_argument(
        "--category",
        choices=("steering_match", "capability_registry", "intent_classification"),
        help="Optional Candidate_Keyword category to filter keyword counts.",
    )
    skill_ledger.add_argument("--project-root")
    skill_ledger.set_defaults(handler=handle_skill_ledger)

    skill_optimize = skill_subparsers.add_parser(
        "optimize", help="Run a batch Optimization_Run and stage Edit_Proposals."
    )
    skill_optimize.add_argument("--run-id")
    skill_optimize.add_argument("--seed", type=int)
    skill_optimize.add_argument(
        "--window",
        help="Optional time window '<from>:<to>' (e.g. 2026-05-01:2026-06-08).",
    )
    skill_optimize.add_argument("--project-root")
    skill_optimize.set_defaults(handler=handle_skill_optimize)

    skill_proposals = skill_subparsers.add_parser(
        "proposals", help="List staged Edit_Proposals awaiting adoption."
    )
    skill_proposals.add_argument("--run-id", required=True)
    skill_proposals.add_argument("--project-root")
    skill_proposals.set_defaults(handler=handle_skill_proposals)

    skill_adopt = skill_subparsers.add_parser(
        "adopt", help="Apply a staged Edit_Proposal after human confirmation."
    )
    skill_adopt.add_argument("--run-id", required=True)
    skill_adopt.add_argument("--proposal-id", required=True)
    skill_adopt.add_argument("--confirm", action="store_true")
    skill_adopt.add_argument("--project-root")
    skill_adopt.set_defaults(handler=handle_skill_adopt)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return args.handler(args)
    except (FileNotFoundError, KeyError, SchemaValidationError, ValueError) as exc:
        print_json({"status": "failed", "error": str(exc)})
        return 1


if __name__ == "__main__":
    sys.exit(main())
