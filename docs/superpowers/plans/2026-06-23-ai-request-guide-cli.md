# AI Request Guide CLI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement a read-only `python tools\ai\ai.py request guide` command that returns deterministic clarification questions, safe defaults, and summaries for non-engineering Unity requests.

**Architecture:** Add versioned JSON schemas for request guide inputs and outputs, implement deterministic request classification and question selection in a focused `forai.request_guide` module, then wire it into the existing Python CLI. The command remains read-only and only emits JSON; it does not create workflows, modify Unity assets, or bypass existing workflow/risk/preflight gates.

**Tech Stack:** Python stdlib, `argparse`, existing `forai.json_io`, existing schema validator, `pytest`, Markdown docs.

---

## File Structure

- Create: `tools/ai/schemas/request-guide.v1.schema.json`
  - JSON Schema for `request-guide/v1` CLI output.
- Create: `tools/ai/schemas/request-guide-answers.v1.schema.json`
  - JSON Schema for optional `--answers` input.
- Create: `tools/ai/forai/request_guide.py`
  - Pure deterministic logic: task classification, answer parsing, question selection, safe defaults, summary generation.
- Create: `tools/ai/tests/test_request_guide.py`
  - Unit tests for the pure logic.
- Modify: `tools/ai/tests/test_schemas.py`
  - Schema validation tests for request guide payloads.
- Modify: `tools/ai/tests/test_cli.py`
  - CLI integration tests for `request guide`.
- Modify: `tools/ai/ai.py`
  - Add `request guide` parser and handler.
- Modify: `docs/ai/capability-registry.md`
  - Register Request Guide CLI as read-only capability.
- Modify: `docs/ai/workflows.md`
  - Add the command to the non-engineering clarification workflow.

## Task 1: Add Request Guide Schemas

**Files:**
- Create: `tools/ai/schemas/request-guide.v1.schema.json`
- Create: `tools/ai/schemas/request-guide-answers.v1.schema.json`
- Modify: `tools/ai/tests/test_schemas.py`

- [ ] **Step 1: Write schema tests first**

Append these tests to `tools/ai/tests/test_schemas.py`:

```python

def test_validate_request_guide_accepts_needs_clarification_payload():
    root = find_project_root()
    schema = load_schema(root, "request-guide/v1")
    payload = {
        "version": "request-guide/v1",
        "runId": "question-20260623-100000",
        "intent": "我想做一个背包界面",
        "taskType": "ui",
        "status": "needs_clarification",
        "questions": [
            {
                "id": "ui.kind",
                "prompt": "这是新界面，还是修改已有界面？",
                "kind": "single_choice",
                "options": ["新界面", "修改已有界面", "不知道"],
                "required": True,
            }
        ],
        "safeDefaults": [
            {
                "field": "prefabOverwrite",
                "value": "false",
                "reason": "未确认覆盖时默认不覆盖已有 Prefab。",
            }
        ],
        "known": {"goal": "做一个背包界面"},
        "unknowns": ["ui.kind"],
        "summary": None,
        "workflowProfileHint": "question",
        "nextAction": "ask_user",
    }
    validate_payload(schema, payload)


def test_validate_request_guide_answers_accepts_basic_payload():
    root = find_project_root()
    schema = load_schema(root, "request-guide-answers/v1")
    payload = {
        "version": "request-guide-answers/v1",
        "runId": "question-20260623-100000",
        "answers": {
            "ui.kind": "新界面",
            "ui.purpose": "玩家查看道具列表",
            "ui.reference": "不知道",
            "ui.count": 12,
            "ui.optional": True,
            "ui.tags": ["背包", "道具"],
        },
    }
    validate_payload(schema, payload)
```

- [ ] **Step 2: Run schema tests and verify RED**

Run:

```powershell
python -m pytest tools\ai\tests\test_schemas.py -q
```

Expected: fails because `request-guide/v1` and `request-guide-answers/v1` schemas do not exist.

- [ ] **Step 3: Add `request-guide.v1.schema.json`**

