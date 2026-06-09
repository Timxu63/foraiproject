using System.Threading.Tasks;
using UnityEditor;
using UnityEngine;

namespace ProjectMagicEscape.Editor.RoslynGateway
{
    internal sealed class UnityGatewayControlWindow : EditorWindow
    {
        private const double StatusRefreshIntervalSec = 1.5;

        private GatewayRuntimeStatus _runtimeStatus;
        private Task<GatewayRuntimeStatus> _statusTask;
        private Task<GatewayProcessOperationResult> _operationTask;

        private string _pythonExecutable;
        private string _skillInstallProjectRoot;
        private int _defaultCompileTimeoutSec;
        private int _maxCompileDiagnostics;
        private double _nextRefreshTime;
        private string _operationMessage = string.Empty;
        private Vector2 _scrollPosition;

        [MenuItem("Tools/Unity Roslyn Gateway/Control Window")]
        public static void OpenWindow()
        {
            UnityGatewayControlWindow window = GetWindow<UnityGatewayControlWindow>("Unity Roslyn Gateway");
            window.minSize = new Vector2(560f, 360f);
            window.Show();
        }

        private void OnEnable()
        {
            if (UnityGatewayProcessController.ProcessState == GatewayProcessState.Running
                || UnityGatewayProcessController.ProcessState == GatewayProcessState.Starting
                || UnityGatewayProcessController.AutoStartEnabled)
            {
                UnityGatewayAgent.Startup();
            }

            _pythonExecutable = UnityGatewayProcessController.PythonExecutable;
            SyncSettingsFromStore();
            _nextRefreshTime = 0;
            EditorApplication.update += OnEditorUpdate;
        }

        private void OnDisable()
        {
            EditorApplication.update -= OnEditorUpdate;
        }

        private void OnEditorUpdate()
        {
            UnityGatewayProcessController.UpdateProcessState();

            if (_statusTask != null && _statusTask.IsCompleted)
            {
                if (_statusTask.Status == TaskStatus.RanToCompletion)
                {
                    _runtimeStatus = _statusTask.Result;
                }
                else
                {
                    _runtimeStatus = new GatewayRuntimeStatus
                    {
                        gatewayReachable = false,
                        error = "状态刷新任务失败",
                    };
                }

                _statusTask = null;
                Repaint();
            }

            if (_operationTask != null && _operationTask.IsCompleted)
            {
                if (_operationTask.Status == TaskStatus.RanToCompletion && _operationTask.Result != null)
                {
                    _operationMessage = _operationTask.Result.message ?? string.Empty;
                }
                else
                {
                    _operationMessage = "操作失败";
                }

                _operationTask = null;
                _nextRefreshTime = 0;
                Repaint();
            }

            if (_statusTask == null && _operationTask == null && EditorApplication.timeSinceStartup >= _nextRefreshTime)
            {
                _statusTask = UnityGatewayProcessController.QueryRuntimeStatusAsync();
                _nextRefreshTime = EditorApplication.timeSinceStartup + StatusRefreshIntervalSec;
            }
        }

        private void OnGUI()
        {
            _scrollPosition = EditorGUILayout.BeginScrollView(_scrollPosition);

            DrawHeader();
            EditorGUILayout.Space(8f);
            DrawRuntimeStatus();
            EditorGUILayout.Space(8f);
            DrawCompilationStatus();
            EditorGUILayout.Space(8f);
            DrawControlButtons();
            EditorGUILayout.Space(8f);
            DrawPathAndConfig();
            EditorGUILayout.Space(8f);
            DrawSkillInstallers();
            EditorGUILayout.Space(8f);
            DrawCompilationConfig();
            EditorGUILayout.Space(8f);
            DrawHintBlock();

            EditorGUILayout.EndScrollView();
        }

        private void DrawHeader()
        {
            EditorGUILayout.LabelField("Unity Roslyn Gateway 控制面板", EditorStyles.boldLabel);
            EditorGUILayout.HelpBox(
                "用于在 Unity Editor 内启动/停止中心网关进程，并查看多个 Unity Agent 的连接状态。",
                MessageType.Info);
        }

