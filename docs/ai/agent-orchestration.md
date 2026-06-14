# Agent 编排 v1

本文件定义第一版人工关卡 Agent 编排。核心原则是：LLM 只产出结构化 artifact；CLI 负责校验、记录、风险审查和 gate 状态；Unity 修改仍只能经 `Unity Editor Adapter`。

## Universal Workflow Engine v2

v2 将所有请求统一纳入 `Workflow Engine`，但按风险和目的分成三个 profile：

- `question`：用于解释、分析和问题思考，只允许产出报告，不允许修改。
- `plan`：用于计划模式和方案设计，必须产出并校验 `intent-analysis`、`context-pack`、`requirement-check`、`domain-spec`、`execution-plan` 和 `risk-review`，不允许执行修改。
- `change`：用于修改请求，必须具备完整 artifact 链、risk review，并在需要时通过 preview 和人工 gate。

入口命令：

```powershell
python tools\ai\ai.py workflow begin --profile question --intent "<intent>" --project-root "D:\foraiproject"
python tools\ai\ai.py workflow begin --profile plan --intent "<intent>" --project-root "D:\foraiproject"
python tools\ai\ai.py workflow begin --profile change --intent "<intent>" --project-root "D:\foraiproject"
python tools\ai\ai.py workflow next --run-id <run-id> --project-root "D:\foraiproject"
python tools\ai\ai.py workflow attach-artifact --run-id <run-id> --name <artifact-name> --schema <schema-id> --input <artifact.json> --project-root "D:\foraiproject"
python tools\ai\ai.py workflow preflight --run-id <run-id> --project-root "D:\foraiproject"
python tools\ai\ai.py workflow complete --run-id <run-id> --summary "<summary>" --project-root "D:\foraiproject"
```

`workflow-state/v2` 记录 `profile`、`phase`、`nextAction`、`intent`、时间戳和 artifact/gate/blocker。artifact 可记录 `artifactRunId`；`workflow next` 会阻止 artifact schema 失败、路径缺失或 `runId` 不匹配。新 Engine 默认写入 v2；旧 v1 state 在被新命令读取时会迁移为 v2。

## LLM 介入层

LLM 可以介入以下层级，但输出必须落到 schema 化 artifact 或人类可审阅报告：

- `IntentAgent`：解析用户意图，输出 `intent-analysis/v1`。
- `RequirementAgent`：检查需求完整性，输出 `requirement-check/v1`。
- `SpecAgent`：生成或更新 domain spec，输出 `domain-spec/v1`。
- `PlanAgent`：生成 `execution-plan/v1`，步骤只能声明 `read_only`、`cli`、`unity_adapter` 或 `validation`，并填写 `command`、`inputs`、`outputs`、`dryRunSupported` 和 `validation`。
- `RepairAgent`：在验证失败后提出最小修复建议，不能直接执行修改。
- `ReportAgent`：汇总 artifact、验证证据、gate 状态和剩余 blocker。

LLM 不直接执行 `CLI`，不直接修改 Unity 资产，不替代 schema 校验、编译验证或人工批准。

## 确定性执行层

`tools/ai/ai.py` 是 v1 的稳定入口：

```powershell
python tools\ai\ai.py workflow begin --profile change --intent "<intent>" --run-id <run-id> --project-root "D:\foraiproject"
python tools\ai\ai.py workflow attach-artifact --run-id <run-id> --name intent-analysis --schema intent-analysis/v1 --input <intent-analysis.json> --project-root "D:\foraiproject"
python tools\ai\ai.py scan context --run-id <run-id> --project-root "D:\foraiproject"
python tools\ai\ai.py requirements check --input <requirement-check.json> --project-root "D:\foraiproject"
python tools\ai\ai.py workflow attach-artifact --run-id <run-id> --name requirement-check --schema requirement-check/v1 --input <requirement-check.json> --project-root "D:\foraiproject"
python tools\ai\ai.py spec validate --input <domain-spec.json> --project-root "D:\foraiproject"
python tools\ai\ai.py workflow attach-artifact --run-id <run-id> --name domain-spec --schema domain-spec/v1 --input <domain-spec.json> --project-root "D:\foraiproject"
python tools\ai\ai.py plan validate --input <execution-plan.json> --project-root "D:\foraiproject"
python tools\ai\ai.py validate file --schema context-pack/v1 --input <path> --project-root "D:\foraiproject"
python tools\ai\ai.py risk review --run-id <run-id> --plan <execution-plan.json> --project-root "D:\foraiproject"
python tools\ai\ai.py gate approve --run-id <run-id> --gate risk-review --reason "<reason>" --project-root "D:\foraiproject"
python tools\ai\ai.py unity status --project-root "D:\foraiproject"
python tools\ai\ai.py unity compile --run-id <run-id> --project-root "D:\foraiproject"
```

CLI 负责：

- 生成 `context-pack/v1`。
- 校验 JSON artifact。
- 通过 `workflow attach-artifact` 将外部 Agent 产物登记到 workflow state。
- 将每次运行状态写入 `artifacts/ai-runs/<run-id>/workflow-state.json`。
- 对 `execution-plan/v1` 产出 `risk-review/v1`。
- 记录人工 gate 的 `pending`、`approved` 或 `rejected` 状态。
- 将 Unity 编译结果归一化为 `validation-report/v1`。

## 人工关卡

以下情况必须进入人工关卡：

- `risk review` 返回 `medium`、`high` 或 `blocked`。
- 计划包含 Unity 资产、场景、Prefab、ProjectSettings 或 package manifest 相关变更。
- 多个 Unity 实例在线但未指定目标。
- dry-run 或 diff preview 不能证明变更范围。

`blocked` 风险不能靠 `gate approve` 直接变成可执行动作；需要先修改 plan，让风险审查不再返回 `blocked`。

`workflow preflight` 是修改执行前的硬检查：

- `question` 和 `plan` profile 总是拒绝修改执行。
- `change` profile 缺少 `intent-analysis`、`context-pack`、`requirement-check`、`domain-spec`、`execution-plan` 或 `risk-review` 时拒绝执行。
- artifact 路径缺失、schema 失败或 `runId` 不匹配时拒绝执行。
- `risk-review/v1` 返回 `blocked` 时拒绝执行。
- `confirmationRequired` 为 `true` 时必须先有 `risk-review` gate 的 `approved` 状态。
- `previewRequired` 为 `true` 时必须先有 `previewArtifacts` 声明的 evidence artifact。

## 禁止动作

- Agent 不能直接编辑 `.unity`、`.prefab`、`.asset`、`.meta` 或 `ProjectSettings/*.asset`。
- Agent 不能绕过 `risk review` 执行修改型步骤。
- Agent 不能把 Gateway 返回的 `SecurityCheck` 当作普通编译错误处理。
- Agent 不能在未得到用户明确判断时切换分支、创建并行 worktree 或迁移当前任务状态。

## 运行证据

每个有 `run-id` 的运行默认写入：

```text
artifacts/ai-runs/<run-id>/
  workflow-state.json
  intent-analysis.json
  context-pack.json
  requirement-check.json
  domain-spec.json
  execution-plan.json
  risk-review.json
  validation-report.json
```

`workflow-state/v1` 只记录机器可读状态，不保存长篇推理。报告层可以引用这些 artifact，但不能伪造未执行的验证结果。