Create `tools/ai/schemas/request-guide.v1.schema.json`:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://forai.local/schemas/request-guide.v1.schema.json",
  "title": "RequestGuideV1",
  "type": "object",
  "required": [
    "version",
    "intent",
    "taskType",
    "status",
    "questions",
    "safeDefaults",
    "known",
    "unknowns",
    "summary",
    "workflowProfileHint",
    "nextAction"
  ],
  "additionalProperties": false,
  "properties": {
    "version": { "const": "request-guide/v1" },
    "runId": { "type": "string", "minLength": 1 },
    "intent": { "type": "string", "minLength": 1 },
    "taskType": {
      "enum": ["ui", "prefab", "art_asset", "config", "bug", "read_only", "unknown"]
    },
    "status": {
      "enum": ["needs_clarification", "ready_for_summary", "blocked"]
    },
    "questions": {
      "type": "array",
      "maxItems": 3,
      "items": {
        "type": "object",
        "required": ["id", "prompt", "kind", "options", "required"],
        "additionalProperties": false,
        "properties": {
          "id": { "type": "string", "minLength": 1 },
          "prompt": { "type": "string", "minLength": 1 },
          "kind": { "enum": ["single_choice", "short_text"] },
          "options": {
            "type": "array",
            "items": { "type": "string" }
          },
          "required": { "type": "boolean" }
        }
      }
    },
    "safeDefaults": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["field", "value", "reason"],
        "additionalProperties": false,
        "properties": {
          "field": { "type": "string", "minLength": 1 },
          "value": { "type": "string" },
          "reason": { "type": "string", "minLength": 1 }
        }
      }
    },
    "known": {
      "type": "object",
      "additionalProperties": {
        "anyOf": [
          { "type": "string" },
          { "type": "number" },
          { "type": "boolean" },
          { "type": "array", "items": { "type": "string" } }
        ]
      }
    },
    "unknowns": {
      "type": "array",
      "items": { "type": "string", "minLength": 1 }
    },
    "summary": {
      "anyOf": [
        { "type": "null" },
        {
          "type": "object",
          "required": [
            "taskType",
            "goal",
            "targetPath",
            "inputs",
            "defaultHandling",
            "risks",
            "acceptance"
          ],
          "additionalProperties": false,
          "properties": {
            "taskType": { "type": "string", "minLength": 1 },
            "goal": { "type": "string", "minLength": 1 },
            "targetPath": { "type": "string" },
            "inputs": { "type": "array", "items": { "type": "string" } },
            "defaultHandling": { "type": "array", "items": { "type": "string" } },
            "risks": { "type": "array", "items": { "type": "string" } },
            "acceptance": { "type": "array", "items": { "type": "string" } }
          }
        }
      ]
    },
    "workflowProfileHint": { "enum": ["question", "plan", "change"] },
    "nextAction": { "enum": ["ask_user", "confirm_summary", "revise_request"] }
  }
}
```

- [ ] **Step 4: Add `request-guide-answers.v1.schema.json`**

Create `tools/ai/schemas/request-guide-answers.v1.schema.json`:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://forai.local/schemas/request-guide-answers.v1.schema.json",
  "title": "RequestGuideAnswersV1",
  "type": "object",
  "required": ["version", "answers"],
  "additionalProperties": false,
  "properties": {
    "version": { "const": "request-guide-answers/v1" },
    "runId": { "type": "string", "minLength": 1 },
    "answers": {
      "type": "object",
      "additionalProperties": {
        "anyOf": [
          { "type": "string" },
          { "type": "number" },
          { "type": "boolean" },
          { "type": "array", "items": { "type": "string" } }
        ]
      }
    }
  }
}
```

- [ ] **Step 5: Run schema tests and verify GREEN**

Run:

```powershell
python -m pytest tools\ai\tests\test_schemas.py -q
```

Expected: all tests in `test_schemas.py` pass.

- [ ] **Step 6: Commit schema task**

Run:

```powershell
git add tools/ai/schemas/request-guide.v1.schema.json tools/ai/schemas/request-guide-answers.v1.schema.json tools/ai/tests/test_schemas.py
git commit -m "feat: add request guide schemas"
```

Expected: commit succeeds and includes only the two schema files plus schema tests.

## Task 2: Implement Request Guide Core Logic

**Files:**
- Create: `tools/ai/forai/request_guide.py`
- Create: `tools/ai/tests/test_request_guide.py`

- [ ] **Step 1: Write failing tests for classification and initial questions**

Create `tools/ai/tests/test_request_guide.py`:

```python
import pytest

from forai.request_guide import build_request_guide


def question_ids(payload):
    return [question["id"] for question in payload["questions"]]


def test_ui_intent_returns_first_three_ui_questions():
    payload = build_request_guide("我想做一个背包界面")

    assert payload["version"] == "request-guide/v1"
    assert payload["taskType"] == "ui"
    assert payload["status"] == "needs_clarification"
    assert question_ids(payload) == ["ui.kind", "ui.purpose", "ui.display"]
    assert len(payload["questions"]) == 3
    assert payload["known"]["goal"] == "我想做一个背包界面"
    assert payload["workflowProfileHint"] == "question"
    assert payload["nextAction"] == "ask_user"


def test_bug_keywords_take_priority_over_ui_keywords():
    payload = build_request_guide("背包界面按钮点击没有反应，帮我修复")

    assert payload["taskType"] == "bug"
    assert question_ids(payload) == ["bug.symptom", "bug.steps", "bug.expected"]


def test_unknown_intent_returns_common_classification_question():
    payload = build_request_guide("帮我处理一下")

    assert payload["taskType"] == "unknown"
    assert payload["status"] == "needs_clarification"
    assert question_ids(payload) == ["common.task_type"]
    assert payload["questions"][0]["kind"] == "single_choice"


def test_run_id_is_echoed_when_provided():
    payload = build_request_guide("解释一下这个 Prefab", run_id="question-1")

    assert payload["runId"] == "question-1"
```