        private void DrawRuntimeStatus()
        {
            using (new EditorGUILayout.VerticalScope("box"))
            {
                GatewayProcessState processState = UnityGatewayProcessController.ProcessState;
                EditorGUILayout.LabelField("网关进程状态", processState.ToString());
                EditorGUILayout.LabelField("进程信息", UnityGatewayProcessController.LastMessage);
                EditorGUILayout.LabelField("执行安全模式", UnityGatewayExecutionSettings.SecurityModeLabel);
                EditorGUILayout.LabelField("启动记忆", UnityGatewayProcessController.AutoStartEnabled ? "开启后自动启动" : "保持关闭");

                int pid = UnityGatewayProcessController.OwnedProcessId;
                EditorGUILayout.LabelField("进程 PID", pid > 0 ? pid.ToString() : "-");

                bool gatewayReachable = _runtimeStatus != null && _runtimeStatus.gatewayReachable;
                EditorGUILayout.LabelField("网关 HTTP", gatewayReachable ? "Online" : "Offline");

                string centerState = _runtimeStatus != null ? _runtimeStatus.centerGatewayState : string.Empty;
                string centerDetail = _runtimeStatus != null ? _runtimeStatus.centerGatewayDetail : string.Empty;
                EditorGUILayout.LabelField("中心网关状态", string.IsNullOrWhiteSpace(centerState) ? "-" : centerState);
                EditorGUILayout.LabelField("中心网关详情", string.IsNullOrWhiteSpace(centerDetail) ? "-" : centerDetail);

                string gatewayState = _runtimeStatus != null ? _runtimeStatus.gatewayState : string.Empty;
                string gatewayDetail = _runtimeStatus != null ? _runtimeStatus.gatewayDetail : string.Empty;
                EditorGUILayout.LabelField("默认目标状态", string.IsNullOrWhiteSpace(gatewayState) ? "-" : gatewayState);
                EditorGUILayout.LabelField("默认目标详情", string.IsNullOrWhiteSpace(gatewayDetail) ? "-" : gatewayDetail);

                bool unityConnected = _runtimeStatus != null && _runtimeStatus.unityConnected;
                int onlineCount = _runtimeStatus != null && _runtimeStatus.onlineUnityList != null ? _runtimeStatus.onlineUnityList.Count : 0;
                EditorGUILayout.LabelField("在线 Unity 数量", unityConnected ? onlineCount.ToString() : "0");
                EditorGUILayout.LabelField("当前 Unity ID", string.IsNullOrWhiteSpace(UnityGatewayAgent.CurrentUnityId) ? "-" : UnityGatewayAgent.CurrentUnityId);
                EditorGUILayout.LabelField("默认 Unity Session", _runtimeStatus != null && !string.IsNullOrWhiteSpace(_runtimeStatus.unitySessionId) ? _runtimeStatus.unitySessionId : "-");
                EditorGUILayout.LabelField("最近心跳(UTC)", _runtimeStatus != null && !string.IsNullOrWhiteSpace(_runtimeStatus.lastHeartbeatUtc) ? _runtimeStatus.lastHeartbeatUtc : "-");

                if (_runtimeStatus != null && _runtimeStatus.onlineUnityList != null && _runtimeStatus.onlineUnityList.Count > 0)
                {
                    EditorGUILayout.Space(4f);
                    EditorGUILayout.LabelField("在线 Unity 列表", EditorStyles.boldLabel);
                    for (int i = 0; i < _runtimeStatus.onlineUnityList.Count; i++)
                    {
                        GatewayUnityRuntimeInfo unity = _runtimeStatus.onlineUnityList[i];
                        if (unity == null)
                        {
                            continue;
                        }

                        string title = string.IsNullOrWhiteSpace(unity.projectRoot) ? unity.unityId : unity.projectRoot;
                        EditorGUILayout.LabelField($"{i + 1}. {title}");
                        EditorGUI.indentLevel++;
                        EditorGUILayout.LabelField("Unity ID", string.IsNullOrWhiteSpace(unity.unityId) ? "-" : unity.unityId);
                        EditorGUILayout.LabelField("状态", string.IsNullOrWhiteSpace(unity.state) ? "-" : unity.state);
                        EditorGUILayout.LabelField("详情", string.IsNullOrWhiteSpace(unity.detail) ? "-" : unity.detail);
                        EditorGUILayout.LabelField("进程", unity.unityProcessId > 0 ? unity.unityProcessId.ToString() : "-");
                        EditorGUILayout.LabelField("版本", string.IsNullOrWhiteSpace(unity.editorVersion) ? "-" : unity.editorVersion);
                        EditorGUI.indentLevel--;
                    }
                }

                if (_runtimeStatus != null && !string.IsNullOrWhiteSpace(_runtimeStatus.error))
                {
                    EditorGUILayout.HelpBox(_runtimeStatus.error, MessageType.Warning);
                }

                if (!string.IsNullOrWhiteSpace(_operationMessage))
                {
                    EditorGUILayout.HelpBox(_operationMessage, MessageType.None);
                }
            }
        }

