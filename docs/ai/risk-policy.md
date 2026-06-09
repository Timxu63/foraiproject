# AI 风险策略

本策略用于在 AI 辅助操作执行前进行风险分级。

## 风险等级

### Low

示例：

- 读取文件。
- 创建或编辑文档。
- 创建 schema 文件。
- 生成报告。

执行规则：

- 在常规计划批准后可以执行。

### Medium

示例：

- 创建测试。
- 在已批准目录中创建新的源码文件。
- 通过 `Unity Editor Adapter` 在项目自有目录中创建新资产。

执行规则：

- 在计划批准后可以执行。
- 必须进行验证。

### High

示例：

- 场景变更。
- Prefab 覆盖。
- ProjectSettings 变更。
- Package manifest 变更。
- 移动或删除资产。
- 批量重命名。
- 会影响运行时行为的生成代码。

执行规则：

- 必须获得用户对具体计划的明确确认。
- 在可用时必须先执行 dry-run 或 diff preview。
- 执行后必须进行编译和相关测试。

### Blocked

示例：

- 修改 `D:\foraiproject` 之外的文件。
- 直接编辑 `.meta` 文件。
- 直接编辑 `.unity` 或 `.prefab` YAML。
- 多个 Unity 实例在线但未指定目标时执行 Unity 代码。
- 在没有专门安全审查的情况下执行涉及 secrets 或 credentials 的代码。
- 将 gateway `SecurityCheck` 结果当成编译错误。

执行规则：

- 不执行。改为请求更安全的路径，或要求用户明确给出底层修复指令。

## 必须保留的证据

每次修改型运行都应记录：

- Intent analysis。
- Context pack。
- Domain spec。
- Execution plan。
- Risk review。
- 适用时记录 Unity execution result。
- 适用时记录 compile result。
- 适用时记录 test result。
- Final report。

当自动化层可用后，证据应保存在 `artifacts/ai-runs/<run-id>/`。
