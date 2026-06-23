import pytest

from forai.paths import find_project_root
from forai.request_guide import build_request_guide, validate_answers_run_id
from forai.schemas import load_schema, validate_payload


def test_build_request_guide_classifies_ui_intent():
    payload = build_request_guide("我想做一个背包界面", run_id="question-123")

    assert payload["version"] == "request-guide/v1"
    assert payload["runId"] == "question-123"
    assert payload["taskType"] == "ui"
    assert payload["status"] == "needs_clarification"
    assert payload["workflowProfileHint"] == "question"
    assert payload["nextAction"] == "ask_user"
    assert [question["id"] for question in payload["questions"]] == [
        "ui.target",
        "ui.reference",
        "ui.asset_source",
    ]
    assert payload["safeDefaults"][0]["field"] == "ui.implementation"


def test_build_request_guide_classifies_bug_intent_with_priority_default():
    payload = build_request_guide("背包界面按钮点击没有反应")

    assert payload["taskType"] == "bug"
    assert payload["workflowProfileHint"] == "question"
    assert any(default["field"] == "bug.priority" for default in payload["safeDefaults"])
    assert payload["questions"][0]["id"] == "bug.repro_steps"


def test_build_request_guide_blocks_empty_intent():
    payload = build_request_guide("   ")

    assert payload["taskType"] == "unknown"
    assert payload["status"] == "blocked"
    assert payload["nextAction"] == "revise_request"
    assert payload["questions"][0]["id"] == "intent.goal"


def test_build_request_guide_skips_answered_questions():
    payload = build_request_guide(
        "创建一个道具 Prefab",
        answers={
            "prefab.target": "药水道具",
            "prefab.overwrite": "不知道",
        },
    )

    question_ids = [question["id"] for question in payload["questions"]]
    assert "prefab.target" not in question_ids
    assert "prefab.overwrite" not in question_ids
    assert payload["known"]["prefab.target"] == "药水道具"
    assert any(default["field"] == "prefab.overwrite" for default in payload["safeDefaults"])


def test_build_request_guide_ready_when_required_answers_exist():
    payload = build_request_guide(
        "我想做一个背包界面",
        answers={
            "ui.target": "玩家查看和整理道具",
            "ui.reference": "参考现有商城界面",
            "ui.asset_source": "使用现有图集",
            "ui.interaction": "点击格子显示详情",
        },
    )

    assert payload["status"] == "ready"
    assert payload["workflowProfileHint"] == "plan"
    assert payload["nextAction"] == "begin_workflow"
    assert payload["questions"] == []
    assert payload["summary"]["ready"] is True
    assert payload["summary"]["suggestedProfile"] == "plan"


def test_validate_answers_run_id_accepts_matching_run_id():
    validate_answers_run_id({"runId": "question-123"}, "question-123")


def test_validate_answers_run_id_rejects_mismatch():
    with pytest.raises(ValueError, match="runId mismatch"):
        validate_answers_run_id({"runId": "other"}, "question-123")


def test_build_request_guide_payload_matches_schema():
    root = find_project_root()
    schema = load_schema(root, "request-guide/v1")

    payload = build_request_guide("需要优化角色立绘导入流程")

    validate_payload(schema, payload)