- [ ] **Step 2: Run request guide tests and verify RED**

Run:

```powershell
python -m pytest tools\ai\tests\test_request_guide.py -q
```

Expected: fails because `forai.request_guide` does not exist.

- [ ] **Step 3: Implement minimal core module**

Create `tools/ai/forai/request_guide.py`:

```python
from __future__ import annotations

from typing import Any


QUESTION_KIND_SINGLE_CHOICE = "single_choice"
QUESTION_KIND_SHORT_TEXT = "short_text"


def build_request_guide(
    intent: str,
    *,
    answers: dict[str, Any] | None = None,
    run_id: str | None = None,
) -> dict[str, Any]:
    cleaned_intent = intent.strip()
    if not cleaned_intent:
        return _payload(
            intent=intent,
            task_type="unknown",
            status="blocked",
            questions=[_question("common.task_type", "你这次想做的是哪一类？", QUESTION_KIND_SINGLE_CHOICE, _common_options(), True)],
            safe_defaults=[],
            known={},
            unknowns=["intent"],
            summary=None,
            workflow_profile_hint="question",
            next_action="revise_request",
            run_id=run_id,
        )

    answers = answers or {}
    task_type = _classify(cleaned_intent, answers)
    known: dict[str, Any] = {"goal": cleaned_intent}
    known.update(answers)

    safe_defaults = _safe_defaults(task_type, answers)
    questions = _next_questions(task_type, answers)
    if questions:
        status = "needs_clarification"
        summary = None
        workflow_profile_hint = "question"
        next_action = "ask_user"
    else:
        status = "ready_for_summary"
        summary = _summary(task_type, cleaned_intent, answers, safe_defaults)
        workflow_profile_hint = "plan" if task_type != "read_only" else "question"
        next_action = "confirm_summary"

    return _payload(
        intent=cleaned_intent,
        task_type=task_type,
        status=status,
        questions=questions,
        safe_defaults=safe_defaults,
        known=known,
        unknowns=[question["id"] for question in questions if question["required"]],
        summary=summary,
        workflow_profile_hint=workflow_profile_hint,
        next_action=next_action,
        run_id=run_id,
    )


def validate_answers_run_id(answers_payload: dict[str, Any], run_id: str | None) -> None:
    answers_run_id = answers_payload.get("runId")
    if answers_run_id and run_id and answers_run_id != run_id:
        raise ValueError(f"Answers runId {answers_run_id!r} does not match --run-id {run_id!r}.")


def _payload(
    *,
    intent: str,
    task_type: str,
    status: str,
    questions: list[dict[str, Any]],
    safe_defaults: list[dict[str, str]],
    known: dict[str, Any],
    unknowns: list[str],
    summary: dict[str, Any] | None,
    workflow_profile_hint: str,
    next_action: str,
    run_id: str | None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "version": "request-guide/v1",
        "intent": intent,
        "taskType": task_type,
        "status": status,
        "questions": questions[:3],
        "safeDefaults": safe_defaults,
        "known": known,
        "unknowns": unknowns,
        "summary": summary,
        "workflowProfileHint": workflow_profile_hint,
        "nextAction": next_action,
    }
    if run_id:
        payload["runId"] = run_id
    return payload


def _question(
    question_id: str,
    prompt: str,
    kind: str,
    options: list[str] | None = None,
    required: bool = True,
) -> dict[str, Any]:
    return {
        "id": question_id,
        "prompt": prompt,
        "kind": kind,
        "options": options or [],
        "required": required,
    }


def _common_options() -> list[str]:
    return ["新增东西", "修改已有东西", "修复问题", "整理资源或文档", "只想了解现状"]


def _classify(intent: str, answers: dict[str, Any]) -> str:
    lowered = intent.lower()
    if "common.task_type" in answers:
        return _task_type_from_common_answer(str(answers["common.task_type"]))
    if _contains_any(lowered, ["报错", "无反应", "异常", "复现", "修复", "崩溃", "空引用", "bug"]):
        return "bug"
    if _contains_any(lowered, ["界面", "页面", "按钮", "弹窗", "入口", "ui", "背包"]):
        return "ui"
    if _contains_any(lowered, ["prefab", "预制体", "组件", "子物体", "挂载", "引用"]):
        return "prefab"
    if _contains_any(lowered, ["图标", "立绘", "音效", "材质", "模型", "导入", "整理资源"]):
        return "art_asset"
    if _contains_any(lowered, ["数值", "配置", "表格", "scriptableobject", "json", "属性"]):
        return "config"
    if _contains_any(lowered, ["解释", "检查", "看看", "说明", "分析", "只读"]):
        return "read_only"
    return "unknown"


def _contains_any(value: str, keywords: list[str]) -> bool:
    return any(keyword in value for keyword in keywords)


def _task_type_from_common_answer(answer: str) -> str:
    if "修复" in answer:
        return "bug"
    if "整理" in answer:
        return "art_asset"
    if "了解" in answer or "现状" in answer:
        return "read_only"
    if "新增" in answer or "修改" in answer:
        return "ui"
    return "unknown"


def _question_bank(task_type: str) -> list[dict[str, Any]]:
    banks = {
        "ui": [
            _question("ui.kind", "这是新界面，还是修改已有界面？", QUESTION_KIND_SINGLE_CHOICE, ["新界面", "修改已有界面", "不知道"]),
            _question("ui.purpose", "这个界面什么时候打开，给玩家完成什么事情？", QUESTION_KIND_SHORT_TEXT),
            _question("ui.display", "页面上需要显示哪些信息？", QUESTION_KIND_SHORT_TEXT),
            _question("ui.interaction", "有哪些按钮或可点击区域？点击后分别发生什么？", QUESTION_KIND_SHORT_TEXT),
            _question("ui.reference", "有没有参考图、现有页面、Prefab 或素材路径？", QUESTION_KIND_SHORT_TEXT, ["没有", "不知道"], False),
            _question("ui.create_permission", "是否允许创建新的脚本、Prefab 或 Addressables 条目？", QUESTION_KIND_SINGLE_CHOICE, ["允许", "不允许", "不知道"]),
            _question("ui.acceptance", "你希望怎么验收这个页面？", QUESTION_KIND_SHORT_TEXT),
        ],
        "prefab": [
            _question("prefab.kind", "你要创建新 Prefab，还是修改已有 Prefab？", QUESTION_KIND_SINGLE_CHOICE, ["创建新 Prefab", "修改已有 Prefab", "不知道"]),
            _question("prefab.usage", "Prefab 用在什么场景或系统里？", QUESTION_KIND_SHORT_TEXT),
            _question("prefab.path", "目标路径或现有 Prefab 路径是什么？", QUESTION_KIND_SHORT_TEXT),
            _question("prefab.components", "需要哪些组件、子物体或引用资源？", QUESTION_KIND_SHORT_TEXT),
            _question("prefab.overwrite", "是否允许覆盖已有 Prefab？", QUESTION_KIND_SINGLE_CHOICE, ["允许", "不允许", "不知道"]),
            _question("prefab.naming", "是否有命名规则或参考对象？", QUESTION_KIND_SHORT_TEXT, ["没有", "不知道"], False),
            _question("prefab.acceptance", "验收时要看到什么？", QUESTION_KIND_SHORT_TEXT),
        ],
        "art_asset": [
            _question("art_asset.type", "资源类型是什么，例如图标、立绘、音效、材质或模型？", QUESTION_KIND_SHORT_TEXT),
            _question("art_asset.source_target", "资源现在在哪里，目标放到哪里？", QUESTION_KIND_SHORT_TEXT),
            _question("art_asset.naming", "是否需要改名？命名规则是什么？", QUESTION_KIND_SHORT_TEXT),
            _question("art_asset.addressables", "是否需要加入 Addressables 分组？", QUESTION_KIND_SINGLE_CHOICE, ["需要", "不需要", "不知道"], False),
            _question("art_asset.overwrite", "是否允许移动或覆盖已有资源？", QUESTION_KIND_SINGLE_CHOICE, ["允许", "不允许", "不知道"]),
            _question("art_asset.acceptance", "导入后怎么判断结果正确？", QUESTION_KIND_SHORT_TEXT),
        ],
        "config": [
            _question("config.target", "要调整哪个系统、角色、道具或功能？", QUESTION_KIND_SHORT_TEXT),
            _question("config.values", "当前数值是多少？目标数值是多少？", QUESTION_KIND_SHORT_TEXT),
            _question("config.source", "数值来源在哪里，例如表格、ScriptableObject、JSON、代码常量？", QUESTION_KIND_SHORT_TEXT),
            _question("config.runtime_impact", "调整是否影响线上或热更新内容？", QUESTION_KIND_SINGLE_CHOICE, ["影响", "不影响", "不知道"]),
            _question("config.acceptance", "验收时看哪个表现？", QUESTION_KIND_SHORT_TEXT),
        ],
        "bug": [
            _question("bug.symptom", "你看到了什么异常现象？", QUESTION_KIND_SHORT_TEXT),
            _question("bug.steps", "从打开项目到出现问题，需要哪些步骤？", QUESTION_KIND_SHORT_TEXT),
            _question("bug.expected", "你期望看到什么结果？", QUESTION_KIND_SHORT_TEXT),
            _question("bug.actual", "实际结果是什么？", QUESTION_KIND_SHORT_TEXT),
            _question("bug.stability", "这个问题是否稳定复现？", QUESTION_KIND_SINGLE_CHOICE, ["稳定复现", "偶现", "不知道"]),
            _question("bug.recent_changes", "最近是否改过相关 UI、Prefab、配置或脚本？", QUESTION_KIND_SHORT_TEXT, ["没有", "不知道"], False),
            _question("bug.acceptance", "修复后你希望用什么方式验收？", QUESTION_KIND_SHORT_TEXT),
        ],
        "read_only": [
            _question("read_only.target", "你想了解哪个对象、系统或文件？", QUESTION_KIND_SHORT_TEXT),
            _question("read_only.style", "你希望 AI 用什么方式解释：简单说明、流程图、风险点、修改建议？", QUESTION_KIND_SHORT_TEXT),
            _question("read_only.confirm", "是否只读，不做任何修改？", QUESTION_KIND_SINGLE_CHOICE, ["只读", "可能需要修改", "不知道"]),
        ],
        "unknown": [
            _question("common.task_type", "你这次想做的是哪一类？", QUESTION_KIND_SINGLE_CHOICE, _common_options()),
        ],
    }
    return banks[task_type]


def _next_questions(task_type: str, answers: dict[str, Any]) -> list[dict[str, Any]]:
    questions = []
    for question in _question_bank(task_type):
        if question["id"] not in answers:
            questions.append(question)
        if len(questions) == 3:
            break
    return questions


def _safe_defaults(task_type: str, answers: dict[str, Any]) -> list[dict[str, str]]:
    defaults: list[dict[str, str]] = []
    if task_type in {"ui", "prefab"} and _is_unknown_or_missing(answers, "prefab.overwrite"):
        defaults.append(
            {
                "field": "prefabOverwrite",
                "value": "false",
                "reason": "未确认覆盖时默认不覆盖已有 Prefab。",
            }
        )
    if task_type == "art_asset":
        defaults.extend(
            [
                {"field": "deleteOldAssets", "value": "false", "reason": "默认不删除旧资源。"},
                {"field": "overwriteSameName", "value": "false", "reason": "默认不覆盖同名资源。"},
                {"field": "editMeta", "value": "false", "reason": "默认不直接改 .meta。"},
            ]
        )
    if task_type == "config" and _is_unknown_or_missing(answers, "config.source"):
        defaults.append(
            {
                "field": "configSource",
                "value": "read-only scan first",
                "reason": "不知道配置位置时，先只读扫描并报告候选位置。",
            }
        )
    if task_type == "bug":
        defaults.append(
            {
                "field": "debugMode",
                "value": "read-only investigation first",
                "reason": "复现步骤不完整或不能复现时，先做只读排查，不直接修改。",
            }
        )
    return defaults


def _is_unknown_or_missing(answers: dict[str, Any], field: str) -> bool:
    value = answers.get(field)
    return value is None or str(value).strip() in {"", "不知道"}


def _summary(
    task_type: str,
    intent: str,
    answers: dict[str, Any],
    safe_defaults: list[dict[str, str]],
) -> dict[str, Any]:
    return {
        "taskType": _summary_task_type(task_type),
        "goal": str(answers.get("goal", intent)),
        "targetPath": str(answers.get(f"{task_type}.path", "建议路径，待用户确认。")),
        "inputs": _string_list(answers.get(f"{task_type}.reference", [])),
        "defaultHandling": [item["reason"] for item in safe_defaults],
        "risks": _risks(task_type),
        "acceptance": _string_list(answers.get(f"{task_type}.acceptance", "用户确认结果符合需求摘要。")),
    }


def _summary_task_type(task_type: str) -> str:
    return {
        "ui": "UI 页面新增或修改",
        "prefab": "Prefab 创建或修改",
        "art_asset": "美术资源导入或整理",
        "config": "数值或配置调整",
        "bug": "Bug 复现和修复",
        "read_only": "只读解释或检查",
        "unknown": "未知任务",
    }[task_type]


def _risks(task_type: str) -> list[str]:
    if task_type == "ui":
        return ["可能创建新 UI 脚本或 Prefab，执行前需要确认。"]
    if task_type == "prefab":
        return ["修改或覆盖 Prefab 前必须明确确认。"]
    if task_type == "art_asset":
        return ["移动、覆盖或加入 Addressables 分组前必须确认。"]
    if task_type == "config":
        return ["涉及运行时行为时必须补充验证。"]
    if task_type == "bug":
        return ["修复运行时行为时必须运行相关测试或验证命令。"]
    return []


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if str(item)]
    text = str(value)
    return [text] if text else []
```

