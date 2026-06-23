# AI 需求澄清 CLI 向导设计

日期：2026-06-23
项目：`D:\foraiproject`
关联目标：让本 Unity 工程成为对策划、美术等非工程用户友好、面向 AI 的工程。

## 目标

新增第一版只读 CLI 需求澄清向导，稳定回答“下一轮该问用户什么”。它把 `docs/ai/request-templates.md` 中的问答脚本落成机器可调用入口，让 Agent、CI、未来 MCP 或 Unity Editor UI 能复用同一个规则源。

第一版只做确定性规则和 JSON 输出，不调用 LLM，不修改 Unity 资产，不创建 Unity Editor 窗口。

## 当前缺口

当前项目已经具备以下基础：

- `docs/ai/user-guide.md` 告诉策划、美术可以先用一句话表达需求。
- `docs/ai/request-templates.md` 定义 UI、Prefab、美术资源、配置、Bug、只读检查六类提问脚本。
- `docs/ai/workflows.md` 明确需求澄清和摘要记录在 `question` 或 `auto` workflow 内完成。
- `tools/ai/ai.py` 已有 `workflow`、`scan`、`requirements`、`spec`、`plan`、`risk`、`unity` 等稳定入口。

缺口是：文档说明了 AI 应该继续提问，但工具层还没有一个稳定命令能根据用户一句话产出下一轮问题、默认建议和需求摘要。结果仍依赖 Agent 自行阅读文档并即兴执行，难以验证，也难以被未来 MCP 或 Unity Editor UI 复用。

## 设计原则

1. 用户只提供一句自然语言意图也可以开始。
2. CLI 只做只读分析，不执行修改。
3. CLI 输出机器可读 JSON，用户友好文本由上层 Agent 或 UI 呈现。
4. 每轮最多返回三个问题，优先短问题和选择题。
5. 用户回答“不知道”时，输出安全默认建议，而不是强迫用户补完整文档。
6. 需求澄清属于 workflow 内阶段，不能作为绕过 `Workflow Engine` 的前置聊天。
7. 输出只能作为后续 `intent-analysis`、`requirement-check`、`domain-spec`、`execution-plan` 的输入，不得绕过 `risk review`、`workflow preflight`、验证或 `Unity Editor Adapter`。

## 命令形态

新增 CLI 分组：

```powershell
python tools\ai\ai.py request guide --intent "<用户一句话意图>" --project-root "D:\foraiproject"
```

可选参数：

```powershell
python tools\ai\ai.py request guide `
  --intent "<用户一句话意图>" `
  --answers "<answers.json>" `
  --run-id <run-id> `
  --project-root "D:\foraiproject"
```

参数说明：

- `--intent`：用户自然语言意图，必填。
- `--answers`：上一轮问答结果 JSON，可选。
- `--run-id`：已有 workflow run id，可选；提供时输出应回显该值。
- `--project-root`：项目根目录，可选但推荐显式传入。

第一版不要求 CLI 自动创建 workflow。Agent 仍应先执行 `workflow begin --profile question` 或 `workflow begin --profile auto`，再调用 `request guide`。如果传入 `--run-id`，CLI 只回显并在输出中标记该澄清结果属于该 workflow。

## 输出协议

新增 schema：`request-guide/v1`。

示例输出：

```json
{
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
      "required": true
    },
    {
      "id": "ui.purpose",
      "prompt": "这个界面什么时候打开，给玩家完成什么事情？",
      "kind": "short_text",
      "options": [],
      "required": true
    },
    {
      "id": "ui.reference",
      "prompt": "有没有参考图、现有页面、Prefab 或素材路径？",
      "kind": "short_text",
      "options": ["没有", "不知道"],
      "required": false
    }
  ],
  "safeDefaults": [
    {
      "field": "prefabOverwrite",
      "value": "false",
      "reason": "未确认覆盖时默认不覆盖已有 Prefab。"
    }
  ],
  "known": {
    "goal": "做一个背包界面"
  },
  "unknowns": ["ui.kind", "ui.purpose"],
  "summary": null,
  "workflowProfileHint": "question",
  "nextAction": "ask_user"
}
```

当信息足够时：

```json
{
  "version": "request-guide/v1",
  "runId": "question-20260623-100000",
  "intent": "我想做一个背包界面",
  "taskType": "ui",
  "status": "ready_for_summary",
  "questions": [],
  "safeDefaults": [
    {
      "field": "prefabOverwrite",
      "value": "false",
      "reason": "用户未明确允许覆盖已有 Prefab。"
    }
  ],
  "known": {
    "goal": "做一个背包界面",
    "ui.kind": "新界面",
    "ui.purpose": "玩家查看道具列表"
  },
  "unknowns": [],
  "summary": {
    "taskType": "UI 页面新增或修改",
    "goal": "新增背包页面，用于查看道具列表。",
    "targetPath": "建议路径，待用户确认。",
    "inputs": [],
    "defaultHandling": ["默认不覆盖已有 Prefab。"],
    "risks": ["可能创建新 UI 脚本或 Prefab，执行前需要确认。"],
    "acceptance": ["页面能打开。", "道具列表能显示测试数据。"]
  },
  "workflowProfileHint": "plan",
  "nextAction": "confirm_summary"
}
```

## 状态定义

- `needs_clarification`：仍需继续问用户。
- `ready_for_summary`：已能生成需求摘要，但还不能执行修改。
- `blocked`：用户意图无法归类，或答案互相冲突，必须重新澄清。

第一版不输出 `ready_to_execute`。任何执行都必须由后续 workflow、artifact、risk review、gate、preflight 和验证决定。

## 任务类型识别

