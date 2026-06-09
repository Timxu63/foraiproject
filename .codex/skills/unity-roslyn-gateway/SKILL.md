---
name: unity-roslyn-gateway
description: 通过 ProjectMagicEscape 单中心网关（`Packages/com.forai.roslyn-gateway/Python~/ai_gateway_client.py`）执行 Unity Editor C# 代码。凡是需要在 Unity 内进行实际操作（例如创建/修改 Prefab、创建/修改/删除 GameObject、管理目录与资源、读取仅编辑器可见状态、触发编译）时，都应优先使用本 Skill，而不是仅靠离线文本编辑。支持多个 Unity 同时在线；多 Unity 在线时必须用 `--project-root` 或 `--unity-id` 指定目标。查询信息类任务优先使用 `return` 返回值，不仅依赖 `Debug.Log`。
---

# Unity Roslyn 网关

## 概述
使用本技能可通过 `python3 Packages/com.forai.roslyn-gateway/Python~/ai_gateway_client.py` 发送 C# 代码字符串来控制 Unity Editor。
当前网关是单中心、多 Unity Agent 模型：多个 Unity Editor 会注册到同一个 `127.0.0.1:19090` 中心网关。
Unity 控制面板中的“断开当前 Unity”会主动注销当前 Editor 的 Agent；需要恢复时点击“连接当前 Unity”。
优先保证命令格式确定、超时策略可预期、状态重试逻辑清晰。

## 高价值场景
当仅靠直接改文件不够、必须依赖 Unity 运行时或编辑器上下文时，使用本技能。
另外，任何“需要在 Unity 中落地操作”的请求（如创建 Prefab）也应直接使用本技能执行。
1. 在已打开场景中创建、重命名、移动或删除 `GameObject`。
2. 通过 `UnityEditor.AssetDatabase` 和 `UnityEditor.PrefabUtility` 创建目录、移动资源、保存 Prefab。
3. 读取仅编辑器可见且难以从仓库文本直接推断的状态，例如激活场景根节点、选择状态、依赖数量、保存状态。
4. 主动触发脚本编译，并等待 Unity 回到稳定状态。

## 核心流程
1. 如可能存在多个 Unity 在线，先列出目标。
```bash
python3 Packages/com.forai.roslyn-gateway/Python~/ai_gateway_client.py list-unities
```
2. 直接使用 `do-code` 执行 C#。
- `--code` 的整段字符串使用单引号包裹。
- C# 字符串字面量使用正常双引号。
- 轻量操作默认从 `--timeout 30` 开始。
- 多 Unity 在线时添加 `--project-root "<UnityProject绝对路径>"`，这是推荐目标标识。
```bash
python3 Packages/com.forai.roslyn-gateway/Python~/ai_gateway_client.py do-code --code 'Debug.Log("Hello---");' --timeout 30
python3 Packages/com.forai.roslyn-gateway/Python~/ai_gateway_client.py do-code --project-root "/path/to/UnityProject" --code 'return UnityEngine.Application.dataPath;' --timeout 30
```
3. 解析结果 JSON，并按 `state` 分支处理。
- `Success`：消费 `result`。
- `CompileError`：检查 `compile.diagnostics`。
- `SecurityCheck`：代码已编译，但被 Roslyn 安全模式拦截。
- `RuntimeError`：检查 `error.stackTrace`。
- `Timeout`：增大超时或拆分任务。
- `BusyRejected`：查询 `status`，等待状态恢复后重试。
- `Offline`：查询 `status` 确认离线，先恢复网关或 Unity 连接。
- `ClientError` 且包含 `onlineUnities`：通常是 0 个或多个 Unity 在线但未指定目标，需要选择 `projectRoot` 或 `unityId` 后重试。
4. 仅在失败后执行状态诊断。
```bash
python3 Packages/com.forai.roslyn-gateway/Python~/ai_gateway_client.py status
python3 Packages/com.forai.roslyn-gateway/Python~/ai_gateway_client.py status --project-root "/path/to/UnityProject"
```