- [ ] **Step 4: Run initial tests and verify GREEN**

Run:

```powershell
python -m pytest tools\ai\tests\test_request_guide.py -q
```

Expected: all tests in `test_request_guide.py` pass.

- [ ] **Step 5: Add answers and summary tests**

Append to `tools/ai/tests/test_request_guide.py`:

```python

def test_answers_skip_answered_questions():
    payload = build_request_guide(
        "我想做一个背包界面",
        answers={
            "ui.kind": "新界面",
            "ui.purpose": "玩家查看道具列表",
            "ui.display": "道具图标、名称、数量",
        },
    )

    assert question_ids(payload) == ["ui.interaction", "ui.reference", "ui.create_permission"]
    assert payload["known"]["ui.kind"] == "新界面"


def test_unknown_answer_produces_safe_default_for_prefab_overwrite():
    payload = build_request_guide("创建一个道具 Prefab", answers={"prefab.overwrite": "不知道"})

    assert payload["taskType"] == "prefab"
    assert {
        "field": "prefabOverwrite",
        "value": "false",
        "reason": "未确认覆盖时默认不覆盖已有 Prefab。",
    } in payload["safeDefaults"]


def test_ready_for_summary_when_all_questions_answered():
    payload = build_request_guide(
        "我想做一个背包界面",
        answers={
            "ui.kind": "新界面",
            "ui.purpose": "玩家查看道具列表",
            "ui.display": "道具图标、名称、数量",
            "ui.interaction": "点击道具显示详情",
            "ui.reference": "不知道",
            "ui.create_permission": "允许",
            "ui.acceptance": "页面能打开，列表能显示测试数据",
        },
    )

    assert payload["status"] == "ready_for_summary"
    assert payload["questions"] == []
    assert payload["summary"]["taskType"] == "UI 页面新增或修改"
    assert payload["workflowProfileHint"] == "plan"
    assert payload["nextAction"] == "confirm_summary"


def test_answers_run_id_mismatch_raises():
    from forai.request_guide import validate_answers_run_id

    with pytest.raises(ValueError, match="does not match"):
        validate_answers_run_id({"runId": "other"}, "question-1")
```

