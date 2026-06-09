using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Net.Http;
using System.Text;
using System.Threading.Tasks;
using Newtonsoft.Json;
using UnityEditor;
using UnityEngine;

namespace ProjectMagicEscape.Editor.RoslynGateway
{
    internal enum GatewayProcessState
    {
        Unknown = 0,
        NotRunning = 1,
        Running = 2,
        Starting = 3,
        Stopping = 4,
        Error = 5,
    }

    internal sealed class GatewayProcessOperationResult
    {
        public bool success;
        public string message;
    }

    internal sealed class GatewayRuntimeStatus
    {
        /// <summary>
        /// 中心网关 HTTP 服务是否可访问。
        /// </summary>
        public bool gatewayReachable;

        /// <summary>
        /// 兼容旧版 /v1/status 的 Unity 执行状态。
        /// </summary>
        public string gatewayState;

        /// <summary>
        /// 兼容旧版 /v1/status 的 Unity 执行详情。
        /// </summary>
        public string gatewayDetail;

        /// <summary>
        /// 是否存在至少一个在线 Unity。
        /// </summary>
        public bool unityConnected;

        /// <summary>
        /// 兼容旧版单 Unity 网关的 Session ID。
        /// </summary>
        public string unitySessionId;

        /// <summary>
        /// 兼容旧版单 Unity 网关的最近心跳时间。
        /// </summary>
        public string lastHeartbeatUtc;

        /// <summary>
        /// 中心网关自身状态。
        /// </summary>
        public string centerGatewayState;

        /// <summary>
        /// 中心网关自身状态详情。
        /// </summary>
        public string centerGatewayDetail;

        /// <summary>
        /// 当前中心网关中在线的 Unity 列表。
        /// </summary>
        public List<GatewayUnityRuntimeInfo> onlineUnityList = new List<GatewayUnityRuntimeInfo>();

        /// <summary>
        /// 状态查询失败时的错误信息。
        /// </summary>
        public string error;
    }

    internal sealed class GatewayUnityRuntimeInfo
    {
        /// <summary>
        /// Unity 实例稳定身份 ID。
        /// </summary>
        public string unityId;

        /// <summary>
        /// Unity Agent 当前 Session ID。
        /// </summary>
        public string sessionId;

        /// <summary>
        /// Unity Agent 名称。
        /// </summary>
        public string agentName;

        /// <summary>
        /// Unity 工程根目录。
        /// </summary>
        public string projectRoot;

        /// <summary>
        /// Unity 工程 Assets 目录。
        /// </summary>
        public string dataPath;

        /// <summary>
        /// Unity Editor 进程 ID。
        /// </summary>
        public int unityProcessId;

        /// <summary>
        /// Unity Editor 版本号。
        /// </summary>
        public string editorVersion;

        /// <summary>
        /// Unity Agent 当前状态。
        /// </summary>
        public string state;

        /// <summary>
        /// Unity Agent 当前状态详情。
        /// </summary>
        public string detail;

        /// <summary>
        /// Unity Agent 最近心跳时间。
        /// </summary>
        public string lastHeartbeatUtc;
    }

    internal sealed class GatewayStatusResponse
    {
        /// <summary>
        /// 兼容旧版 /v1/status 的状态字段。
        /// </summary>
        public string state;

        /// <summary>
        /// 兼容旧版 /v1/status 的详情字段。
        /// </summary>
        public string detail;

        /// <summary>
        /// 中心网关自身状态字段。
        /// </summary>
        public string gatewayState;

        /// <summary>
        /// 中心网关自身详情字段。
        /// </summary>
        public string gatewayDetail;

        /// <summary>
        /// 中心网关自身状态字段的备用名称。
        /// </summary>
        public string centerGatewayState;

        /// <summary>
        /// 中心网关自身详情字段的备用名称。
        /// </summary>
        public string centerGatewayDetail;

        /// <summary>
        /// 中心网关自身状态对象。
        /// </summary>
        public GatewayCenterStatusResponse gateway;

        /// <summary>
        /// 兼容旧版单 Unity 网关的 Session ID。
        /// </summary>
        public string unitySessionId;

        /// <summary>
        /// 兼容旧版单 Unity 网关的最近心跳时间。
        /// </summary>
        public string lastHeartbeatUtc;

        /// <summary>
        /// 兼容新版状态根节点直接返回的 Unity ID。
        /// </summary>
        public string unityId;

        /// <summary>
        /// 新版中心网关返回的当前选中 Unity 目标。
        /// </summary>
        public GatewayUnityStatusResponse unityTarget;

        /// <summary>
        /// 兼容新版状态根节点直接返回的工程根目录。
        /// </summary>
        public string projectRoot;

        /// <summary>
        /// 兼容新版状态根节点直接返回的 Assets 目录。
        /// </summary>
        public string dataPath;

        /// <summary>
        /// 兼容新版状态根节点直接返回的 Unity 进程 ID。
        /// </summary>
        public int unityProcessId;

        /// <summary>
        /// 兼容新版状态根节点直接返回的 Unity 版本号。
        /// </summary>
        public string editorVersion;

