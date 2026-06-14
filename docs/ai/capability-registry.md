# AI 能力注册表

本文件声明项目中每类自动化能力可以做什么，以及不能做什么。

## 只读能力

### Project Context Scan

允许：

- 读取项目文件。
- 读取 Unity package manifest 和 project settings。
- 汇总场景、Prefab、脚本和测试。
- 查询 Unity gateway 状态。

禁止：

- 修改文件。
- 触发 Unity 变更。

### Requirement Check

允许：

- 判断用户意图是否完整。
- 标记假设。
- 请求澄清。

禁止：

- 执行变更。
- 编造不存在的 Unity 状态。

## 规划能力

### Domain Spec Generation

允许：

- 产出 desired-state spec。
- 引用已批准的目标路径。
- 定义验收标准。

禁止：

- 为 Unity 修改夹带任意 C# 片段。
- 直接编辑资产。

### Execution Plan Generation

允许：

- 产出有序步骤。
- 将每个步骤分类为 read-only、CLI、Unity Adapter 或 validation。

禁止：

- 包含对 `.unity`、`.prefab`、`.asset`、`.meta` 或 `ProjectSettings` 的直接编辑。

## 修改能力

### Normal File Edit

允许：

- 文档。
- AI schemas。
- 已批准计划范围内的源码。
- 测试。

需要验证：

- schema 文件要做 JSON 解析。
- 源码变更要做编译或测试。

### Unity Editor Adapter

允许：

- 创建或修改 Unity 资产。
- 创建或修改 Prefab。
- 查询仅编辑器可见的状态。
- 触发 `AssetDatabase.Refresh`。
- 触发脚本编译。
- 运行编辑器侧验证。

必须：

- 在目标可能有歧义时显式传入 `--project-root`。
- 返回包含 request ID、state、diagnostics 和 errors 的结构化结果。

## 未来能力

### MCP Server

MCP 可以在 CLI 和 schemas 稳定后包装 CLI。MCP tools 必须保留与 CLI 相同的风险策略和确认要求。

## 确定性 AI CLI

### Workflow State

入口：

- `python tools\ai\ai.py workflow init`
- `python tools\ai\ai.py workflow begin`
- `python tools\ai\ai.py workflow next`
- `python tools\ai\ai.py workflow attach-artifact`
- `python tools\ai\ai.py workflow preflight`
- `python tools\ai\ai.py workflow complete`
- `python tools\ai\ai.py workflow status`

允许：

- 创建 `workflow-state/v1`。
- 创建和推进 `workflow-state/v2`。
- 查询 `artifacts/ai-runs/<run-id>/workflow-state.json`。
- 按 `question`、`plan`、`change` profile 计算 `phase` 和 `nextAction`。
- 通过 `workflow attach-artifact` 校验并登记 `intent-analysis`、`requirement-check`、`domain-spec`、`execution-plan`、`risk-review` 等 JSON artifact。
- 在修改型执行前检查 artifact 缺失、schema 失败、`runId` 不匹配、risk review、preview evidence 和 gate 状态。

禁止：

- 代替人工批准。
- 绕过风险审查直接标记执行完成。
- 让 `question` 或 `plan` profile 执行修改。

### Requirement/Spec/Plan Validation

入口：

- `python tools\ai\ai.py requirements check`
- `python tools\ai\ai.py spec validate`
- `python tools\ai\ai.py plan validate`

允许：

- 校验 `requirement-check/v1`、`domain-spec/v1`、`execution-plan/v1`。
- 返回机器可读校验状态。

禁止：

- 自动生成或修正 LLM artifact。
- 绕过 `workflow attach-artifact` 直接修改 workflow state。

### Artifact Validation

入口：

- `python tools\ai\ai.py validate file`

允许：

- 校验 `tools/ai/schemas` 下登记的 JSON artifact。
- 对 schema 额外字段、缺失字段和类型错误返回失败状态。

禁止：

- 自动修正 LLM artifact。

### Context Scan

入口：

- `python tools\ai\ai.py scan context`

允许：

- 只读扫描 Unity 版本、package manifest、AI 文档和 schema 列表。
- 生成 `context-pack/v1`。

禁止：

- 修改 Unity 工程文件。

### Risk Review

入口：

- `python tools\ai\ai.py risk review`

允许：

- 读取 `execution-plan/v1`。
- 输出 `risk-review/v1`。
- 阻止 parent-directory path、CLI 直改 Unity YAML 或 metadata 的计划。
- 将 ProjectSettings、package manifest、Prefab/scene 变更、覆盖/移动/删除/批量操作标记为 high risk。
- 对 high risk 输出 `previewRequired` 和 `previewArtifacts`，供 `workflow preflight` 校验 preview evidence。

禁止：

- 将 `blocked` 风险转成可执行动作。

### Human Gate

入口：

- `python tools\ai\ai.py gate approve`
- `python tools\ai\ai.py gate reject`

允许：

- 记录人工审批结论。

禁止：

- 替代用户对分支切换、并行 worktree、场景变更、Prefab 覆盖、ProjectSettings 变更或 package manifest 变更的明确判断。

### Unity Read/Validate

入口：

- `python tools\ai\ai.py unity status`
- `python tools\ai\ai.py unity compile`

允许：

- 查询 Gateway status。
- 调用编译检查并输出 `validation-report/v1`。

禁止：

- 通过 CLI 直接创建、修改、移动或删除 Unity 资产。
- 将 Gateway 返回的 `SecurityCheck` 当作普通编译错误。