        private void DrawCompilationStatus()
        {
            using (new EditorGUILayout.VerticalScope("box"))
            {
                EditorGUILayout.LabelField("编译任务状态", EditorStyles.boldLabel);
                EditorGUILayout.LabelField("活跃任务", UnityGatewayAgent.HasActiveTask ? "Yes" : "No");

                if (!UnityGatewayAgent.HasActiveTask)
                {
                    EditorGUILayout.LabelField("任务详情", "-");
                    return;
                }

                EditorGUILayout.LabelField("请求 ID", string.IsNullOrWhiteSpace(UnityGatewayAgent.ActiveTaskRequestId) ? "-" : UnityGatewayAgent.ActiveTaskRequestId);
                EditorGUILayout.LabelField("任务阶段", string.IsNullOrWhiteSpace(UnityGatewayAgent.ActiveTaskStage) ? "-" : UnityGatewayAgent.ActiveTaskStage);
                EditorGUILayout.LabelField("任务详情", string.IsNullOrWhiteSpace(UnityGatewayAgent.ActiveTaskDetail) ? "-" : UnityGatewayAgent.ActiveTaskDetail);
                EditorGUILayout.LabelField("开始时间(UTC)", string.IsNullOrWhiteSpace(UnityGatewayAgent.ActiveTaskWaitingStartedAtUtc) ? "-" : UnityGatewayAgent.ActiveTaskWaitingStartedAtUtc);
                EditorGUILayout.LabelField("截止时间(UTC)", string.IsNullOrWhiteSpace(UnityGatewayAgent.ActiveTaskDeadlineUtc) ? "-" : UnityGatewayAgent.ActiveTaskDeadlineUtc);

                GatewayCompilationSnapshot snapshot = UnityGatewayAgent.CurrentCompilationSnapshot;
                EditorGUILayout.LabelField("编译 Session", snapshot != null && !string.IsNullOrWhiteSpace(snapshot.sessionId) ? snapshot.sessionId : "-");
                EditorGUILayout.LabelField("是否已开始", snapshot != null && snapshot.started ? "Yes" : "No");
                EditorGUILayout.LabelField("是否已完成", snapshot != null && snapshot.completed ? "Yes" : "No");
                EditorGUILayout.LabelField("是否有错误", snapshot != null && snapshot.hadErrors ? "Yes" : "No");
                EditorGUILayout.LabelField("编译详情", snapshot != null && !string.IsNullOrWhiteSpace(snapshot.detail) ? snapshot.detail : "-");
                EditorGUILayout.LabelField("耗时(ms)", snapshot != null && snapshot.elapsedMs > 0 ? snapshot.elapsedMs.ToString() : "-");
            }
        }

        private void DrawControlButtons()
        {
            bool busy = _operationTask != null;
            GatewayProcessState processState = UnityGatewayProcessController.ProcessState;

            using (new EditorGUILayout.HorizontalScope())
            {
                GUI.enabled = !busy && processState != GatewayProcessState.Running && processState != GatewayProcessState.Starting;
                if (GUILayout.Button("启动网关", GUILayout.Height(28f)))
                {
                    StartGateway();
                }

                GUI.enabled = !busy && (processState == GatewayProcessState.Running || processState == GatewayProcessState.Error || processState == GatewayProcessState.NotRunning);
                if (GUILayout.Button("停止中心网关", GUILayout.Height(28f)))
                {
                    StopGateway();
                }

                GUI.enabled = !busy && UnityGatewayAgent.IsStarted;
                if (GUILayout.Button("断开当前 Unity", GUILayout.Height(28f)))
                {
                    DisconnectCurrentUnity();
                }

                GUI.enabled = !busy && !UnityGatewayAgent.IsStarted;
                if (GUILayout.Button("连接当前 Unity", GUILayout.Height(28f)))
                {
                    ConnectCurrentUnity();
                }

                GUI.enabled = !busy;
                if (GUILayout.Button("立即刷新状态", GUILayout.Height(28f)))
                {
                    ForceRefreshStatus();
                }

                GUI.enabled = true;
            }
        }

