# AI 工作流

本文件定义 AI 辅助变更的标准工作流。

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