        /// <summary>
        /// 新版中心网关返回的在线 Unity 列表。
        /// </summary>
        public List<GatewayUnityStatusResponse> onlineUnityList;

        /// <summary>
        /// 新版中心网关返回的在线 Unity 列表备用名称。
        /// </summary>
        public List<GatewayUnityStatusResponse> onlineUnities;

        /// <summary>
        /// 新版中心网关返回的 Unity Agent 列表备用名称。
        /// </summary>
        public List<GatewayUnityStatusResponse> unityAgents;

        /// <summary>
        /// 新版中心网关返回的 Unity 列表备用名称。
        /// </summary>
        public List<GatewayUnityStatusResponse> unityList;

        /// <summary>
        /// 新版中心网关返回的 Unity 实例列表备用名称。
        /// </summary>
        public List<GatewayUnityStatusResponse> unityInstances;

        /// <summary>
        /// 新版中心网关返回的 Agent 列表备用名称。
        /// </summary>
        public List<GatewayUnityStatusResponse> agents;
    }

    internal sealed class GatewayCenterStatusResponse
    {
        /// <summary>
        /// 中心网关自身状态。
        /// </summary>
        public string state;

        /// <summary>
        /// 中心网关自身状态详情。
        /// </summary>
        public string detail;
    }

    internal sealed class GatewayUnityStatusResponse
    {
        /// <summary>
        /// Unity 实例稳定身份 ID。
        /// </summary>
        public string unityId;

        /// <summary>
        /// Unity Agent 当前 Session ID。
        /// </summary>
        public string sessionId;

        /// <summary>
        /// Unity Agent 当前 Session ID 的旧字段名。
        /// </summary>
        public string unitySessionId;

        /// <summary>
        /// Unity Agent 名称。
        /// </summary>
        public string agentName;

        /// <summary>
        /// Unity 工程根目录。
        /// </summary>
        public string projectRoot;

        /// <summary>
        /// Unity 工程 Assets 目录。
        /// </summary>
        public string dataPath;

        /// <summary>
        /// Unity Editor 进程 ID。
        /// </summary>
        public int unityProcessId;

        /// <summary>
        /// Unity Editor 版本号。
        /// </summary>
        public string editorVersion;

        /// <summary>
        /// Unity Agent 当前状态。
        /// </summary>
        public string state;

        /// <summary>
        /// Unity Agent 当前状态详情。
        /// </summary>
        public string detail;

        /// <summary>
        /// Unity Agent 最近心跳时间。
        /// </summary>
        public string lastHeartbeatUtc;

        /// <summary>
        /// 兼容中心网关显式在线标记。
        /// </summary>
        public bool isOnline;

        /// <summary>
        /// 兼容中心网关显式在线标记。
        /// </summary>
        public bool? online;

        /// <summary>
        /// 兼容中心网关显式连接标记。
        /// </summary>
        public bool? connected;
    }

    internal static class UnityGatewayProcessController
    {
        private const string PythonExecPrefKey = "ProjectMagicEscape.UnityRoslynGateway.PythonExec";
        private const string GatewayPidPrefKey = "ProjectMagicEscape.UnityRoslynGateway.GatewayPid";
        private const string AutoStartPrefKey = "ProjectMagicEscape.UnityRoslynGateway.AutoStartEnabled";

        private const int CommandTimeoutMs = 30000;
        private const int PipInstallTimeoutMs = 300000;
        private const int StopWaitTimeoutMs = 3000;
        private const int CommandOutputLimit = 2048;

        private static readonly HttpClient HttpClient = new HttpClient();

        private static readonly object SyncRoot = new object();

        private static Process _ownedProcess;
        private static GatewayProcessState _processState = GatewayProcessState.Unknown;
        private static string _lastMessage = "未初始化";
        private static bool _autoStartTriggeredThisSession;

        /// <summary>
        /// 当前是否复用了非本 Unity 控制器启动的中心网关。
        /// </summary>
        private static bool _usingExternalGateway;

        static UnityGatewayProcessController()
        {
            HttpClient.Timeout = TimeSpan.FromSeconds(3);
            TryRecoverOwnedProcess();
            UpdateProcessState();
        }

        public static GatewayProcessState ProcessState => _processState;
        public static string LastMessage => _lastMessage ?? string.Empty;
        public static int OwnedProcessId => _ownedProcess != null && !_ownedProcess.HasExited ? _ownedProcess.Id : -1;
        public static string DefaultPythonExecutable => Application.platform == RuntimePlatform.WindowsEditor ? "python" : "python3";
        public static bool AutoStartEnabled
        {
            get => EditorPrefs.GetBool(AutoStartPrefKey, false);
            set => EditorPrefs.SetBool(AutoStartPrefKey, value);
        }

        public static string GatewayBaseUrl
        {
            get
            {
                string fromEnv = Environment.GetEnvironmentVariable("UNITY_ROSLYN_GATEWAY_URL");
                string url = string.IsNullOrWhiteSpace(fromEnv) ? "http://127.0.0.1:19090" : fromEnv;
                return url.TrimEnd('/');
            }
        }