- [ ] **Step 6: Run request guide tests again**

Run:

```powershell
python -m pytest tools\ai\tests\test_request_guide.py -q
```

Expected: all request guide tests pass.

- [ ] **Step 7: Validate payloads against schema in core tests**

Append to `tools/ai/tests/test_request_guide.py`:

```python
from forai.paths import find_project_root
from forai.schemas import load_schema, validate_payload


def test_request_guide_payload_matches_schema():
    root = find_project_root()
    schema = load_schema(root, "request-guide/v1")
    payload = build_request_guide("我想做一个背包界面", run_id="question-1")

    validate_payload(schema, payload)
```

- [ ] **Step 8: Run core and schema tests**

Run:

```powershell
python -m pytest tools\ai\tests\test_request_guide.py tools\ai\tests\test_schemas.py -q
```

Expected: all selected tests pass.

- [ ] **Step 9: Commit core logic task**

Run:

```powershell
git add tools/ai/forai/request_guide.py tools/ai/tests/test_request_guide.py
git commit -m "feat: add request guide logic"
```

Expected: commit succeeds and includes only the core module and its tests.

## Task 3: Wire Request Guide Into CLI

**Files:**
- Modify: `tools/ai/ai.py`
- Modify: `tools/ai/tests/test_cli.py`