第一版使用规则识别，不调用模型。

任务类型：

- `ui`：包含界面、页面、按钮、弹窗、入口、UI、背包等词。
- `prefab`：包含 Prefab、预制体、组件、子物体、挂载、引用等词。
- `art_asset`：包含图标、立绘、音效、材质、模型、导入、整理资源等词。
- `config`：包含数值、配置、表格、ScriptableObject、JSON、道具属性等词。
- `bug`：包含报错、无反应、异常、复现、修复、崩溃、空引用等词。
- `read_only`：包含解释、检查、看看、说明、分析、只读等词。
- `unknown`：无法可靠识别。

识别冲突时优先级：

1. `bug`
2. `ui`
3. `prefab`
4. `art_asset`
5. `config`
6. `read_only`
7. `unknown`

如果识别为 `unknown`，第一问必须是通用分类问题：

```text
你这次想做的是哪一类？
1. 新增东西
2. 修改已有东西
3. 修复问题
4. 整理资源或文档
5. 只想了解现状
```

## 问题选择规则

每个任务类型维护一个问题序列。CLI 根据 `--answers` 中已回答字段跳过已知问题，最多返回前三个未回答问题。

第一版不做复杂依赖图，只做线性序列和少量默认值：

- UI：是否新建或修改、打开时机和用途、显示信息、交互、参考资源、是否允许创建脚本或 Prefab、验收方式。
- Prefab：创建或修改、使用场景、路径、组件和引用、是否允许覆盖、命名规则、验收方式。
- 美术资源：资源类型、来源和目标路径、命名规则、Addressables、是否允许移动或覆盖、验收方式。
- 配置：目标系统、当前值和目标值、来源位置、线上或热更新影响、验收方式。
- Bug：异常现象、复现步骤、期望结果、实际结果、是否稳定复现、近期改动、验收方式。
- 只读检查：目标对象、解释方式、是否只读。

## Answers 输入格式

`--answers` 指向 JSON 文件：

```json
{
  "version": "request-guide-answers/v1",
  "runId": "question-20260623-100000",
  "answers": {
    "ui.kind": "新界面",
    "ui.purpose": "玩家查看道具列表",
    "ui.reference": "不知道"
  }
}
```

规则：

- `answers` 的 key 使用问题 `id`。
- 值可以是字符串、数字、布尔值或字符串数组。
- 用户回答“不知道”时，CLI 不应直接失败；能默认的字段进入 `safeDefaults`，必须确认的字段保留在 `unknowns`。
- `runId` 如果存在且与命令行 `--run-id` 不一致，应返回失败。

## 与 Workflow Engine 的关系

`request guide` 是 workflow 内的只读辅助命令。

推荐顺序：

```powershell
python tools\ai\ai.py workflow begin --profile question --intent "<用户意图>" --project-root "D:\foraiproject"
python tools\ai\ai.py request guide --intent "<用户意图>" --run-id <run-id> --project-root "D:\foraiproject"
```

如果用户确认需求摘要，后续再进入 `plan` 或 `change` profile。`request guide` 的输出不能让 `question` workflow 执行修改，也不能替代 `requirement-check/v1`、`domain-spec/v1` 或 `execution-plan/v1`。

## 安全边界

`request guide` 禁止：

- 修改任何文件。
- 创建、移动、删除或覆盖 Unity 资产。
- 直接编辑 `.unity`、`.prefab`、`.asset`、`.meta`、`ProjectSettings`、`Packages/manifest.json` 或 `packages-lock.json`。
- 自动批准风险。
- 自动执行 `workflow preflight`。
- 将需求摘要等同于执行计划。

`request guide` 必须：

- 对覆盖、删除、移动、场景、Prefab、ProjectSettings、Package manifest、运行时行为变更输出风险提示。
- 对不明确路径输出“建议路径，待用户确认”，而不是直接当成已确认事实。
- 对运行时行为和 Bug 修复提示后续需要验证。
- 保留 `Workflow Engine`、`risk review`、人工 gate、`workflow preflight`、验证和 `Unity Editor Adapter` 边界。

## 文件结构建议

后续实施计划可考虑新增：

```text
tools/ai/forai/request_guide.py
tools/ai/schemas/request-guide.v1.schema.json
tools/ai/schemas/request-guide-answers.v1.schema.json
tools/ai/tests/test_request_guide.py
```

并修改：

```text
tools/ai/ai.py
docs/ai/capability-registry.md
docs/ai/workflows.md
```

本设计规格不直接实施这些文件。

## 测试策略

后续实施应至少覆盖：

- UI 意图能识别为 `ui`，返回前三个 UI 问题。
- Bug 意图优先识别为 `bug`。
- 未知意图返回通用分类问题。
- `--answers` 能跳过已回答问题。
- “不知道”能产生安全默认建议。
- 信息足够时输出 `ready_for_summary` 和需求摘要。
- `runId` 不匹配时返回失败。
- JSON 输出符合 `request-guide/v1` schema。
- CLI help 中出现 `request guide`。

## 验收标准

本设计规格完成后，应满足：

- 明确了 `request guide` 的目标、命令形态、输出协议和状态。
- 明确第一版只读、规则型、不调用 LLM、不做 Unity Editor UI。
- 明确任务类型识别、问题选择、answers 输入和 summary 输出。
- 明确该命令属于 workflow 内辅助步骤，不能绕过 `Workflow Engine`。
- 明确不降低 `risk review`、人工 gate、`workflow preflight`、验证和 `Unity Editor Adapter` 边界。
- 给出后续实施应创建或修改的文件建议。
- 文档可正常读取，且不包含未完成标记。