        public static string PythonExecutable
        {
            get
            {
                string fromPrefs = EditorPrefs.GetString(PythonExecPrefKey, string.Empty);
                if (!string.IsNullOrWhiteSpace(fromPrefs))
                {
                    return fromPrefs;
                }

                string fromEnv = Environment.GetEnvironmentVariable("UNITY_ROSLYN_GATEWAY_PYTHON");
                if (!string.IsNullOrWhiteSpace(fromEnv))
                {
                    return fromEnv.Trim();
                }

                return DefaultPythonExecutable;
            }
            set
            {
                if (string.IsNullOrWhiteSpace(value))
                {
                    EditorPrefs.DeleteKey(PythonExecPrefKey);
                    return;
                }

                EditorPrefs.SetString(PythonExecPrefKey, value.Trim());
            }
        }

        public static string GatewayToolDirectory
        {
            get { return UnityGatewayPaths.GatewayToolDirectory; }
        }

        public static void UpdateProcessState()
        {
            lock (SyncRoot)
            {
                if (_processState == GatewayProcessState.Starting || _processState == GatewayProcessState.Stopping)
                {
                    return;
                }

                if (_ownedProcess != null)
                {
                    if (_ownedProcess.HasExited)
                    {
                        _ownedProcess = null;
                        ClearOwnedPid();
                        _usingExternalGateway = false;
                        _processState = GatewayProcessState.NotRunning;
                        if (string.IsNullOrWhiteSpace(_lastMessage) || _lastMessage.Contains("PID="))
                        {
                            _lastMessage = "网关进程已退出";
                        }
                    }
                    else
                    {
                        _processState = GatewayProcessState.Running;
                        _lastMessage = $"网关进程运行中，PID={_ownedProcess.Id}";
                    }

                    return;
                }

                if (_usingExternalGateway)
                {
                    _processState = GatewayProcessState.Running;
                    if (string.IsNullOrWhiteSpace(_lastMessage))
                    {
                        _lastMessage = "复用已运行的中心网关";
                    }

                    return;
                }

                _processState = GatewayProcessState.NotRunning;
            }
        }