- [ ] **Step 1: Write CLI tests first**

Append to `tools/ai/tests/test_cli.py`:

```python

def test_request_guide_cli_outputs_questions_for_ui_intent():
    root = find_project_root()

    completed = run_cli(
        "request",
        "guide",
        "--intent",
        "我想做一个背包界面",
        "--run-id",
        "question-1",
        "--project-root",
        str(root),
    )

    assert completed.returncode == 0, completed.stderr
    payload = parse_stdout(completed)
    assert payload["version"] == "request-guide/v1"
    assert payload["runId"] == "question-1"
    assert payload["taskType"] == "ui"
    assert [question["id"] for question in payload["questions"]] == ["ui.kind", "ui.purpose", "ui.display"]


def test_request_guide_cli_reads_answers_file(tmp_path: Path):
    root = find_project_root()
    answers = write_json(
        tmp_path / "answers.json",
        {
            "version": "request-guide-answers/v1",
            "runId": "question-1",
            "answers": {
                "ui.kind": "新界面",
                "ui.purpose": "玩家查看道具列表",
                "ui.display": "道具图标、名称、数量",
            },
        },
    )

    completed = run_cli(
        "request",
        "guide",
        "--intent",
        "我想做一个背包界面",
        "--answers",
        str(answers),
        "--run-id",
        "question-1",
        "--project-root",
        str(root),
    )

    assert completed.returncode == 0, completed.stderr
    payload = parse_stdout(completed)
    assert [question["id"] for question in payload["questions"]] == [
        "ui.interaction",
        "ui.reference",
        "ui.create_permission",
    ]


def test_request_guide_cli_rejects_answers_run_id_mismatch(tmp_path: Path):
    root = find_project_root()
    answers = write_json(
        tmp_path / "answers.json",
        {
            "version": "request-guide-answers/v1",
            "runId": "other",
            "answers": {},
        },
    )

    completed = run_cli(
        "request",
        "guide",
        "--intent",
        "我想做一个背包界面",
        "--answers",
        str(answers),
        "--run-id",
        "question-1",
        "--project-root",
        str(root),
    )

    assert completed.returncode == 1
    payload = parse_stdout(completed)
    assert payload["status"] == "failed"
    assert "runId" in payload["error"]
```

