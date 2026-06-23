from __future__ import annotations

from typing import Any


QUESTION_LIMIT = 3


Question = dict[str, Any]


QUESTION_BANK: dict[str, list[Question]] = {
    "ui": [
        {
            "id": "ui.target",
            "label": "目标界面",
            "prompt": "这个界面给玩家完成什么操作？",
            "kind": "text",
            "required": True,
            "options": [],
        },
        {
            "id": "ui.reference",
            "label": "参考样式",
            "prompt": "有没有现有界面、截图或竞品参考？没有也可以回答“无”。",
            "kind": "text",
            "required": True,
            "options": [],
        },
        {
            "id": "ui.asset_source",
            "label": "素材来源",
            "prompt": "按钮、图标、背景等素材来自现有项目、你提供的新图，还是需要先用临时素材？",
            "kind": "choice",
            "required": True,
            "options": ["现有项目素材", "提供新素材", "先用临时素材"],
        },
        {
            "id": "ui.interaction",
            "label": "交互",
            "prompt": "玩家点击、拖拽或切换时分别应该发生什么？",
            "kind": "multiline",
            "required": True,
            "options": [],
        },
    ],
    "bug": [
        {
            "id": "bug.repro_steps",
            "label": "复现步骤",
            "prompt": "从打开游戏到出现问题，需要按哪些步骤操作？",
            "kind": "multiline",
            "required": True,
            "options": [],
        },
        {
            "id": "bug.expected",
            "label": "期望表现",
            "prompt": "你期望它应该表现成什么样？",
            "kind": "text",
            "required": True,
            "options": [],
        },
        {
            "id": "bug.actual",
            "label": "实际表现",
            "prompt": "现在实际看到的表现、报错或截图是什么？",
            "kind": "multiline",
            "required": True,
            "options": [],
        },
        {
            "id": "bug.scope",
            "label": "影响范围",
            "prompt": "这个问题只在某个场景、角色、设备或操作下出现吗？",
            "kind": "text",
            "required": False,
            "options": [],
        },
    ],
    "prefab": [
        {
            "id": "prefab.target",
            "label": "目标 Prefab",
            "prompt": "要创建或修改哪个 Prefab？如果是新 Prefab，请描述名称和用途。",
            "kind": "text",
            "required": True,
            "options": [],
        },
        {
            "id": "prefab.components",
            "label": "组件需求",
            "prompt": "它需要哪些组件、子物体、挂点、碰撞或脚本？",
            "kind": "multiline",
            "required": True,
            "options": [],
        },
        {
            "id": "prefab.asset_source",
            "label": "素材来源",
            "prompt": "模型、贴图、特效或图标来自哪里？",
            "kind": "text",
            "required": True,
            "options": [],
        },
        {
            "id": "prefab.overwrite",
            "label": "覆盖确认",
            "prompt": "如果目标 Prefab 已存在，是否允许覆盖？",
            "kind": "choice",
            "required": True,
            "options": ["不覆盖，先生成新版本", "允许覆盖", "不确定"],
        },
    ],
    "art": [
        {
            "id": "art.asset_type",
            "label": "资源类型",
            "prompt": "这次处理的是图片、图标、立绘、模型、材质、动画还是特效？",
            "kind": "choice",
            "required": True,
            "options": ["图片/图标", "立绘", "模型", "材质", "动画", "特效"],
        },
        {
            "id": "art.source_path",
            "label": "源文件",
            "prompt": "源文件放在哪个路径？如果还没导入，请说明文件名和来源。",
            "kind": "path",
            "required": True,
            "options": [],
        },
        {
            "id": "art.usage",
            "label": "使用位置",
            "prompt": "这些资源会用在哪个界面、角色、场景或 Prefab 上？",
            "kind": "text",
            "required": True,
            "options": [],
        },
        {
            "id": "art.import_settings",
            "label": "导入设置",
            "prompt": "是否有分辨率、压缩、Sprite、透明通道、材质或平台设置要求？",
            "kind": "multiline",
            "required": False,
            "options": [],
        },
    ],
    "scene": [
        {
            "id": "scene.target",
            "label": "目标场景",
            "prompt": "要处理哪个场景？如果是新场景，请说明名称和用途。",
            "kind": "text",
            "required": True,
            "options": [],
        },
        {
            "id": "scene.change",
            "label": "场景变化",
            "prompt": "场景里需要新增、删除或调整哪些对象？",
            "kind": "multiline",
            "required": True,
            "options": [],
        },
        {
            "id": "scene.confirmation",
            "label": "场景确认",
            "prompt": "场景变更会影响当前编辑状态，是否允许通过 Unity Editor Adapter 执行？",
            "kind": "choice",
            "required": True,
            "options": ["先预览", "允许执行", "不确定"],
        },
    ],
    "system": [
        {
            "id": "system.goal",
            "label": "系统目标",
            "prompt": "这套系统最终要支持哪类玩法、工具或工作流？",
            "kind": "text",
            "required": True,
            "options": [],
        },
        {
            "id": "system.scope",
            "label": "范围",
            "prompt": "这次只做文档、编辑器工具、运行时代码、数据结构，还是完整链路？",
            "kind": "choice",
            "required": True,
            "options": ["文档", "编辑器工具", "运行时代码", "数据结构", "完整链路"],
        },
        {
            "id": "system.entry",
            "label": "入口",
            "prompt": "使用者从哪里触发它：CLI、Unity 菜单、Inspector、场景对象还是游戏内 UI？",
            "kind": "choice",
            "required": True,
            "options": ["CLI", "Unity 菜单", "Inspector", "场景对象", "游戏内 UI"],
        },
    ],
    "unknown": [
        {
            "id": "intent.goal",
            "label": "目标",
            "prompt": "你希望 AI 最终帮你完成什么？请用一句话描述结果。",
            "kind": "text",
            "required": True,
            "options": [],
        },
        {
            "id": "intent.target",
            "label": "对象",
            "prompt": "这件事影响哪个界面、角色、场景、Prefab、资源或系统？",
            "kind": "text",
            "required": True,
            "options": [],
        },
        {
            "id": "intent.evidence",
            "label": "参考或现象",
            "prompt": "有没有截图、参考、报错、现象描述或现有路径？",
            "kind": "multiline",
            "required": False,
            "options": [],
        },
    ],
}


KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    ("bug", ("bug", "报错", "错误", "没反应", "没有反应", "异常", "崩溃", "修复", "broken", "error")),
    ("prefab", ("prefab", "预制体", "道具", "挂点")),
    ("scene", ("scene", "场景", "关卡", "地图")),
    ("ui", ("ui", "界面", "按钮", "面板", "窗口", "hud", "背包", "菜单")),
    ("art", ("美术", "素材", "图片", "图标", "立绘", "模型", "贴图", "材质", "动画", "特效", "导入")),
    ("system", ("系统", "流程", "框架", "工具", "管线", "生成器", "workflow", "cli")),
]


def build_request_guide(
    intent: str,
    *,
    answers: dict[str, Any] | None = None,
    run_id: str | None = None,
) -> dict[str, Any]:
    normalized_intent = intent.strip()
    known = _known_answers(answers or {})
    task_type = _classify(normalized_intent)
    questions = _next_questions(task_type, known)

    if not normalized_intent:
        status = "blocked"
        workflow_profile = "question"
        next_action = "revise_request"
    elif questions:
        status = "needs_clarification"
        workflow_profile = "question"
        next_action = "ask_user"
    elif _has_defaulted_required_answer(task_type, known):
        status = "defaultable"
        workflow_profile = "plan"
        next_action = "begin_workflow"
    else:
        status = "ready"
        workflow_profile = "plan"
        next_action = "begin_workflow"

    payload: dict[str, Any] = {
        "version": "request-guide/v1",
        "intent": normalized_intent,
        "taskType": task_type,
        "status": status,
        "workflowProfileHint": workflow_profile,
        "known": known,
        "unknowns": [question["id"] for question in questions if question["required"]],
        "questions": questions,
        "safeDefaults": _safe_defaults(task_type, known),
        "summary": _summary(normalized_intent, task_type, known, status, workflow_profile),
        "nextAction": next_action,
    }
    if run_id:
        payload["runId"] = run_id
    return payload