        public static async Task<GatewayProcessOperationResult> StartGatewayAsync()
        {
            AutoStartEnabled = true;
            UnityGatewayAgent.Startup();

            lock (SyncRoot)
            {
                if (_processState == GatewayProcessState.Starting || _processState == GatewayProcessState.Stopping)
                {
                    return new GatewayProcessOperationResult { success = false, message = "网关正在处理其他操作，请稍后重试" };
                }

                if (_ownedProcess != null && !_ownedProcess.HasExited)
                {
                    _usingExternalGateway = false;
                    _processState = GatewayProcessState.Running;
                    _lastMessage = $"网关进程已在运行，PID={_ownedProcess.Id}";
                    return new GatewayProcessOperationResult { success = true, message = _lastMessage };
                }

                if (_ownedProcess != null && _ownedProcess.HasExited)
                {
                    _ownedProcess = null;
                    ClearOwnedPid();
                }

                _processState = GatewayProcessState.Starting;
                _lastMessage = "正在检测中心网关";
            }

            try
            {
                if (await IsGatewayReachableAsync())
                {
                    lock (SyncRoot)
                    {
                        _usingExternalGateway = true;
                        _processState = GatewayProcessState.Running;
                        _lastMessage = "中心网关已可达，复用现有服务";
                    }

                    return new GatewayProcessOperationResult { success = true, message = _lastMessage };
                }

                lock (SyncRoot)
                {
                    _usingExternalGateway = false;
                    _lastMessage = "正在启动中心网关";
                }

                if (!Directory.Exists(GatewayToolDirectory))
                {
                    return SetStartFailure($"未找到网关目录: {GatewayToolDirectory}");
                }

                string gatewayScriptPath = Path.Combine(GatewayToolDirectory, "gateway_server.py");
                string requirementsPath = Path.Combine(GatewayToolDirectory, "requirements.txt");
                if (!File.Exists(gatewayScriptPath))
                {
                    return SetStartFailure($"未找到网关脚本: {gatewayScriptPath}");
                }

                if (!File.Exists(requirementsPath))
                {
                    return SetStartFailure($"未找到依赖文件: {requirementsPath}");
                }

                PythonResolveResult pythonResolve = await ResolvePythonCommandAsync(GatewayToolDirectory);
                if (!pythonResolve.success || pythonResolve.spec == null)
                {
                    return SetStartFailure($"未找到可用 Python 运行时。{pythonResolve.message}");
                }

                PythonCommandSpec pythonSpec = pythonResolve.spec;
                if (!string.Equals(PythonExecutable, pythonSpec.persistValue, StringComparison.Ordinal))
                {
                    PythonExecutable = pythonSpec.persistValue;
                }

                CommandExecResult depCheck = await RunPythonCommandAsync(
                    pythonSpec,
                    "-c \"import fastapi,uvicorn,pydantic\"",
                    GatewayToolDirectory,
                    CommandTimeoutMs);

                if (!depCheck.success)
                {
                    CommandExecResult pipCheck = await RunPythonCommandAsync(
                        pythonSpec,
                        "-m pip --version",
                        GatewayToolDirectory,
                        CommandTimeoutMs);

                    if (!pipCheck.success)
                    {
                        CommandExecResult ensurePip = await RunPythonCommandAsync(
                            pythonSpec,
                            "-m ensurepip --upgrade",
                            GatewayToolDirectory,
                            PipInstallTimeoutMs);

                        if (!ensurePip.success)
                        {
                            return SetStartFailure($"自动部署 pip 失败: {BuildCommandFailureMessage(ensurePip)}");
                        }
                    }

                    CommandExecResult installResult = await RunPythonCommandAsync(
                        pythonSpec,
                        "-m pip install -r requirements.txt",
                        GatewayToolDirectory,
                        PipInstallTimeoutMs);

                    if (!installResult.success)
                    {
                        CommandExecResult userInstallResult = await RunPythonCommandAsync(
                            pythonSpec,
                            "-m pip install --user -r requirements.txt",
                            GatewayToolDirectory,
                            PipInstallTimeoutMs);

                        if (!userInstallResult.success)
                        {
                            return SetStartFailure(
                                $"安装依赖失败。普通安装: {BuildCommandFailureMessage(installResult)}；--user 安装: {BuildCommandFailureMessage(userInstallResult)}");
                        }
                    }

                    CommandExecResult verifyResult = await RunPythonCommandAsync(
                        pythonSpec,
                        "-c \"import fastapi,uvicorn,pydantic\"",
                        GatewayToolDirectory,
                        CommandTimeoutMs);

                    if (!verifyResult.success)
                    {
                        return SetStartFailure($"依赖安装后校验失败: {BuildCommandFailureMessage(verifyResult)}");
                    }
                }

                ProcessStartInfo startInfo = new ProcessStartInfo
                {
                    FileName = pythonSpec.fileName,
                    Arguments = MergeArguments(pythonSpec.prefixArguments, "gateway_server.py"),
                    WorkingDirectory = GatewayToolDirectory,
                    UseShellExecute = false,
                    CreateNoWindow = true,
                    RedirectStandardOutput = false,
                    RedirectStandardError = false,
                };

                startInfo.EnvironmentVariables["UNITY_ROSLYN_GATEWAY_LOG_LEVEL"] = "warning";
                startInfo.EnvironmentVariables["UNITY_ROSLYN_GATEWAY_ACCESS_LOG"] = "0";

                Process process = new Process();
                process.StartInfo = startInfo;
                process.EnableRaisingEvents = true;
                process.Exited += OnOwnedProcessExited;

                bool started = process.Start();
                if (!started)
                {
                    return SetStartFailure("启动网关进程失败，进程未启动");
                }

                lock (SyncRoot)
                {
                    _usingExternalGateway = false;
                    _ownedProcess = process;
                    SaveOwnedPid(process.Id);
                    _processState = GatewayProcessState.Running;
                    _lastMessage = $"网关启动成功，PID={process.Id}";
                }

                return new GatewayProcessOperationResult { success = true, message = _lastMessage };
            }
            catch (Exception ex)
            {
                return SetStartFailure($"启动网关异常: {ex.GetType().Name}: {ex.Message}");
            }
        }

        public static async Task<GatewayProcessOperationResult> StopGatewayAsync()
        {
            AutoStartEnabled = false;

            lock (SyncRoot)
            {
                if (_processState == GatewayProcessState.Starting || _processState == GatewayProcessState.Stopping)
                {
                    return new GatewayProcessOperationResult { success = false, message = "网关正在处理其他操作，请稍后重试" };
                }

                _processState = GatewayProcessState.Stopping;
                _lastMessage = "正在停止网关";
            }

            try
            {
                await TryRequestShutdownAsync();

                Process processToStop = null;
                lock (SyncRoot)
                {
                    processToStop = _ownedProcess;
                }

                if (processToStop != null)
                {
                    if (!processToStop.HasExited && !processToStop.WaitForExit(StopWaitTimeoutMs))
                    {
                        try
                        {
                            processToStop.Kill();
                        }
                        catch
                        {
                        }
                    }
                }
                else
                {
                    int knownPid = LoadOwnedPid();
                    if (knownPid > 0)
                    {
                        try
                        {
                            Process recovered = Process.GetProcessById(knownPid);
                            if (!recovered.HasExited)
                            {
                                recovered.Kill();
                            }
                        }
                        catch
                        {
                        }
                    }
                }

                lock (SyncRoot)
                {
                    _ownedProcess = null;
                    ClearOwnedPid();
                    _usingExternalGateway = false;
                    _processState = GatewayProcessState.NotRunning;
                    _lastMessage = "中心网关已停止，当前 Unity Agent 保持等待重连";
                }

                return new GatewayProcessOperationResult { success = true, message = _lastMessage };
            }
            catch (Exception ex)
            {
                lock (SyncRoot)
                {
                    _processState = GatewayProcessState.Error;
                    _lastMessage = $"停止网关异常: {ex.GetType().Name}: {ex.Message}";
                }

                return new GatewayProcessOperationResult { success = false, message = _lastMessage };
            }
        }

