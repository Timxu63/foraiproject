# Unity Roslyn Gateway

## 目录说明
- `gateway_server.py`: 外部常驻网关服务（FastAPI）
- `ai_gateway_client.py`: AIAgent调用脚本，支持 `status` 与 `do-code`
- `models.py`: 网关协议模型
- `state_store.py`: 网关会话与任务状态管理

## 启动网关
```bash
cd Packages/com.forai.roslyn-gateway/Python~
python3 -m pip install -r requirements.txt
python3 gateway_server.py
```

默认监听地址：`http://127.0.0.1:19090`。
当前版本使用单中心网关模型：多个 Unity Editor 会向同一个中心网关注册、心跳、拉取任务。中心网关重启后，Unity Agent 会在旧 Session 被拒绝后自动重新注册。

## AIAgent调用
```bash
python3 Packages/com.forai.roslyn-gateway/Python~/ai_gateway_client.py status
python3 Packages/com.forai.roslyn-gateway/Python~/ai_gateway_client.py list-unities
python3 Packages/com.forai.roslyn-gateway/Python~/ai_gateway_client.py do-code --code "<UTF-8代码字符串>"
python3 Packages/com.forai.roslyn-gateway/Python~/ai_gateway_client.py do-code --project-root "/path/to/UnityProject" --code "<UTF-8代码字符串>"
python3 Packages/com.forai.roslyn-gateway/Python~/check_unity_compile.py
```

目标选择规则：
- `do-code` 未指定目标时，只有 1 个 Unity 在线会自动执行。
- 0 个 Unity 在线或多个 Unity 在线时，网关返回失败，并在 `onlineUnities` 中携带当前在线列表。
- 多 Unity 在线时优先使用 `--project-root` 指定工程根目录；也可以使用 `--unity-id` 指定稳定实例 ID。

包含引号或多行代码时，建议优先使用 `--code-file` 或 `--code-stdin`，避免 shell 转义导致代码内容变化。
当需要让 Unity 主动刷新资源、触发脚本编译并等待最终错误结果时，可结合 `--refresh-assets`、`--request-script-compilation`、`--wait-for-script-compilation`、`--compile-timeout` 参数使用。
如果目标是判断 Unity 工程当前是否存在真实脚本编译错误，优先使用 `check_unity_compile.py --project-root "<UnityProject>"`，不要仅依赖导出的 `dotnet build Unity.sln` 结果。

## Unity Editor 控制窗口
- 菜单路径：`Tools/Unity Roslyn Gateway/Control Window`
- 支持能力：
  - 启动网关（先检测 `fastapi/uvicorn/pydantic`，缺失时自动安装依赖）
  - 停止网关（优先请求网关优雅关闭，再结束本地记录进程）
  - 断开当前 Unity（主动从中心网关注销当前 Editor 的 Agent，不影响中心网关和其他 Unity）
  - 连接当前 Unity（断开后重新启动当前 Editor 的 Agent）
  - 实时查看网关 HTTP 状态、Unity Agent 连接状态、Session、心跳时间
  - Trusted Mode 开关（开启后执行使用 `EnsureLoad`，可调用 `UnityEditor` API）
  - 记住网关开启状态，并在下次启动 Unity Editor 时自动拉起网关与 Unity Agent
- 可配置项：
  - Python 可执行路径（默认 `python3`，可在窗口保存）
  - 默认资源刷新、默认请求编译、默认等待编译、默认编译超时、诊断条数上限
  - Skill 安装按钮：一键复制 `unity-roslyn-gateway` 到 `./.codex/skills/` 或 `./.claude/skills/`

## 环境变量
- `UNITY_ROSLYN_GATEWAY_URL`: Python CLI 默认网关地址
- `UNITY_ROSLYN_GATEWAY_HOST`: 网关监听地址（默认 `127.0.0.1`）
- `UNITY_ROSLYN_GATEWAY_PORT`: 网关监听端口（默认 `19090`）
- `UNITY_ROSLYN_GATEWAY_LOG_LEVEL`: 网关日志级别（默认 `warning`）
- `UNITY_ROSLYN_GATEWAY_ACCESS_LOG`: 是否打印每个HTTP请求访问日志（默认 `0`，关闭）
- `UNITY_ROSLYN_GATEWAY_PYTHON`: Unity Editor 控制窗口默认 Python 可执行路径（未在窗口保存时生效）