        private void DrawPathAndConfig()
        {
            using (new EditorGUILayout.VerticalScope("box"))
            {
                EditorGUILayout.LabelField("配置", EditorStyles.boldLabel);
                EditorGUILayout.LabelField("网关 URL", UnityGatewayProcessController.GatewayBaseUrl);
                EditorGUILayout.LabelField("Unity工程根目录", UnityGatewayPaths.UnityProjectRoot);
                EditorGUILayout.LabelField("Unity ID 文件", UnityGatewayPaths.UnityIdFilePath);
                EditorGUILayout.LabelField("仓库根目录", UnityGatewayPaths.RepositoryRoot);
                EditorGUILayout.LabelField("网关目录", UnityGatewayProcessController.GatewayToolDirectory);
                EditorGUILayout.LabelField("CLI 相对路径", UnityGatewayPaths.GatewayCliProjectRelativePath);

                bool trustedModeEnabled = UnityGatewayExecutionSettings.TrustedModeEnabled;
                bool newTrustedModeEnabled = EditorGUILayout.ToggleLeft(
                    "Trusted Mode（允许执行 UnityEditor 命名空间，跳过 Roslyn 安全校验）",
                    trustedModeEnabled);

                if (newTrustedModeEnabled != trustedModeEnabled)
                {
                    UnityGatewayExecutionSettings.TrustedModeEnabled = newTrustedModeEnabled;
                    _operationMessage = $"已切换执行安全模式: {UnityGatewayExecutionSettings.SecurityModeLabel}";
                }

                string newPython = EditorGUILayout.TextField("Python 可执行路径", _pythonExecutable ?? string.Empty);
                if (newPython != _pythonExecutable)
                {
                    _pythonExecutable = newPython;
                }

                using (new EditorGUILayout.HorizontalScope())
                {
                    if (GUILayout.Button("保存 Python 路径", GUILayout.Height(24f)))
                    {
                        UnityGatewayProcessController.PythonExecutable = _pythonExecutable;
                        _pythonExecutable = UnityGatewayProcessController.PythonExecutable;
                        _operationMessage = $"已保存 Python 路径: {_pythonExecutable}";
                    }

                    string defaultPython = UnityGatewayProcessController.DefaultPythonExecutable;
                    if (GUILayout.Button($"恢复默认({defaultPython})", GUILayout.Height(24f)))
                    {
                        UnityGatewayProcessController.PythonExecutable = defaultPython;
                        _pythonExecutable = UnityGatewayProcessController.PythonExecutable;
                        _operationMessage = $"已恢复默认 Python 路径: {_pythonExecutable}";
                    }
                }

                bool newAutoStartEnabled = EditorGUILayout.ToggleLeft("记住网关开启状态并在下次启动 Unity 时自动开启", UnityGatewayProcessController.AutoStartEnabled);
                if (newAutoStartEnabled != UnityGatewayProcessController.AutoStartEnabled)
                {
                    UnityGatewayProcessController.AutoStartEnabled = newAutoStartEnabled;
                    _operationMessage = newAutoStartEnabled
                        ? "已启用网关自动启动"
                        : "已关闭网关自动启动";
                }
            }
        }