        public static GatewayProcessOperationResult DisconnectCurrentUnityAgent()
        {
            UnityGatewayAgent.Shutdown();
            return new GatewayProcessOperationResult
            {
                success = true,
                message = "当前 Unity Agent 已断开，中心网关仍保持运行",
            };
        }

        public static GatewayProcessOperationResult ConnectCurrentUnityAgent()
        {
            UnityGatewayAgent.Startup();
            return new GatewayProcessOperationResult
            {
                success = true,
                message = "当前 Unity Agent 已开始连接中心网关",
            };
        }

        public static async Task<GatewayRuntimeStatus> QueryRuntimeStatusAsync()
        {
            GatewayRuntimeStatus status = new GatewayRuntimeStatus();

            string url = GatewayBaseUrl + "/v1/status";
            try
            {
                using (HttpRequestMessage request = new HttpRequestMessage(HttpMethod.Get, url))
                using (HttpResponseMessage response = await HttpClient.SendAsync(request))
                {
                    string body = await response.Content.ReadAsStringAsync();
                    if (!response.IsSuccessStatusCode)
                    {
                        status.gatewayReachable = false;
                        status.error = $"HTTP {(int)response.StatusCode}";
                        return status;
                    }

                    GatewayStatusResponse parsed = JsonConvert.DeserializeObject<GatewayStatusResponse>(body);
                    status.gatewayReachable = parsed != null;

                    if (parsed != null)
                    {
                        status.gatewayState = parsed.state ?? string.Empty;
                        status.gatewayDetail = parsed.detail ?? string.Empty;
                        status.centerGatewayState = ResolveCenterGatewayState(parsed);
                        status.centerGatewayDetail = ResolveCenterGatewayDetail(parsed);
                        status.unitySessionId = parsed.unitySessionId ?? string.Empty;
                        status.lastHeartbeatUtc = parsed.lastHeartbeatUtc ?? string.Empty;
                        status.onlineUnityList = ConvertUnityList(parsed);
                        status.unityConnected = status.onlineUnityList.Count > 0;

                        GatewayUnityStatusResponse selectedUnity = parsed.unityTarget;
                        if (selectedUnity == null && !string.IsNullOrWhiteSpace(parsed.unityId))
                        {
                            selectedUnity = new GatewayUnityStatusResponse
                            {
                                unityId = parsed.unityId,
                                sessionId = parsed.unitySessionId,
                                unitySessionId = parsed.unitySessionId,
                                projectRoot = parsed.projectRoot,
                                dataPath = parsed.dataPath,
                                unityProcessId = parsed.unityProcessId,
                                editorVersion = parsed.editorVersion,
                                state = parsed.state,
                                detail = parsed.detail,
                                lastHeartbeatUtc = parsed.lastHeartbeatUtc,
                            };
                        }

                        if (selectedUnity != null)
                        {
                            if (string.IsNullOrWhiteSpace(status.unitySessionId))
                            {
                                status.unitySessionId = !string.IsNullOrWhiteSpace(selectedUnity.sessionId)
                                    ? selectedUnity.sessionId
                                    : selectedUnity.unitySessionId;
                            }

                            if (string.IsNullOrWhiteSpace(status.lastHeartbeatUtc))
                            {
                                status.lastHeartbeatUtc = selectedUnity.lastHeartbeatUtc ?? string.Empty;
                            }
                        }
                    }
                }
            }
            catch (Exception ex)
            {
                status.gatewayReachable = false;
                status.error = $"{ex.GetType().Name}: {ex.Message}";
            }

            return status;
        }

        private static async Task<bool> IsGatewayReachableAsync()
        {
            string url = GatewayBaseUrl + "/v1/status";
            try
            {
                using (HttpRequestMessage request = new HttpRequestMessage(HttpMethod.Get, url))
                using (HttpResponseMessage response = await HttpClient.SendAsync(request))
                {
                    return response.IsSuccessStatusCode;
                }
            }
            catch
            {
                return false;
            }
        }

        private static string ResolveCenterGatewayState(GatewayStatusResponse parsed)
        {
            if (parsed == null)
            {
                return string.Empty;
            }

            if (!string.IsNullOrWhiteSpace(parsed.centerGatewayState))
            {
                return parsed.centerGatewayState;
            }

            if (!string.IsNullOrWhiteSpace(parsed.gatewayState))
            {
                return parsed.gatewayState;
            }

            if (parsed.gateway != null && !string.IsNullOrWhiteSpace(parsed.gateway.state))
            {
                return parsed.gateway.state;
            }

            return "Online";
        }