- [ ] **Step 2: Run CLI tests and verify RED**

Run:

```powershell
python -m pytest tools\ai\tests\test_cli.py -q
```

Expected: fails because `request` command does not exist.

- [ ] **Step 3: Import request guide helpers in `tools/ai/ai.py`**

Add imports near the existing `forai` imports:

```python
from forai.request_guide import build_request_guide, validate_answers_run_id
```

- [ ] **Step 4: Add CLI handler in `tools/ai/ai.py`**

Add this function after `handle_requirements_check`:

```python
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
```

- [ ] **Step 5: Register `request guide` parser in `build_parser`**

Add before the `skill_parser` block:

```python
    request_parser = subparsers.add_parser("request", help="Guide non-engineering AI request clarification.")
    request_subparsers = request_parser.add_subparsers(dest="request_command", required=True)
    request_guide = request_subparsers.add_parser("guide", help="Return clarification questions for a user intent.")
    request_guide.add_argument("--intent", required=True)
    request_guide.add_argument("--answers")
    request_guide.add_argument("--run-id")
    request_guide.add_argument("--project-root")
    request_guide.set_defaults(handler=handle_request_guide)
```

- [ ] **Step 6: Run CLI tests and verify GREEN**

Run:

```powershell
python -m pytest tools\ai\tests\test_cli.py -q
```

Expected: all CLI tests pass.

- [ ] **Step 7: Run focused request guide command manually**

Run:

```powershell
python tools\ai\ai.py request guide --intent "我想做一个背包界面" --run-id question-manual --project-root "D:\foraiproject"
```

Expected: JSON contains `"version": "request-guide/v1"`, `"taskType": "ui"`, and exactly three questions.

- [ ] **Step 8: Commit CLI task**

Run:

```powershell
git add tools/ai/ai.py tools/ai/tests/test_cli.py
git commit -m "feat: add request guide cli"
```

Expected: commit succeeds and includes only CLI wiring and CLI tests.

## Task 4: Update AI Documentation

**Files:**
- Modify: `docs/ai/capability-registry.md`
- Modify: `docs/ai/workflows.md`

- [ ] **Step 1: Update capability registry**

In `docs/ai/capability-registry.md`, under `## 确定性 AI CLI`, add a section before `### Workflow State`:

```markdown
### Request Guide

入口：

- `python tools\ai\ai.py request guide`

允许：

- 根据用户自然语言意图返回下一轮澄清问题。
- 读取可选的 `request-guide-answers/v1` answers 文件。
- 输出 `request-guide/v1` JSON。
- 给出安全默认建议和需求摘要。

禁止：

- 修改文件或 Unity 资产。
- 自动创建、移动、删除或覆盖资源。
- 代替 `Workflow Engine`、`risk review`、人工 gate、`workflow preflight` 或验证。
```

