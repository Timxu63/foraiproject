# AI 工作流

本文件定义 AI 辅助变更的标准工作流。

## 非工程用户需求澄清工作流

适用于策划、美术用自然语言提出的模糊需求。

1. 用户先用一句话描述想法。
2. AI 调用 `python tools\ai\ai.py request guide --intent "<用户意图>" --project-root "D:\foraiproject"` 获取 `request-guide/v1`。
3. AI 根据 `request-guide/v1.questions` 逐轮提问，每轮最多 3 个问题。
4. 用户可以回答“不知道”；AI 根据 `safeDefaults` 给出安全默认建议，或说明为什么必须确认。
5. 如需继续澄清，AI 将已回答内容写成 `request-guide-answers/v1`，再调用 `request guide --answers <answers.json>` 获取下一轮问题。
6. AI 结合 `docs/ai/request-templates.md` 汇总需求摘要，包括目标、对象、路径、输入素材、默认处理、风险点和验收方式。
7. 需求澄清和摘要记录在对应的 `question` 或 `auto` workflow 内完成。
8. 用户确认需求摘要后，AI 才能继续进入 `plan`、`change` profile 或修改执行阶段。
9. 修改型任务仍必须经过 `risk review`、必要的人工 gate、`workflow preflight` 和验证。
10. 执行完成后，AI 使用 `docs/ai/acceptance-checklists.md` 带用户验收。

该工作流只降低表达门槛，不降低安全要求。

## 标准修改工作流

```text
User Intent
  -> Intent Analysis
  -> Context Pack
  -> Requirement Completeness Check
  -> Gap Analysis
  -> Clarification or Defaulting
  -> Domain Spec
  -> Spec Validation
  -> Execution Plan
  -> Risk Review
  -> Dry Run or Diff Preview
  -> User Confirmation for high risk
  -> CLI Execution
  -> Unity Editor Adapter Execution
  -> Compile, Test, Validation
  -> Evidence Report
  -> Repair Loop
```

这些阶段名保留英文，便于和 schema、CLI 输出、自动化日志保持一致。

## 纯文档工作流

适用于 docs、schemas 和项目说明文件。

1. 读取已批准的设计或 spec 上下文。
2. 编写范围明确的文档或 schema 文件。
3. 如果存在 JSON 文件，执行 JSON 解析检查。
4. 扫描未完成标记。
5. 报告变更文件和验证结果。

## Unity 资产工作流

适用于会修改场景、Prefab、ScriptableObject、资产或 ProjectSettings 的请求。

1. 构建 `context pack`。
2. 生成 `domain spec`。
3. 校验 `domain spec`。
4. 生成 `execution plan`。
5. 进行风险分级。
6. 对高风险动作请求确认。
7. 通过 `Unity Editor Adapter` 执行。
8. 在需要时触发资产刷新或脚本编译。
9. 运行编译验证。
10. 在相关时运行 EditMode 或 PlayMode 测试。
11. 报告证据。

## 修复工作流

适用于验证失败后的修复。

1. 保留失败运行的证据。
2. 判断失败类型：schema、gateway、compile、test 或 runtime。
3. 产出修复计划。
4. 执行最小安全修复。
5. 重新运行失败的验证。
6. 报告原始失败、修复动作和最终验证结果。

## 多 Unity 目标规则

当多个 Unity 实例在线时，每个 Unity 操作都必须指定以下任一目标：

- `--project-root "D:\foraiproject"`
- 稳定的 `--unity-id`

如果无法明确目标，则阻止执行，直到用户选择目标。

## 人工关卡 Agent 编排工作流

适用于需要让 LLM 参与分析、规格、计划或报告，但执行必须由 CLI、人工 gate 和 Unity Editor Adapter 控制的任务。

```text
User Intent
  -> LLM Artifact Draft
  -> CLI Schema Validation
  -> Context Pack
  -> Execution Plan
  -> Risk Review
  -> Human Gate
  -> Deterministic Execution
  -> Unity Adapter when needed
  -> Validation Report
  -> Evidence Report
```

推荐命令顺序：

```powershell
python tools\ai\ai.py workflow begin --profile change --intent "<intent>" --run-id <run-id> --project-root "D:\foraiproject"
python tools\ai\ai.py workflow attach-artifact --run-id <run-id> --name intent-analysis --schema intent-analysis/v1 --input <intent-analysis.json> --project-root "D:\foraiproject"
python tools\ai\ai.py scan context --run-id <run-id> --project-root "D:\foraiproject"
python tools\ai\ai.py workflow attach-artifact --run-id <run-id> --name requirement-check --schema requirement-check/v1 --input <requirement-check.json> --project-root "D:\foraiproject"
python tools\ai\ai.py workflow attach-artifact --run-id <run-id> --name domain-spec --schema domain-spec/v1 --input <domain-spec.json> --project-root "D:\foraiproject"
python tools\ai\ai.py risk review --run-id <run-id> --plan <execution-plan.json> --project-root "D:\foraiproject"
python tools\ai\ai.py gate approve --run-id <run-id> --gate risk-review --reason "<reason>" --project-root "D:\foraiproject"
python tools\ai\ai.py workflow preflight --run-id <run-id> --project-root "D:\foraiproject"
python tools\ai\ai.py workflow status --run-id <run-id> --project-root "D:\foraiproject"
```

LLM 只能产出或修订 artifact；`SecurityCheck` 必须作为安全拦截处理，不得当作普通编译错误继续推进。

## Universal Workflow Profiles

所有 AI 请求先进入 `workflow begin`，再按 profile 推进：

```text
question:
  Intent
  -> Optional Context
  -> Report
  -> Complete

plan:
  Intent
  -> Context Pack
  -> Requirement Check
  -> Domain Spec
  -> Execution Plan
  -> Risk Review
  -> Report
  -> Complete

change:
  Intent
  -> Context Pack
  -> Requirement Check
  -> Domain Spec
  -> Execution Plan
  -> Risk Review
  -> Dry Run or Diff Preview when required
  -> Human Gate when required
  -> Preflight
  -> Execution
  -> Validation
  -> Report
  -> Complete
```

推荐入口：

```powershell
python tools\ai\ai.py workflow begin --profile auto --intent "<intent>" --project-root "D:\foraiproject"
python tools\ai\ai.py workflow next --run-id <run-id> --project-root "D:\foraiproject"
python tools\ai\ai.py workflow attach-artifact --run-id <run-id> --name <artifact-name> --schema <schema-id> --input <artifact.json> --project-root "D:\foraiproject"
```

修改型执行前必须通过：

```powershell
python tools\ai\ai.py workflow preflight --run-id <run-id> --project-root "D:\foraiproject"
```

`workflow attach-artifact` 会校验 JSON schema、复制 artifact 到 `artifacts/ai-runs/<run-id>/`，并检查带 `runId` 的 artifact 是否匹配当前 workflow。`workflow next` 和 `workflow preflight` 会阻止缺失、schema 失败或 `runId` 不匹配的 artifact。

`execution-plan/v1` 的每个 step 必须包含 `command`、`inputs`、`outputs`、`dryRunSupported` 和 `validation`。`risk-review/v1` 会声明 `gateReason`、`previewRequired` 和 `previewArtifacts`；当 `previewRequired` 为 `true` 时，preflight 必须看到对应 preview artifact 后才允许执行。