        private static string ResolveCenterGatewayDetail(GatewayStatusResponse parsed)
        {
            if (parsed == null)
            {
                return string.Empty;
            }

            if (!string.IsNullOrWhiteSpace(parsed.centerGatewayDetail))
            {
                return parsed.centerGatewayDetail;
            }

            if (!string.IsNullOrWhiteSpace(parsed.gatewayDetail))
            {
                return parsed.gatewayDetail;
            }

            if (parsed.gateway != null && !string.IsNullOrWhiteSpace(parsed.gateway.detail))
            {
                return parsed.gateway.detail;
            }

            return "中心网关可访问";
        }

        private static List<GatewayUnityRuntimeInfo> ConvertUnityList(GatewayStatusResponse parsed)
        {
            List<GatewayUnityRuntimeInfo> result = new List<GatewayUnityRuntimeInfo>();
            if (parsed == null)
            {
                return result;
            }

            List<GatewayUnityStatusResponse> source = parsed.onlineUnities
                ?? parsed.onlineUnityList
                ?? parsed.unityAgents
                ?? parsed.unityList
                ?? parsed.unityInstances
                ?? parsed.agents;

            if (source != null)
            {
                for (int i = 0; i < source.Count; i++)
                {
                    GatewayUnityRuntimeInfo item = ConvertUnityInfo(source[i]);
                    if (item != null)
                    {
                        result.Add(item);
                    }
                }
            }

            if (result.Count == 0 && parsed.unityTarget != null)
            {
                GatewayUnityRuntimeInfo item = ConvertUnityInfo(parsed.unityTarget);
                if (item != null)
                {
                    result.Add(item);
                }
            }

            return result;
        }

        private static GatewayUnityRuntimeInfo ConvertUnityInfo(GatewayUnityStatusResponse source)
        {
            if (source == null)
            {
                return null;
            }

            return new GatewayUnityRuntimeInfo
            {
                unityId = source.unityId ?? string.Empty,
                sessionId = !string.IsNullOrWhiteSpace(source.sessionId) ? source.sessionId : source.unitySessionId ?? string.Empty,
                agentName = source.agentName ?? string.Empty,
                projectRoot = source.projectRoot ?? string.Empty,
                dataPath = source.dataPath ?? string.Empty,
                unityProcessId = source.unityProcessId,
                editorVersion = source.editorVersion ?? string.Empty,
                state = source.state ?? string.Empty,
                detail = source.detail ?? string.Empty,
                lastHeartbeatUtc = source.lastHeartbeatUtc ?? string.Empty,
            };
        }

        private static async Task TryStopExistingGatewayBeforeStartAsync()
        {
            await TryRequestShutdownAsync();

            Process processToStop = null;
            lock (SyncRoot)
            {
                processToStop = _ownedProcess;
            }

            if (processToStop != null)
            {
                if (!processToStop.HasExited && !processToStop.WaitForExit(StopWaitTimeoutMs))
                {
                    try
                    {
                        processToStop.Kill();
                    }
                    catch
                    {
                    }
                }
            }
            else
            {
                int knownPid = LoadOwnedPid();
                if (knownPid > 0)
                {
                    try
                    {
                        Process recovered = Process.GetProcessById(knownPid);
                        if (!recovered.HasExited)
                        {
                            if (!recovered.WaitForExit(StopWaitTimeoutMs))
                            {
                                recovered.Kill();
                            }
                        }
                    }
                    catch
                    {
                    }
                }
            }

            lock (SyncRoot)
            {
                _ownedProcess = null;
                ClearOwnedPid();
            }
        }

        public static void TryAutoStartGatewayOnEditorLaunch()
        {
            lock (SyncRoot)
            {
                if (_autoStartTriggeredThisSession)
                {
                    return;
                }

                _autoStartTriggeredThisSession = true;
            }

            UpdateProcessState();

            bool shouldRestoreAgent = AutoStartEnabled || ProcessState == GatewayProcessState.Running;
            if (!shouldRestoreAgent)
            {
                return;
            }

            UnityGatewayAgent.Startup();

            if (ProcessState == GatewayProcessState.Running || ProcessState == GatewayProcessState.Starting)
            {
                return;
            }

            _ = StartGatewayAsync();
        }

        private static async Task TryRequestShutdownAsync()
        {
            string url = GatewayBaseUrl + "/internal/control/shutdown";
            try
            {
                using (StringContent content = new StringContent("{}", Encoding.UTF8, "application/json"))
                using (HttpResponseMessage response = await HttpClient.PostAsync(url, content))
                {
                    if (!response.IsSuccessStatusCode)
                    {
                        return;
                    }
                }
            }
            catch
            {
            }
        }

        private static GatewayProcessOperationResult SetStartFailure(string message)
        {
            lock (SyncRoot)
            {
                _usingExternalGateway = false;
                _processState = GatewayProcessState.Error;
                _lastMessage = message;
            }

            return new GatewayProcessOperationResult { success = false, message = message };
        }