- [ ] **Step 2: Update workflows**

In `docs/ai/workflows.md`, in `## 非工程用户需求澄清工作流`, change the numbered list to include the command after the one-sentence intent:

```markdown
1. 用户先用一句话描述想法。
2. AI 先进入 `question` 或 `auto` workflow。
3. AI 调用 `python tools\ai\ai.py request guide --intent "<用户意图>" --run-id <run-id> --project-root "D:\foraiproject"` 获取下一轮澄清问题。
4. AI 根据 `docs/ai/request-templates.md` 和 `request-guide/v1` 输出判断任务类型并逐步提问。
5. 用户可以回答“不知道”；AI 给出安全默认建议，或说明为什么必须确认。
6. AI 汇总需求摘要，包括目标、对象、路径、输入素材、默认处理、风险点和验收方式。
7. 需求澄清和摘要记录在对应的 `question` 或 `auto` workflow 内完成。
8. 用户确认需求摘要后，AI 才能继续进入 `plan`、`change` profile 或修改执行阶段。
9. 修改型任务仍必须经过 `risk review`、必要的人工 gate、`workflow preflight` 和验证。
10. 执行完成后，AI 使用 `docs/ai/acceptance-checklists.md` 带用户验收。
```

- [ ] **Step 3: Validate docs**

Run:

```powershell
Get-Content -Encoding UTF8 -LiteralPath "D:\foraiproject\docs\ai\capability-registry.md" | Out-Null
Get-Content -Encoding UTF8 -LiteralPath "D:\foraiproject\docs\ai\workflows.md" | Out-Null
rg -n "request guide|request-guide/v1|Workflow Engine|risk review|workflow preflight|Unity Editor Adapter" docs\ai\capability-registry.md docs\ai\workflows.md
```

Expected: files are readable and key terms are present.

- [ ] **Step 4: Commit docs task**

Run:

```powershell
git add docs/ai/capability-registry.md docs/ai/workflows.md
git commit -m "docs: document request guide cli"
```

Expected: commit succeeds and includes only the two docs.

## Task 5: Final Validation

**Files:**
- Read: all files changed by Tasks 1-4

- [ ] **Step 1: Run full AI tool test suite**

Run:

```powershell
python -m pytest tools\ai\tests -q
```

Expected: all tests pass.

- [ ] **Step 2: Validate schemas by CLI**

Run:

```powershell
python tools\ai\ai.py validate file --schema request-guide/v1 --input artifacts\ai-runs\request-guide-sample.json --project-root "D:\foraiproject"
```

Expected: skip this exact command unless Task 5 first creates a sample file under `artifacts`; schema validation is already covered by tests. Do not create tracked sample files.

- [ ] **Step 3: Run manual CLI smoke checks**

Run:

```powershell
python tools\ai\ai.py request guide --intent "我想做一个背包界面" --run-id question-smoke --project-root "D:\foraiproject"
python tools\ai\ai.py request guide --intent "背包界面按钮点击没有反应" --project-root "D:\foraiproject"
python tools\ai\ai.py request guide --intent "帮我处理一下" --project-root "D:\foraiproject"
```

Expected:

- First command outputs `taskType: ui`.
- Second command outputs `taskType: bug`.
- Third command outputs `taskType: unknown` and question `common.task_type`.

- [ ] **Step 4: Scan changed files for unfinished markers**

Run:

```powershell
rg -n "T[B]D|TO[D]O|FIX[M]E|待[定]|占[位]" tools\ai\forai\request_guide.py tools\ai\tests\test_request_guide.py tools\ai\tests\test_cli.py tools\ai\tests\test_schemas.py tools\ai\schemas\request-guide.v1.schema.json tools\ai\schemas\request-guide-answers.v1.schema.json docs\ai\capability-registry.md docs\ai\workflows.md
```

Expected: exit code `1`, no output.

- [ ] **Step 5: Check git status**

Run:

```powershell
git status --short
```

Expected: no uncommitted changes after all task commits.

## Acceptance Criteria

- `python tools\ai\ai.py request guide --intent "我想做一个背包界面"` outputs valid `request-guide/v1` JSON.
- UI intent returns task type `ui` and at most three questions.
- Bug intent takes priority over UI terms.
- Unknown intent returns the common classification question.
- `--answers` skips answered questions.
- `--answers` runId mismatch fails with JSON error.
- Safe defaults include no Prefab overwrite when overwrite is unknown.
- Fully answered UI request returns `ready_for_summary`.
- Output validates against `request-guide/v1`.
- CLI remains read-only and does not modify Unity assets.
- Docs register the new capability and preserve workflow/risk/preflight/Unity Adapter boundaries.
