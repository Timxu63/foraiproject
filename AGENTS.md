# AI 项目规范

本 Unity 项目支持 AI 辅助开发。任何 Agent 在读取、规划、编辑或执行变更前，都必须遵守本文件。

## 项目身份

- 项目根目录：`D:\foraiproject`
- Unity 版本：2022.3.62f2
- 当前 Unity 网关：`Packages/com.forai.roslyn-gateway`
- 已批准设计规格：`docs/superpowers/specs/2026-06-08-ai-friendly-unity-engineering-design.md`

## 文档语言规范

- 后续新增或更新的 Markdown 文档默认使用中文。
- 路径、命令、CLI 子命令、schema id、JSON 字段名、代码标识符、Unity API 名称保留英文。
- 面向机器读取的 JSON、schema、manifest、代码文件按其生态约定使用英文。
- 引用英文资料时，用中文解释结论，必要的原文术语保留英文。

## 必须遵守的边界

- `Workflow Engine` 只调度阶段，不直接调用 Unity API。
- `Agent` 只分析上下文并产出结构化结果，不直接修改 Unity 资产。
- `CLI` 是人、Agent、CI 和未来 MCP 工具的稳定入口。
- `Unity Editor Adapter` 是唯一允许创建、修改、移动或删除 Unity 资产、场景、Prefab、ProjectSettings 或编辑器状态的执行层。

## Universal Workflow Engine

所有 AI 请求都必须进入 `Workflow Engine`，但按任务类型使用不同 profile：

- 问题思考：先执行 `python tools\ai\ai.py workflow begin --profile question --intent "<用户意图>" --project-root "D:\foraiproject"`。
- 计划模式：先执行 `python tools\ai\ai.py workflow begin --profile plan --intent "<用户意图>" --project-root "D:\foraiproject"`。
- 修改请求：先执行 `python tools\ai\ai.py workflow begin --profile change --intent "<用户意图>" --project-root "D:\foraiproject"`。

修改型任务在任何文件编辑、Unity 操作或执行型命令前，必须让同一 `run-id` 通过：

```powershell
python tools\ai\ai.py workflow preflight --run-id <run-id> --project-root "D:\foraiproject"
```

`question` 和 `plan` profile 不能执行修改；`change` profile 必须具备 `context-pack`、`execution-plan`、`risk-review`，并在需要时获得人工 gate approval。

## 禁止直接编辑

除非用户明确要求进行底层手工修复，否则不要直接编辑以下文件或目录：

- `*.unity`
- `*.prefab`
- `*.asset`
- `*.meta`
- `ProjectSettings/*.asset`
- `Packages/manifest.json`
- `Packages/packages-lock.json`

任何 Unity 感知型变更都必须通过 `Unity Editor Adapter` 或专用的已验证命令执行。

## 修改型任务的标准流程

1. 分析用户意图。
2. 创建或续用 `change` workflow。
3. 构建聚焦的 `context pack`。
4. 检查需求完整性。
5. 生成或更新 `domain spec`。
6. 使用 schema 校验 spec。
7. 生成 `execution plan`。
8. 执行前进行风险审查。
9. 在可用时先执行 dry-run 或 diff preview。
10. 通过 `workflow preflight`。
11. 通过 `CLI` 或 `Unity Editor Adapter` 执行。
12. 运行编译和测试验证。
13. 报告证据与修复建议。

## 风险策略

默认阻止：

- 修改本 workspace 之外的文件。
- 未经批准计划删除 Unity 资产。
- 直接编辑 Unity YAML 或 `.meta` 文件。
- 多个 Unity 实例在线但未指定目标时执行 Unity 代码。
- 将网关返回的 `SecurityCheck` 误判为编译错误。

需要确认：

- 场景变更。
- Prefab 覆盖。
- ProjectSettings 变更。
- Package manifest 变更。
- 批量操作。
- 会影响运行时行为的生成代码。

## 文档地图

- 架构说明：`docs/ai/architecture.md`
- 项目地图：`docs/ai/project-map.md`
- 能力注册表：`docs/ai/capability-registry.md`
- 风险策略：`docs/ai/risk-policy.md`
- 工作流：`docs/ai/workflows.md`
- 机器协议：`tools/ai/schemas`

## 验证要求

- Markdown 和 JSON 文件必须能被正常读取或解析。
- JSON Schema 必须是有效 JSON。
- Unity 变更必须进行 Unity 编译验证。
- 运行时行为变更必须补充相关 EditMode 或 PlayMode 测试。
- 当自动化层可用时，每次修改型执行都应在 `artifacts/ai-runs/<run-id>/` 下产出证据。