        private static async Task<PythonResolveResult> ResolvePythonCommandAsync(string workingDirectory)
        {
            List<PythonCommandSpec> candidates = BuildPythonCandidates();
            if (candidates.Count == 0)
            {
                return new PythonResolveResult
                {
                    success = false,
                    message = "没有可尝试的 Python 命令，请在控制面板中设置有效路径。",
                };
            }

            StringBuilder failures = new StringBuilder();

            for (int i = 0; i < candidates.Count; i++)
            {
                PythonCommandSpec candidate = candidates[i];
                CommandExecResult versionResult = await RunPythonCommandAsync(
                    candidate,
                    "--version",
                    workingDirectory,
                    CommandTimeoutMs);

                if (versionResult.success)
                {
                    return new PythonResolveResult
                    {
                        success = true,
                        spec = candidate,
                        message = $"已使用 {candidate.displayName}",
                    };
                }

                if (failures.Length > 0)
                {
                    failures.Append(" | ");
                }

                failures.Append(candidate.displayName)
                    .Append(": ")
                    .Append(BuildCommandFailureMessage(versionResult));
            }

            return new PythonResolveResult
            {
                success = false,
                message = failures.ToString(),
            };
        }

        private static List<PythonCommandSpec> BuildPythonCandidates()
        {
            List<PythonCommandSpec> candidates = new List<PythonCommandSpec>(6);
            HashSet<string> dedupe = new HashSet<string>(StringComparer.OrdinalIgnoreCase);

            TryAddPythonCandidate(candidates, dedupe, PythonExecutable);

            if (Application.platform == RuntimePlatform.WindowsEditor)
            {
                TryAddPythonCandidate(candidates, dedupe, "py -3");
                TryAddPythonCandidate(candidates, dedupe, "python");
                TryAddPythonCandidate(candidates, dedupe, "python3");
                TryAddPythonCandidate(candidates, dedupe, "py");
            }
            else
            {
                TryAddPythonCandidate(candidates, dedupe, "python3");
                TryAddPythonCandidate(candidates, dedupe, "python");
            }

            return candidates;
        }

        private static void TryAddPythonCandidate(List<PythonCommandSpec> candidates, HashSet<string> dedupe, string commandText)
        {
            PythonCommandSpec spec = ParsePythonCommand(commandText);
            if (spec == null)
            {
                return;
            }

            string key = $"{spec.fileName}\n{spec.prefixArguments}";
            if (!dedupe.Add(key))
            {
                return;
            }

            candidates.Add(spec);
        }

        private static PythonCommandSpec ParsePythonCommand(string commandText)
        {
            if (string.IsNullOrWhiteSpace(commandText))
            {
                return null;
            }

            string trimmed = commandText.Trim();
            string normalized = trimmed;

            if (trimmed.Length >= 2 && trimmed.StartsWith("\"") && trimmed.EndsWith("\""))
            {
                normalized = trimmed.Substring(1, trimmed.Length - 2);
            }

            if (File.Exists(normalized))
            {
                return new PythonCommandSpec
                {
                    fileName = normalized,
                    prefixArguments = string.Empty,
                    displayName = normalized,
                    persistValue = normalized,
                };
            }

            string fileName;
            string prefixArguments;

            if (trimmed.StartsWith("\""))
            {
                int closingQuote = trimmed.IndexOf('"', 1);
                if (closingQuote > 0)
                {
                    fileName = trimmed.Substring(1, closingQuote - 1).Trim();
                    prefixArguments = trimmed.Substring(closingQuote + 1).Trim();
                }
                else
                {
                    fileName = trimmed.Trim('"').Trim();
                    prefixArguments = string.Empty;
                }
            }
            else
            {
                int firstSpace = trimmed.IndexOf(' ');
                if (firstSpace > 0)
                {
                    fileName = trimmed.Substring(0, firstSpace).Trim();
                    prefixArguments = trimmed.Substring(firstSpace + 1).Trim();
                }
                else
                {
                    fileName = trimmed;
                    prefixArguments = string.Empty;
                }
            }

            if (string.IsNullOrWhiteSpace(fileName))
            {
                return null;
            }

            string persistValue = string.IsNullOrWhiteSpace(prefixArguments)
                ? fileName
                : $"{fileName} {prefixArguments}";

            return new PythonCommandSpec
            {
                fileName = fileName,
                prefixArguments = prefixArguments,
                displayName = persistValue,
                persistValue = persistValue,
            };
        }

        private static Task<CommandExecResult> RunPythonCommandAsync(
            PythonCommandSpec spec,
            string pythonArguments,
            string workingDirectory,
            int timeoutMs)
        {
            return RunCommandAsync(spec.fileName, MergeArguments(spec.prefixArguments, pythonArguments), workingDirectory, timeoutMs);
        }

