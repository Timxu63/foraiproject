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