def validate_answers_run_id(payload: dict[str, Any], run_id: str | None) -> None:
    answer_run_id = payload.get("runId")
    if run_id and answer_run_id and answer_run_id != run_id:
        raise ValueError(f"runId mismatch: answers payload is {answer_run_id!r}, CLI run-id is {run_id!r}")


def _classify(intent: str) -> str:
    if not intent:
        return "unknown"
    lowered = intent.lower()
    for task_type, keywords in KEYWORDS:
        if any(keyword in lowered for keyword in keywords):
            return task_type
    return "unknown"


def _known_answers(answers: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in answers.items() if not _is_blank(value)}


def _next_questions(task_type: str, known: dict[str, Any]) -> list[Question]:
    unanswered = [
        dict(question)
        for question in QUESTION_BANK[task_type]
        if question["id"] not in known
    ]
    return unanswered[:QUESTION_LIMIT]


def _safe_defaults(task_type: str, known: dict[str, Any]) -> list[dict[str, str]]:
    defaults = {
        "ui": [
            {
                "field": "ui.implementation",
                "value": "UGUI",
                "reason": "当前项目已启用 com.unity.ugui，默认优先复用 UGUI。",
            }
        ],
        "bug": [
            {
                "field": "bug.priority",
                "value": "normal",
                "reason": "未提供阻断信息时按普通优先级排查。",
            }
        ],
        "prefab": [
            {
                "field": "prefab.overwrite",
                "value": "不覆盖，先生成新版本",
                "reason": "Prefab 覆盖属于高风险操作，默认不覆盖。",
            }
        ],
        "art": [
            {
                "field": "art.import_mode",
                "value": "保守导入，不覆盖原资源",
                "reason": "美术资源导入默认避免破坏已有资产。",
            }
        ],
        "scene": [
            {
                "field": "scene.execution",
                "value": "先预览，再执行",
                "reason": "场景变更需要确认和预览证据。",
            }
        ],
        "system": [
            {
                "field": "system.first_step",
                "value": "先写 plan，再进入 change workflow",
                "reason": "系统级改动通常影响范围较大，需要先规划。",
            }
        ],
        "unknown": [
            {
                "field": "workflow.profile",
                "value": "question",
                "reason": "目标不明确时只能进入问题澄清，不能执行修改。",
            }
        ],
    }
    return [
        default
        for default in defaults[task_type]
        if default["field"] not in known or _is_uncertain(known[default["field"]])
    ]


def _summary(
    intent: str,
    task_type: str,
    known: dict[str, Any],
    status: str,
    workflow_profile: str,
) -> dict[str, Any]:
    return {
        "ready": status in {"ready", "defaultable"},
        "suggestedProfile": workflow_profile,
        "taskType": task_type,
        "intent": intent,
        "knownCount": len(known),
    }


def _has_defaulted_required_answer(task_type: str, known: dict[str, Any]) -> bool:
    required_question_ids = {
        question["id"]
        for question in QUESTION_BANK[task_type]
        if question["required"]
    }
    return any(_is_uncertain(known.get(question_id)) for question_id in required_question_ids)


def _is_blank(value: Any) -> bool:
    return isinstance(value, str) and not value.strip()


def _is_uncertain(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    normalized = value.strip().lower()
    return normalized in {"不知道", "不确定", "无", "none", "unknown", "n/a"}