        private static async Task<CommandExecResult> RunCommandAsync(string fileName, string arguments, string workingDirectory, int timeoutMs)
        {
            return await Task.Run(() =>
            {
                CommandExecResult result = new CommandExecResult();
                Process process = null;

                try
                {
                    ProcessStartInfo startInfo = new ProcessStartInfo
                    {
                        FileName = fileName,
                        Arguments = arguments,
                        WorkingDirectory = workingDirectory,
                        UseShellExecute = false,
                        CreateNoWindow = true,
                        RedirectStandardError = true,
                        RedirectStandardOutput = true,
                    };

                    StringBuilder stdoutBuilder = new StringBuilder();
                    StringBuilder stderrBuilder = new StringBuilder();

                    process = new Process();
                    process.StartInfo = startInfo;
                    process.OutputDataReceived += (_, args) => AppendCommandOutput(stdoutBuilder, args.Data);
                    process.ErrorDataReceived += (_, args) => AppendCommandOutput(stderrBuilder, args.Data);

                    process.Start();
                    process.BeginOutputReadLine();
                    process.BeginErrorReadLine();

                    if (!process.WaitForExit(Mathf.Max(1000, timeoutMs)))
                    {
                        result.success = false;
                        result.exitCode = -1;
                        result.errorMessage = "命令执行超时";

                        try
                        {
                            process.Kill();
                        }
                        catch
                        {
                        }

                        result.stdout = stdoutBuilder.ToString().Trim();
                        result.stderr = stderrBuilder.ToString().Trim();
                        return result;
                    }

                    process.WaitForExit();

                    result.exitCode = process.ExitCode;
                    result.success = process.ExitCode == 0;
                    result.stdout = stdoutBuilder.ToString().Trim();
                    result.stderr = stderrBuilder.ToString().Trim();
                    return result;
                }
                catch (Exception ex)
                {
                    result.success = false;
                    result.exitCode = -1;
                    result.errorMessage = $"{ex.GetType().Name}: {ex.Message}";
                    return result;
                }
                finally
                {
                    process?.Dispose();
                }
            });
        }

        private static string BuildCommandFailureMessage(CommandExecResult result)
        {
            if (result == null)
            {
                return "unknown";
            }

            StringBuilder message = new StringBuilder();
            message.Append("exitCode=").Append(result.exitCode);

            if (!string.IsNullOrWhiteSpace(result.errorMessage))
            {
                message.Append(", error=").Append(result.errorMessage);
                return message.ToString();
            }

            if (!string.IsNullOrWhiteSpace(result.stderr))
            {
                message.Append(", stderr=").Append(result.stderr);
                return message.ToString();
            }

            if (!string.IsNullOrWhiteSpace(result.stdout))
            {
                message.Append(", stdout=").Append(result.stdout);
            }

            return message.ToString();
        }

        private static void AppendCommandOutput(StringBuilder builder, string line)
        {
            if (builder == null || string.IsNullOrEmpty(line) || builder.Length >= CommandOutputLimit)
            {
                return;
            }

            int remain = CommandOutputLimit - builder.Length;
            if (remain <= 0)
            {
                return;
            }

            string toAppend = line;
            if (line.Length + Environment.NewLine.Length > remain)
            {
                int allowedLength = Math.Max(0, remain - Environment.NewLine.Length);
                toAppend = allowedLength > 0 ? line.Substring(0, allowedLength) : string.Empty;
            }

            if (toAppend.Length > 0)
            {
                builder.AppendLine(toAppend);
            }
        }

        private static string MergeArguments(string prefixArguments, string suffixArguments)
        {
            if (string.IsNullOrWhiteSpace(prefixArguments))
            {
                return suffixArguments ?? string.Empty;
            }

            if (string.IsNullOrWhiteSpace(suffixArguments))
            {
                return prefixArguments;
            }

            return $"{prefixArguments} {suffixArguments}";
        }

        private static void OnOwnedProcessExited(object sender, EventArgs e)
        {
            lock (SyncRoot)
            {
                _ownedProcess = null;
                ClearOwnedPid();
                _processState = GatewayProcessState.NotRunning;
                _lastMessage = "网关进程已退出";
            }
        }

        private static void TryRecoverOwnedProcess()
        {
            int pid = LoadOwnedPid();
            if (pid <= 0)
            {
                return;
            }

            try
            {
                Process process = Process.GetProcessById(pid);
                if (process.HasExited)
                {
                    ClearOwnedPid();
                    return;
                }

                process.EnableRaisingEvents = true;
                process.Exited += OnOwnedProcessExited;

                _ownedProcess = process;
                _processState = GatewayProcessState.Running;
                _lastMessage = $"恢复已启动网关进程，PID={pid}";
            }
            catch
            {
                ClearOwnedPid();
            }
        }

        private static int LoadOwnedPid()
        {
            return EditorPrefs.GetInt(GatewayPidPrefKey, -1);
        }

        private static void SaveOwnedPid(int pid)
        {
            EditorPrefs.SetInt(GatewayPidPrefKey, pid);
        }

        private static void ClearOwnedPid()
        {
            EditorPrefs.DeleteKey(GatewayPidPrefKey);
        }

        private sealed class CommandExecResult
        {
            public bool success;
            public int exitCode;
            public string stdout;
            public string stderr;
            public string errorMessage;
        }

        private sealed class PythonCommandSpec
        {
            public string fileName;
            public string prefixArguments;
            public string displayName;
            public string persistValue;
        }

        private sealed class PythonResolveResult
        {
            public bool success;
            public PythonCommandSpec spec;
            public string message;
        }
    }
}