        private void DrawSkillInstallers()
        {
            using (new EditorGUILayout.VerticalScope("box"))
            {
                EditorGUILayout.LabelField("Skill 安装", EditorStyles.boldLabel);
                string newSkillInstallProjectRoot = EditorGUILayout.TextField("项目根目录", _skillInstallProjectRoot ?? string.Empty);
                if (newSkillInstallProjectRoot != _skillInstallProjectRoot)
                {
                    _skillInstallProjectRoot = newSkillInstallProjectRoot;
                }

                using (new EditorGUILayout.HorizontalScope())
                {
                    if (GUILayout.Button("保存项目根目录", GUILayout.Height(24f)))
                    {
                        SaveSkillInstallProjectRoot(_skillInstallProjectRoot);
                    }

                    if (GUILayout.Button("恢复当前Unity根目录", GUILayout.Height(24f)))
                    {
                        SaveSkillInstallProjectRoot(UnityGatewayPaths.UnityProjectRoot);
                    }
                }

                if (!System.IO.Directory.Exists(UnityGatewayPaths.SkillInstallProjectRoot))
                {
                    EditorGUILayout.HelpBox($"当前项目根目录不存在: {UnityGatewayPaths.SkillInstallProjectRoot}", MessageType.Warning);
                }

                EditorGUILayout.LabelField("Skill 源目录", UnityGatewayPaths.SkillSourceDirectory);
                EditorGUILayout.LabelField("当前项目根目录", UnityGatewayPaths.SkillInstallProjectRoot);
                EditorGUILayout.LabelField("Codex 目标", UnityGatewayPaths.CodexSkillInstallDirectory);
                EditorGUILayout.LabelField("Claude Code 目标", UnityGatewayPaths.ClaudeSkillInstallDirectory);

                using (new EditorGUILayout.HorizontalScope())
                {
                    if (GUILayout.Button("安装 Skill 到 Codex", GUILayout.Height(24f)))
                    {
                        InstallSkillWithDialog(UnityGatewaySkillInstaller.InstallSkillToCodex(), "Codex");
                    }

                    if (GUILayout.Button("安装 Skill 到 ClaudeCode", GUILayout.Height(24f)))
                    {
                        InstallSkillWithDialog(UnityGatewaySkillInstaller.InstallSkillToClaudeCode(), "Claude Code");
                    }
                }
            }
        }

        private void DrawCompilationConfig()
        {
            using (new EditorGUILayout.VerticalScope("box"))
            {
                EditorGUILayout.LabelField("编译检查默认配置", EditorStyles.boldLabel);

                bool newDefaultRefreshAssets = EditorGUILayout.ToggleLeft("默认刷新资源数据库", UnityGatewayExecutionSettings.DefaultRefreshAssets);
                bool newDefaultRequestCompilation = EditorGUILayout.ToggleLeft("默认请求脚本编译", UnityGatewayExecutionSettings.DefaultRequestCompilation);
                bool newDefaultWaitForCompilation = EditorGUILayout.ToggleLeft("默认等待编译结果", UnityGatewayExecutionSettings.DefaultWaitForCompilation);
                int newDefaultCompileTimeoutSec = EditorGUILayout.IntField("默认编译超时(秒)", _defaultCompileTimeoutSec);
                int newMaxCompileDiagnostics = EditorGUILayout.IntField("诊断条数上限", _maxCompileDiagnostics);

                if (newDefaultRefreshAssets != UnityGatewayExecutionSettings.DefaultRefreshAssets)
                {
                    UnityGatewayExecutionSettings.DefaultRefreshAssets = newDefaultRefreshAssets;
                }

                if (newDefaultRequestCompilation != UnityGatewayExecutionSettings.DefaultRequestCompilation)
                {
                    UnityGatewayExecutionSettings.DefaultRequestCompilation = newDefaultRequestCompilation;
                }

                if (newDefaultWaitForCompilation != UnityGatewayExecutionSettings.DefaultWaitForCompilation)
                {
                    UnityGatewayExecutionSettings.DefaultWaitForCompilation = newDefaultWaitForCompilation;
                }

                if (newDefaultCompileTimeoutSec != _defaultCompileTimeoutSec)
                {
                    _defaultCompileTimeoutSec = Mathf.Clamp(newDefaultCompileTimeoutSec, 10, 600);
                    UnityGatewayExecutionSettings.DefaultCompileTimeoutSec = _defaultCompileTimeoutSec;
                }

                if (newMaxCompileDiagnostics != _maxCompileDiagnostics)
                {
                    _maxCompileDiagnostics = Mathf.Clamp(newMaxCompileDiagnostics, 1, 1000);
                    UnityGatewayExecutionSettings.MaxCompileDiagnostics = _maxCompileDiagnostics;
                }

                EditorGUILayout.HelpBox(
                    "当 Agent 未显式传入编译超时时，会使用这里的默认值。编译期间网关短暂失联属于正常现象，任务会在 Unity 恢复后继续收敛结果。",
                    MessageType.None);
            }
        }