## 信息查询返回值规则
当任务目标是“获取 Unity 某些信息”（例如场景名、选择对象数量、依赖数量、配置值）时，优先通过 `return` 返回结果，便于 AIAgent 直接从 JSON 读取。
```bash
python3 Packages/com.forai.roslyn-gateway/Python~/ai_gateway_client.py do-code --project-root "/path/to/UnityProject" --code 'Debug.Log("Test");return UnityEngine.SceneManagement.SceneManager.GetActiveScene().name;' --timeout 30
```
只用 `Debug.Log` 会让结果分散在 Console，不利于自动化消费。

## 默认 Using 命名空间配置
DoCode 执行时会自动包含以下命名空间，无需在代码中显式声明 `using`：
- `using System;`
- `using System.Linq;`
- `using UnityEngine;`
- `using UnityEditor;`

如果执行 DoCode 时因为缺少命名空间导致编译失败（例如 `CS0246: The type or namespace name could not be found`），可以直接修改 `Packages/com.forai.roslyn-gateway/RoslynDoCodeExecutor.cs` 文件的 354-359 行，添加所需的 using 语句。

示例：如果需要使用 `UnityEngine.UI` 命名空间，在 358 行后添加：
```csharp
finalUsings.Add("using UnityEngine.UI;");
```

## 引号与文本规则
遵循以下规则，避免 shell 文本格式导致调用失败。

### 标准终端调用
1. `--code` 外层使用单引号。
2. C# 字符串字面量使用双引号。
3. 除非每个内部双引号都已转义，否则不要使用外层双引号。
4. 多行代码或转义复杂时优先使用 `--code-file` 或 `--code-stdin`。

### Claude Code Bash 工具调用（重要）
**在 Claude Code 的 Bash 工具中调用时，引号处理规则不同：**
- **推荐方案**：使用双引号外层，转义内部双引号
  ```bash
  python3 Packages/com.forai.roslyn-gateway/Python~/ai_gateway_client.py do-code --code "var obj = UnityEditor.Selection.activeGameObject; return obj != null ? obj.name : \"None\";" --timeout 30
  ```
- **避免使用**：单引号外层（Bash 工具对单引号的处理与标准 shell 不同，会导致特殊字符如 `!` 被错误处理，产生 CS1056 等编译错误）
- **备选方案**：使用 `--code-file` 参数传递复杂代码，完全避免引号问题

当请求包含字符串、多行片段或 shell 敏感字符时，阅读 `references/usage-and-quoting.md`。

## 超时策略
根据操作成本使用分层超时。
1. `30s`：简单日志、对象查询、元数据读取、轻量编辑。
2. `60-120s`：目录或 Prefab 批处理、中等规模资源查询。
3. `120-300s`：显式触发编译或可能导致域重载的操作。

触发编译后，需要轮询状态直到 Unity 稳定。

## 编译触发指引
当需要显式触发脚本编译时，使用以下命令。
```bash
python3 Packages/com.forai.roslyn-gateway/Python~/ai_gateway_client.py do-code --project-root "/path/to/UnityProject" --code 'UnityEditor.Compilation.CompilationPipeline.RequestScriptCompilation();' --timeout 120
```
提交后通常需要更长执行窗口，并可能短暂进入 `Busy` 状态。

## 安全模式指引
在调用 `UnityEditor.*` API 前，先检查 Unity Gateway Control Window 的安全模式。
1. 受限模式（`UseSettings`）下，编辑器命名空间可能返回 `SecurityCheck`。
2. 可信模式（`EnsureLoad`）下，允许调用编辑器 API，但安全隔离更少。
3. 出现 `SecurityCheck` 时要明确报告，不要误判为语法编译错误。

## 任务选择
在执行具体 Unity 操作时，阅读 `references/unity-code-recipes.md`。
优先选取最接近请求目标的配方，再保守地调整名称与路径。

## 操作纪律
1. 每次 `do-code` 只聚焦一个意图。
2. 每个变更步骤都先确认成功，再继续后续编辑。
3. 对破坏性操作，在代码中加入明确存在性检查。
4. 多 Unity 在线时必须明确目标工程路径，避免把操作发送到错误的 Editor。
5. 尽可能使用幂等逻辑，降低重复执行造成的副作用。
