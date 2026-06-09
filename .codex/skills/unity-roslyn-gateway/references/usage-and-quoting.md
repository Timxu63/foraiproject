# 使用与引号指南

## 失败后状态诊断
默认先执行 `do-code`，仅在调用失败后再查询状态。

```bash
python3 Packages/com.forai.roslyn-gateway/Python~/ai_gateway_client.py status
python3 Packages/com.forai.roslyn-gateway/Python~/ai_gateway_client.py list-unities
```

快速解读：
- `Ready`：可立即重试。
- `Busy`：等待后重试。
- `Offline`：先恢复网关进程或 Unity agent 连接。
- 多个 Unity 在线时，`do-code` 未指定目标会返回 `ClientError` 并携带 `onlineUnities`，需要使用 `--project-root` 或 `--unity-id` 重试。

## 标准 DoCode 模式
C# 代码整体用外层单引号包裹。

```bash
python3 Packages/com.forai.roslyn-gateway/Python~/ai_gateway_client.py do-code --code 'Debug.Log("Hello---");' --timeout 30
python3 Packages/com.forai.roslyn-gateway/Python~/ai_gateway_client.py do-code --project-root "/path/to/UnityProject" --code 'Debug.Log("Hello---");' --timeout 30
```

## 查询信息时优先返回值
当目标是读取信息而不是修改对象时，优先使用 `return` 返回值。
```bash
python3 Packages/com.forai.roslyn-gateway/Python~/ai_gateway_client.py do-code --project-root "/path/to/UnityProject" --code 'Debug.Log("Test");return UnityEngine.SceneManagement.SceneManager.GetActiveScene().name;' --timeout 30
```
这样返回值会进入 `result` 字段，便于自动化链路直接消费。

## 编译触发模式
显式触发编译时需要更长超时。

```bash
python3 Packages/com.forai.roslyn-gateway/Python~/ai_gateway_client.py do-code --project-root "/path/to/UnityProject" --code 'UnityEditor.Compilation.CompilationPipeline.RequestScriptCompilation();' --timeout 120
```

## 超时建议
- `30`：快速编辑器读写。
- `60`：中等变更与批处理。
- `120`：触发编译或较重编辑器任务。
- `180-300`：大型流程或编译/重载耗时不确定。

## 结果状态处理
- `Success`：继续流程。
- `CompileError`：修复语法或诊断错误。
- `SecurityCheck`：切换到 trusted mode 或避免被拦截 API。
- `RuntimeError`：检查堆栈并补充空值/路径保护。
- `Timeout`：增加超时或拆分操作。
- `BusyRejected`：轮询状态后重试。
- `Offline`：重启网关并确认 Unity agent 重新连接。

## 常见文本格式失败原因
1. 外层双引号且内部 C# 双引号未转义。
2. shell 换行导致分号丢失。
3. 混入 shell 插值字符破坏 C# 文本。
4. 多行代码直接塞进 `--code`，未使用 `--code-file` 或 `--code-stdin`。

## 复杂代码的稳定替代方式
当字符串转义变脆弱时，使用以下方式之一。

1. 文件模式
```bash
python3 Packages/com.forai.roslyn-gateway/Python~/ai_gateway_client.py do-code --project-root "/path/to/UnityProject" --code-file /absolute/or/relative/path.cs.txt --timeout 120
```

2. STDIN 模式
```bash
cat <<'CS' | python3 Packages/com.forai.roslyn-gateway/Python~/ai_gateway_client.py do-code --project-root "/path/to/UnityProject" --code-stdin --timeout 120
Debug.Log("hello");
CS
```

## 重试循环建议
1. 执行一次 `do-code`。
2. 若结果为 `Success`，直接继续后续流程。
3. 若结果为 `ClientError` 且包含多个 `onlineUnities`，选择目标后添加 `--project-root` 重试。
4. 若结果为 `BusyRejected`、`Timeout` 或 `Offline`，再查询 `status` 并按状态决定重试。
5. 达到最大重试次数后停止，并回报最新网关响应。