        private static void DrawHintBlock()
        {
            EditorGUILayout.HelpBox(
                "启动网关时会先检测 fastapi/uvicorn/pydantic，缺失则自动执行 pip 安装。\n" +
                "停止中心网关不会断开当前 Unity Agent；Agent 会等待中心网关恢复后重新注册。\n" +
                "断开当前 Unity 会主动从中心网关注销本 Editor 的 Agent，不影响中心网关和其他 Unity。\n" +
                "编译检查会主动刷新资源并请求 Unity 脚本编译，不依赖切回 Editor 获得焦点。",
                MessageType.None);
        }

        private void StartGateway()
        {
            if (_operationTask != null)
            {
                return;
            }

            UnityGatewayAgent.Startup();
            _operationMessage = "正在启动网关...";
            _operationTask = UnityGatewayProcessController.StartGatewayAsync();
            Repaint();
        }

        private void StopGateway()
        {
            if (_operationTask != null)
            {
                return;
            }

            _operationMessage = "正在停止网关...";
            _operationTask = UnityGatewayProcessController.StopGatewayAsync();
            Repaint();
        }

        private void DisconnectCurrentUnity()
        {
            if (_operationTask != null)
            {
                return;
            }

            GatewayProcessOperationResult result = UnityGatewayProcessController.DisconnectCurrentUnityAgent();
            _operationMessage = result != null ? result.message ?? string.Empty : string.Empty;
            _nextRefreshTime = 0;
            Repaint();
        }

        private void ConnectCurrentUnity()
        {
            if (_operationTask != null)
            {
                return;
            }

            GatewayProcessOperationResult result = UnityGatewayProcessController.ConnectCurrentUnityAgent();
            _operationMessage = result != null ? result.message ?? string.Empty : string.Empty;
            _nextRefreshTime = 0;
            Repaint();
        }

        private void ForceRefreshStatus()
        {
            if (_statusTask != null)
            {
                return;
            }

            _statusTask = UnityGatewayProcessController.QueryRuntimeStatusAsync();
            _nextRefreshTime = EditorApplication.timeSinceStartup + StatusRefreshIntervalSec;
            Repaint();
        }

        private void SyncSettingsFromStore()
        {
            _skillInstallProjectRoot = UnityGatewayExecutionSettings.SkillInstallProjectRoot;
            _defaultCompileTimeoutSec = UnityGatewayExecutionSettings.DefaultCompileTimeoutSec;
            _maxCompileDiagnostics = UnityGatewayExecutionSettings.MaxCompileDiagnostics;
        }

        /// <summary>
        /// 保存 Skill 安装项目根目录，并立即刷新派生目标路径。
        /// </summary>
        private void SaveSkillInstallProjectRoot(string projectRoot)
        {
            try
            {
                string normalizedRoot = string.IsNullOrWhiteSpace(projectRoot)
                    ? UnityGatewayPaths.UnityProjectRoot
                    : System.IO.Path.GetFullPath(projectRoot.Trim());
                UnityGatewayExecutionSettings.SkillInstallProjectRoot = normalizedRoot;
                _skillInstallProjectRoot = UnityGatewayExecutionSettings.SkillInstallProjectRoot;
                _operationMessage = $"已保存 Skill 项目根目录: {_skillInstallProjectRoot}";
            }
            catch (System.Exception ex)
            {
                _operationMessage = $"保存 Skill 项目根目录失败: {ex.GetType().Name}: {ex.Message}";
            }

            Repaint();
        }

        /// <summary>
        /// 执行 Skill 安装后同步更新界面提示，并弹窗明确告知结果。
        /// </summary>
        private void InstallSkillWithDialog(GatewayProcessOperationResult result, string platformName)
        {
            _operationMessage = result != null ? result.message ?? string.Empty : string.Empty;

            string title = result != null && result.success
                ? $"{platformName} 安装成功"
                : $"{platformName} 安装失败";
            string message = string.IsNullOrWhiteSpace(_operationMessage)
                ? $"安装 {platformName} 完成，但未返回详细信息。"
                : _operationMessage;

            EditorUtility.DisplayDialog(title, message, "确定");
            Repaint();
        }
    }
}
