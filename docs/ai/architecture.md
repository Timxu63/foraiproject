# AI 工程架构

本项目使用分层架构来支持 AI 辅助 Unity 开发。

## 分层

1. User Intent
2. Intent Analysis
3. Context Scan
4. Requirement Check
5. Domain Spec
6. Spec Validation
7. Execution Plan
8. Risk Review
9. CLI Execution
10. Unity Editor Adapter Execution
11. Compile, Test, and Validation
12. Report and Repair

这些英文阶段名是稳定协议名，文档说明可以使用中文，但自动化输出应继续使用这些名称或对应 schema 字段。

## 职责边界

### Workflow Engine

`Workflow Engine` 负责任务阶段调度、运行状态记录、重试策略和结构化消息路由。它不能调用 Unity API，也不能直接编辑 Unity 资产。

### Agent

`Agent` 读取上下文并产出结构化结果。它可以提出 spec、plan、risk review 或 repair 建议，但不能直接修改 Unity 资产或编辑器状态。

### CLI

`CLI` 是人、Agent、CI 和未来 MCP 工具的稳定入口。命令应输出机器可读 JSON，并在 Unity 操作中支持明确的项目目标参数。

### Unity Editor Adapter

`Unity Editor Adapter` 是 Unity 感知型修改的唯一可信执行层。它负责调用 `AssetDatabase`、`PrefabUtility`、场景 API、编译 API 和编辑器状态 API。

## 允许的依赖方向

```text
Agent -> Schema
Agent -> Context Pack
Workflow Engine -> CLI
CLI -> Unity Gateway Client
Unity Gateway Client -> Unity Editor Adapter
Unity Editor Adapter -> UnityEditor APIs
```

禁止的依赖方向：

```text
Agent -> UnityEditor APIs
Agent -> direct .unity/.prefab/.asset/.meta edits
Workflow Engine -> UnityEditor APIs
CLI -> direct Unity YAML mutation
```

## 设计规则

只要某个变更依赖 Unity 导入状态、GUID、Prefab、场景、AssetDatabase 或编译状态，它就属于 `Unity Editor Adapter` 的职责范围。
