using System;
using System.Collections.Generic;
using System.IO;
using System.Net.Http;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using Newtonsoft.Json;
using UnityEditor;
using UnityEditor.Compilation;
using UnityEditorInternal;
using UnityEngine;

namespace ProjectMagicEscape.Editor.RoslynGateway
{
    internal static class UnityGatewayAgent
    {
        private const string RegisterPath = "/internal/agent/register";
        private const string HeartbeatPath = "/internal/agent/heartbeat";
        private const string UnregisterPath = "/internal/agent/unregister";
        private const string PullTaskPath = "/internal/agent/pull-task";
        private const string PushResultPath = "/internal/agent/push-result";
        private const string WaitingForAsyncExecutionStage = "WaitingForAsyncExecution";

        private const double RegisterRetrySeconds = 1.0;
        private const int DefaultHttpTimeoutMs = 3000;
        private const int LongPollMaxWaitMs = 500;
        private const int TransportIdleDelayMs = 100;
        private const int PausedMainThreadRetryDelayMs = 200;

        private static readonly object TransportSync = new object();
        private static readonly object AuditLogSync = new object();
        private static readonly Queue<GatewayTaskPayload> PendingPulledTasks = new Queue<GatewayTaskPayload>();
        private static readonly Queue<InternalPushResultRequest> PendingPushResults = new Queue<InternalPushResultRequest>();

        private static HttpClient _httpClient;
        private static string _gatewayBaseUrl;
        private static bool _initialized;
        private static CancellationTokenSource _transportLoopCts;
        private static Task _transportLoopTask;
        private static SynchronizationContext _mainThreadContext;
        private static bool _isEditorPaused;
        private static DateTime _nextRegisterAttemptUtc = DateTime.MinValue;
        private static DateTime _nextHeartbeatUtc = DateTime.MinValue;
        private static DateTime _nextPausedMainThreadSignalUtc = DateTime.MinValue;

        private static string _sessionId;
        private static string _agentState = GatewayStateValues.Ready;
        private static string _stateDetail = "Idle";
        private static string _lastLoggedHeartbeatState = string.Empty;
        private static string _lastLoggedHeartbeatDetail = string.Empty;

        /// <summary>
        /// 注册中心网关时上报的 Unity 工程根目录。
        /// </summary>
        private static string _projectRoot = string.Empty;

        /// <summary>
        /// 注册中心网关时上报的当前 Unity 稳定身份 ID。
        /// </summary>
        private static string _unityId = string.Empty;

        /// <summary>
        /// 注册中心网关时上报的 Assets 目录路径。
        /// </summary>
        private static string _dataPath = string.Empty;

        /// <summary>
        /// 注册中心网关时上报的 Unity Editor 进程 ID。
        /// </summary>
        private static int _unityProcessId;

        /// <summary>
        /// 注册中心网关时上报的 Unity Editor 版本号。
        /// </summary>
        private static string _editorVersion = string.Empty;

        private static float _heartbeatIntervalSec = 1f;

        private static GatewayTaskPayload _pendingTask;
        private static GatewayPersistedTaskState _activeTask;
        private static GatewayDoCodeExecutionState _activeExecutionState;
        private static bool _isExecuting;

        /// <summary>
        /// 当前 Unity Agent 是否已启动传输循环。
        /// </summary>
        public static bool IsStarted => _initialized;

        /// <summary>
        /// 当前 Unity 实例注册到中心网关时使用的稳定身份 ID。
        /// </summary>
        public static string CurrentUnityId => _unityId ?? string.Empty;

        public static bool HasActiveTask => _activeTask != null;

        public static string ActiveTaskRequestId => _activeTask != null && _activeTask.task != null
            ? _activeTask.task.requestId ?? string.Empty
            : string.Empty;

        public static string ActiveTaskStage => _activeTask != null ? _activeTask.stage ?? string.Empty : string.Empty;

        public static string ActiveTaskDetail => _activeTask != null ? _activeTask.detail ?? string.Empty : string.Empty;

        public static string ActiveTaskWaitingStartedAtUtc => _activeTask != null ? _activeTask.waitingStartedAtUtc ?? string.Empty : string.Empty;

        public static string ActiveTaskDeadlineUtc => _activeTask != null ? _activeTask.deadlineUtc ?? string.Empty : string.Empty;

        public static GatewayCompilationSnapshot CurrentCompilationSnapshot => UnityGatewayCompilationCoordinator.GetSnapshot();

        public static void Startup()
        {
            if (_initialized)
            {
                return;
            }

            _gatewayBaseUrl = GetGatewayBaseUrl();
            _httpClient = new HttpClient();
            _httpClient.Timeout = Timeout.InfiniteTimeSpan;
            _mainThreadContext = SynchronizationContext.Current;
            _isEditorPaused = EditorApplication.isPaused;
            RefreshUnityIdentity();

            UnityGatewayCompilationCoordinator.Startup();
            RecoverPersistedTask();

            EditorApplication.update += OnEditorUpdate;
            EditorApplication.pauseStateChanged += OnPauseStateChanged;
            _initialized = true;
            SetState(GatewayStateValues.Ready, "Waiting for registration");
            _nextRegisterAttemptUtc = DateTime.UtcNow;
            _nextHeartbeatUtc = DateTime.UtcNow;
            StartTransportLoop();
            SignalMainThreadWork();
            WriteStateAuditLog("startup", string.Empty, _agentState, string.Empty, _stateDetail, "Unity Gateway Agent started");
            Debug.Log($"[UnityGateway] Started. Gateway={_gatewayBaseUrl}");
        }

        public static void Shutdown()
        {
            if (!_initialized)
            {
                return;
            }

            string sessionId = GetSessionId();

            EditorApplication.update -= OnEditorUpdate;
            EditorApplication.pauseStateChanged -= OnPauseStateChanged;

            StopTransportLoop();
            TryUnregisterSession(sessionId);
            _httpClient?.Dispose();
            _httpClient = null;
            _initialized = false;
            _mainThreadContext = null;
            _isEditorPaused = false;
            _activeExecutionState = null;
            lock (TransportSync)
            {
                _sessionId = null;
                PendingPulledTasks.Clear();
                PendingPushResults.Clear();
                _nextRegisterAttemptUtc = DateTime.MinValue;
                _nextHeartbeatUtc = DateTime.MinValue;
                _nextPausedMainThreadSignalUtc = DateTime.MinValue;
            }

            _pendingTask = null;
            UnityGatewayCompilationCoordinator.Shutdown();
            WriteStateAuditLog("shutdown", _agentState, string.Empty, _stateDetail, string.Empty, "Unity Gateway Agent stopped");
        }

        public static void OnBeforeAssemblyReload()
        {
            if (!_initialized)
            {
                return;
            }

            if (_activeTask != null && string.Equals(_activeTask.stage, UnityGatewayCompilationCoordinator.WaitingForCompilationStage, StringComparison.Ordinal))
            {
                _activeTask.reloadObserved = true;
                _activeTask.detail = "Unity 正在域重载";
                UnityGatewayCompilationCoordinator.MarkReloadObserved();
                PersistActiveTask();
            }
            else if (_activeTask != null && string.Equals(_activeTask.stage, WaitingForAsyncExecutionStage, StringComparison.Ordinal))
            {
                _activeTask.detail = "异步 do-code 执行期间发生域重载";
                PersistActiveTask();
            }

            if (!string.IsNullOrEmpty(_sessionId))
            {
                _ = HeartbeatOnceAsync(_sessionId, GatewayStateValues.Reloading, "Assembly reload", CancellationToken.None);
            }

            StopTransportLoop();
        }

        private static void OnPauseStateChanged(PauseState state)
        {
            if (!_initialized)
            {
                return;
            }

            if (state == PauseState.Paused)
            {
                _isEditorPaused = true;
                SetState(GatewayStateValues.Ready, "Editor 已暂停");
                _nextPausedMainThreadSignalUtc = DateTime.UtcNow;
                SchedulePausedDelayCallPump();
            }
            else if (state == PauseState.Unpaused)
            {
                _isEditorPaused = false;
                SetState(GatewayStateValues.Ready, "Editor 已恢复");
            }

            SignalMainThreadWork();
        }

        private static void OnEditorUpdate()
        {
            TickMainThreadLoop();
        }

        /// <summary>
        /// Unity 主线程上的网关轮询与执行入口。
        /// </summary>
        private static void TickMainThreadLoop()
        {
            if (!_initialized)
            {
                return;
            }

            if (_isExecuting)
            {
                return;
            }

            if (_activeTask != null)
            {
                TickActiveTask();
                return;
            }

            if (_pendingTask != null)
            {
                ExecutePendingTask();
                return;
            }

            GatewayTaskPayload pulledTask = TryDequeuePulledTask();
            if (pulledTask != null)
            {
                _pendingTask = pulledTask;
                ExecutePendingTask();
            }
        }

        /// <summary>
        /// 后台传输循环负责注册、心跳、拉取任务和推送结果，避免网络链路依赖 Unity 暂停态主线程回调。
        /// </summary>
        private static async Task RunTransportLoopAsync(CancellationToken cancellationToken)
        {
            while (!cancellationToken.IsCancellationRequested)
            {
                try
                {
                    string sessionId = GetSessionId();
                    if (string.IsNullOrEmpty(sessionId))
                    {
                        if (DateTime.UtcNow < _nextRegisterAttemptUtc)
                        {
                            await Task.Delay(TransportIdleDelayMs, cancellationToken);
                            continue;
                        }

                        InternalRegisterResponse registerResponse = await RegisterAsync(cancellationToken);
                        if (registerResponse == null || !registerResponse.accepted || string.IsNullOrWhiteSpace(registerResponse.sessionId))
                        {
                            _nextRegisterAttemptUtc = DateTime.UtcNow.AddSeconds(RegisterRetrySeconds);
                            await Task.Delay(TransportIdleDelayMs, cancellationToken);
                            continue;
                        }

                        lock (TransportSync)
                        {
                            _sessionId = registerResponse.sessionId;
                            _heartbeatIntervalSec = Mathf.Max(0.2f, registerResponse.heartbeatIntervalSec);
                            _nextHeartbeatUtc = DateTime.UtcNow;
                        }

                        SetState(GatewayStateValues.Ready, _activeTask != null ? "Recovered active task" : "Registered");
                        SignalMainThreadWork();
                        Debug.Log($"[UnityGateway] Registered session={registerResponse.sessionId}");
                        continue;
                    }

                    await PushPendingResultsAsync(sessionId, cancellationToken);
                    await SendHeartbeatIfNeededAsync(sessionId, cancellationToken);

                    if (ShouldRetryPausedMainThreadWork())
                    {
                        SignalMainThreadWork();
                    }

                    if (HasLocalWorkInFlight())
                    {
                        await Task.Delay(TransportIdleDelayMs, cancellationToken);
                        continue;
                    }

                    InternalPullTaskResponse pullResponse = await PullTaskAsync(sessionId, LongPollMaxWaitMs, cancellationToken);
                    if (pullResponse == null)
                    {
                        await Task.Delay(TransportIdleDelayMs, cancellationToken);
                        continue;
                    }

                    if (!pullResponse.accepted)
                    {
                        ResetSession($"PullTask rejected: {pullResponse.message}");
                        await Task.Delay(TransportIdleDelayMs, cancellationToken);
                        continue;
                    }

                    if (pullResponse.hasTask && pullResponse.task != null)
                    {
                        QueuePulledTask(pullResponse.task);
                        SignalMainThreadWork();
                        continue;
                    }
                }
                catch (OperationCanceledException)
                {
                    break;
                }
                catch (Exception ex)
                {
                    Debug.LogWarning($"[UnityGateway] Transport loop failed: {ex.Message}");
                    await Task.Delay(TransportIdleDelayMs, cancellationToken);
                }
            }
        }

        private static void StartTransportLoop()
        {
            StopTransportLoop();

            _transportLoopCts = new CancellationTokenSource();
            _transportLoopTask = Task.Run(() => RunTransportLoopAsync(_transportLoopCts.Token));
        }

        private static void StopTransportLoop()
        {
            CancellationTokenSource cts = _transportLoopCts;
            Task transportTask = _transportLoopTask;

            _transportLoopCts = null;
            _transportLoopTask = null;

            if (cts == null)
            {
                return;
            }

            try
            {
                cts.Cancel();
                transportTask?.Wait(500);
            }
            catch
            {
            }
            finally
            {
                cts.Dispose();
            }
        }

        private static void ExecutePendingTask()
        {
            GatewayTaskPayload task = _pendingTask;
            _pendingTask = null;

            if (task == null)
            {
                return;
            }

            _isExecuting = true;
            SetState(GatewayStateValues.Busy, $"Executing {task.requestId}");

            GatewayDoCodeExecutionState executionState;
            try
            {
                executionState = RoslynDoCodeExecutor.BeginExecute(task.code, task.timeoutSec);
                executionState.result.requestId = task.requestId;
            }
            catch (Exception ex)
            {
                executionState = new GatewayDoCodeExecutionState();
                executionState.result.requestId = task.requestId;
                executionState.result.success = false;
                executionState.result.state = "RuntimeError";
                executionState.result.error.type = ex.GetType().FullName;
                executionState.result.error.message = ex.Message;
                executionState.result.error.stackTrace = ex.ToString();
            }
            finally
            {
                _isExecuting = false;
            }

            if (executionState.IsPending)
            {
                ActivateAsyncExecution(task, executionState);
                return;
            }

            HandleExecutionCompletion(task, executionState.result);
        }

        /// <summary>
        /// 将未完成的 do-code 异步任务切换到 Editor 轮询阶段。
        /// </summary>
        private static void ActivateAsyncExecution(GatewayTaskPayload task, GatewayDoCodeExecutionState executionState)
        {
            if (task == null || executionState == null)
            {
                return;
            }

            _activeExecutionState = executionState;
            _activeTask = new GatewayPersistedTaskState();
            _activeTask.task = task;
            _activeTask.result = executionState.result;
            _activeTask.stage = WaitingForAsyncExecutionStage;
            _activeTask.waitingStartedAtUtc = DateTime.UtcNow.ToString("O");
            _activeTask.deadlineUtc = DateTime.UtcNow.AddSeconds(GetEffectiveExecutionTimeoutSec(task)).ToString("O");
            _activeTask.detail = "等待异步代码执行完成";
            _activeTask.reloadObserved = false;

            PersistActiveTask();
            SetState(GatewayStateValues.Busy, $"Waiting for async execution {task.requestId}");
            SignalMainThreadWork();
        }

        /// <summary>
        /// 统一处理 do-code 执行完成后的收尾逻辑，包括直接回传结果或继续等待 Unity 编译。
        /// </summary>
        private static void HandleExecutionCompletion(GatewayTaskPayload task, GatewayDoCodeResult executionResult)
        {
            if (task == null || executionResult == null)
            {
                SetState(GatewayStateValues.Ready, "Idle");
                return;
            }

            if (!executionResult.success)
            {
                SetState(GatewayStateValues.Ready, "Idle");
                EnqueueResult(task, executionResult);
                return;
            }

            if (!ShouldHandleCompilation(task))
            {
                SetState(GatewayStateValues.Ready, "Idle");
                EnqueueResult(task, executionResult);
                return;
            }

            PrepareCompilationMetadata(task, executionResult);

            if (!task.waitForScriptCompilation)
            {
                TriggerCompilation(task);
                SetState(GatewayStateValues.Ready, "Idle");
                EnqueueResult(task, executionResult);
                return;
            }

            _activeTask = new GatewayPersistedTaskState();
            _activeTask.task = task;
            _activeTask.result = executionResult;
            _activeTask.stage = UnityGatewayCompilationCoordinator.WaitingForCompilationStage;
            _activeTask.waitingStartedAtUtc = DateTime.UtcNow.ToString("O");
            _activeTask.deadlineUtc = DateTime.UtcNow.AddSeconds(GetEffectiveCompileTimeoutSec(task, out bool _)).ToString("O");
            _activeTask.detail = "等待 Unity 编译结果";
            _activeTask.reloadObserved = false;

            PersistActiveTask();
            TriggerCompilation(task);
            PersistActiveTask();

            SetState(GatewayStateValues.Busy, $"Waiting for compilation {task.requestId}");
        }

        private static void TickActiveTask()
        {
            if (_activeTask == null || _activeTask.task == null)
            {
                ClearActiveTaskState();
                return;
            }

            if (string.Equals(_activeTask.stage, WaitingForAsyncExecutionStage, StringComparison.Ordinal))
            {
                TickAsyncExecutionTask();
                return;
            }

            if (!string.Equals(_activeTask.stage, UnityGatewayCompilationCoordinator.WaitingForCompilationStage, StringComparison.Ordinal))
            {
                return;
            }

            if (HasTaskTimedOut(_activeTask))
            {
                GatewayDoCodeResult timeoutResult = _activeTask.result ?? new GatewayDoCodeResult();
                timeoutResult.requestId = _activeTask.task.requestId;
                timeoutResult.success = false;
                timeoutResult.state = "Timeout";
                timeoutResult.error.type = "Timeout";
                timeoutResult.error.message = $"等待 Unity 编译超时（{GetEffectiveCompileTimeoutSec(_activeTask.task, out bool _)} 秒）";
                timeoutResult.error.stackTrace = string.Empty;
                timeoutResult.compile.compilationCompleted = false;
                timeoutResult.compile.compilationHadErrors = false;
                timeoutResult.compile.compilationElapsedMs = CalculateWaitElapsedMilliseconds(_activeTask);
                SetState(GatewayStateValues.Ready, "Idle");
                EnqueueResult(_activeTask.task, timeoutResult);
                ClearActiveTaskState();
                return;
            }

            GatewayCompilationSnapshot snapshot = UnityGatewayCompilationCoordinator.GetSnapshot();
            if (snapshot != null && snapshot.completed)
            {
                GatewayDoCodeResult result = BuildCompletedCompilationResult(_activeTask, snapshot);
                SetState(GatewayStateValues.Ready, "Idle");
                EnqueueResult(_activeTask.task, result);
                ClearActiveTaskState();
                return;
            }

            if (_activeTask.reloadObserved && !EditorApplication.isCompiling)
            {
                GatewayCompilationSnapshot recoveredSnapshot = new GatewayCompilationSnapshot();
                recoveredSnapshot.sessionId = _activeTask.result != null ? _activeTask.result.compile.compilationSessionId : string.Empty;
                recoveredSnapshot.started = true;
                recoveredSnapshot.completed = true;
                recoveredSnapshot.hadErrors = EditorUtility.scriptCompilationFailed;
                recoveredSnapshot.reloadObserved = true;
                recoveredSnapshot.detail = recoveredSnapshot.hadErrors ? "Unity 域重载后检测到编译错误" : "Unity 域重载后编译完成";
                recoveredSnapshot.elapsedMs = CalculateWaitElapsedMilliseconds(_activeTask);
                GatewayDoCodeResult result = BuildCompletedCompilationResult(_activeTask, recoveredSnapshot);
                SetState(GatewayStateValues.Ready, "Idle");
                EnqueueResult(_activeTask.task, result);
                ClearActiveTaskState();
                return;
            }

            _activeTask.detail = EditorApplication.isCompiling ? "Unity 正在编译脚本" : "等待 Unity 返回编译完成状态";
            PersistActiveTask();
        }

        /// <summary>
        /// 轮询异步 do-code 执行结果，避免在主线程同步阻塞 Task。
        /// </summary>
        private static void TickAsyncExecutionTask()
        {
            if (_activeTask == null || _activeTask.task == null)
            {
                ClearActiveTaskState();
                return;
            }

            if (HasTaskTimedOut(_activeTask))
            {
                GatewayDoCodeResult timeoutResult = CreateAsyncExecutionTimeoutResult(_activeTask);
                SetState(GatewayStateValues.Ready, "Idle");
                EnqueueResult(_activeTask.task, timeoutResult);
                ClearActiveTaskState();
                return;
            }

            if (_activeExecutionState == null)
            {
                GatewayDoCodeResult lostContextResult = CreateAsyncExecutionContextLostResult(_activeTask);
                SetState(GatewayStateValues.Ready, "Idle");
                EnqueueResult(_activeTask.task, lostContextResult);
                ClearActiveTaskState();
                return;
            }

            _activeExecutionState = RoslynDoCodeExecutor.ContinueExecute(_activeExecutionState);
            if (_activeExecutionState == null || _activeExecutionState.IsPending)
            {
                _activeTask.detail = "等待异步代码执行完成";
                PersistActiveTask();
                return;
            }

            GatewayTaskPayload task = _activeTask.task;
            GatewayDoCodeResult result = _activeExecutionState.result ?? new GatewayDoCodeResult();
            result.requestId = task.requestId;
            ApplyAsyncExecutionElapsedTime(result, _activeTask);

            ClearActiveTaskState();
            HandleExecutionCompletion(task, result);
        }

        private static void EnqueueResult(GatewayTaskPayload task, GatewayDoCodeResult executionResult)
        {
            if (task == null || executionResult == null)
            {
                return;
            }

            InternalPushResultRequest request = new InternalPushResultRequest();
            request.requestId = task.requestId;
            request.result = executionResult;

            lock (TransportSync)
            {
                PendingPushResults.Enqueue(request);
            }
            SignalMainThreadWork();
        }

        private static void QueuePulledTask(GatewayTaskPayload task)
        {
            if (task == null)
            {
                return;
            }

            lock (TransportSync)
            {
                PendingPulledTasks.Enqueue(task);
            }
        }

        private static GatewayTaskPayload TryDequeuePulledTask()
        {
            lock (TransportSync)
            {
                if (PendingPulledTasks.Count == 0)
                {
                    return null;
                }

                return PendingPulledTasks.Dequeue();
            }
        }

        private static async Task PushPendingResultsAsync(string sessionId, CancellationToken cancellationToken)
        {
            while (true)
            {
                InternalPushResultRequest request;
                lock (TransportSync)
                {
                    if (PendingPushResults.Count == 0)
                    {
                        return;
                    }

                    request = PendingPushResults.Peek();
                }

                request.sessionId = sessionId;
                InternalPushResultResponse response = await PushResultAsync(request, cancellationToken);
                if (response != null && response.accepted)
                {
                    lock (TransportSync)
                    {
                        if (PendingPushResults.Count > 0 && ReferenceEquals(PendingPushResults.Peek(), request))
                        {
                            PendingPushResults.Dequeue();
                        }
                    }

                    continue;
                }

                if (response != null && string.Equals(response.message, "Unknown request", StringComparison.Ordinal))
                {
                    lock (TransportSync)
                    {
                        if (PendingPushResults.Count > 0 && ReferenceEquals(PendingPushResults.Peek(), request))
                        {
                            PendingPushResults.Dequeue();
                        }
                    }
                    continue;
                }

                if (response != null && string.Equals(response.message, "Timed out request", StringComparison.Ordinal))
                {
                    lock (TransportSync)
                    {
                        if (PendingPushResults.Count > 0 && ReferenceEquals(PendingPushResults.Peek(), request))
                        {
                            PendingPushResults.Dequeue();
                        }
                    }
                    continue;
                }

                if (response != null)
                {
                    ResetSession($"PushResult rejected: {response.message}");
                }
                return;
            }
        }

        private static async Task SendHeartbeatIfNeededAsync(string sessionId, CancellationToken cancellationToken)
        {
            if (DateTime.UtcNow < _nextHeartbeatUtc)
            {
                return;
            }

            string state = ResolveTransportHeartbeatState();
            string detail = ResolveTransportHeartbeatDetail();
            LogHeartbeatStateIfChanged(sessionId, state, detail);
            InternalHeartbeatResponse response = await HeartbeatOnceAsync(sessionId, state, detail, cancellationToken);
            _nextHeartbeatUtc = DateTime.UtcNow.AddSeconds(_heartbeatIntervalSec);

            if (response == null || !response.accepted)
            {
                ResetSession($"Heartbeat rejected: {response?.message}");
            }
        }

        private static bool HasLocalWorkInFlight()
        {
            lock (TransportSync)
            {
                return _pendingTask != null
                    || _activeTask != null
                    || _isExecuting
                    || PendingPulledTasks.Count > 0
                    || PendingPushResults.Count > 0;
            }
        }

        private static bool ShouldRetryPausedMainThreadWork()
        {
            if (!_isEditorPaused)
            {
                return false;
            }

            lock (TransportSync)
            {
                if (_pendingTask == null && _activeTask == null && !_isExecuting && PendingPulledTasks.Count == 0)
                {
                    return false;
                }
            }

            DateTime now = DateTime.UtcNow;
            if (now < _nextPausedMainThreadSignalUtc)
            {
                return false;
            }

            _nextPausedMainThreadSignalUtc = now.AddMilliseconds(PausedMainThreadRetryDelayMs);
            return true;
        }

        private static bool HasPendingMainThreadWork()
        {
            lock (TransportSync)
            {
                return _pendingTask != null || _activeTask != null || _isExecuting || PendingPulledTasks.Count > 0;
            }
        }

        /// <summary>
        /// 使用可重试的 Post 将 Unity 主线程泵唤醒，避免一次性标记卡死后永不重试。
        /// </summary>
        private static void SignalMainThreadWork()
        {
            if (!_initialized || _mainThreadContext == null)
            {
                return;
            }

            try
            {
                _mainThreadContext.Post(_ =>
                {
                    if (!_initialized)
                    {
                        return;
                    }

                    if (_isEditorPaused)
                    {
                        InternalEditorUtility.RepaintAllViews();
                        if (HasPendingMainThreadWork())
                        {
                            SchedulePausedDelayCallPump();
                        }
                    }

                    TickMainThreadLoop();
                }, null);
            }
            catch (Exception ex)
            {
                Debug.LogWarning($"[UnityGateway] Signal main thread failed: {ex.Message}");
            }
        }

        /// <summary>
        /// 使用无锁死标记的 delayCall 作为暂停态备用主线程泵，防止单次 Post 丢失后彻底停转。
        /// </summary>
        private static void SchedulePausedDelayCallPump()
        {
            if (!_initialized || !_isEditorPaused)
            {
                return;
            }

            EditorApplication.delayCall -= OnPausedDelayCallPump;
            EditorApplication.delayCall += OnPausedDelayCallPump;
        }

        private static void OnPausedDelayCallPump()
        {
            EditorApplication.delayCall -= OnPausedDelayCallPump;
            if (!_initialized || !_isEditorPaused)
            {
                return;
            }

            InternalEditorUtility.RepaintAllViews();
            TickMainThreadLoop();
            if (HasPendingMainThreadWork())
            {
                SchedulePausedDelayCallPump();
            }
        }

        private static async Task<InternalRegisterResponse> RegisterAsync(CancellationToken cancellationToken)
        {
            InternalRegisterRequest request = new InternalRegisterRequest();
            request.projectRoot = _projectRoot;
            request.unityId = _unityId;
            request.dataPath = _dataPath;
            request.unityProcessId = _unityProcessId;
            request.editorVersion = _editorVersion;
            return await PostJsonAsync<InternalRegisterRequest, InternalRegisterResponse>(RegisterPath, request, DefaultHttpTimeoutMs, cancellationToken);
        }

        /// <summary>
        /// 在 Unity 主线程采集当前 Editor 身份信息，供后台注册请求复用。
        /// </summary>
        private static void RefreshUnityIdentity()
        {
            _projectRoot = UnityGatewayPaths.UnityProjectRoot;
            _dataPath = Application.dataPath;
            _unityProcessId = System.Diagnostics.Process.GetCurrentProcess().Id;
            _editorVersion = Application.unityVersion ?? string.Empty;
            _unityId = GetOrCreateUnityId();
        }

        /// <summary>
        /// 从 Library 持久化文件读取 Unity ID，不存在或为空时生成新的 GUID。
        /// </summary>
        private static string GetOrCreateUnityId()
        {
            string unityIdPath = UnityGatewayPaths.UnityIdFilePath;
            try
            {
                if (File.Exists(unityIdPath))
                {
                    string savedUnityId = File.ReadAllText(unityIdPath).Trim();
                    if (!string.IsNullOrWhiteSpace(savedUnityId))
                    {
                        return savedUnityId;
                    }
                }

                string directory = Path.GetDirectoryName(unityIdPath);
                if (!string.IsNullOrWhiteSpace(directory))
                {
                    Directory.CreateDirectory(directory);
                }

                string newUnityId = Guid.NewGuid().ToString("D");
                File.WriteAllText(unityIdPath, newUnityId);
                return newUnityId;
            }
            catch (Exception ex)
            {
                Debug.LogWarning($"[UnityGateway] 创建 Unity ID 失败，将使用临时 ID: {ex.Message}");
                return Guid.NewGuid().ToString("D");
            }
        }

        private static async Task<InternalHeartbeatResponse> HeartbeatOnceAsync(string sessionId, string state, string detail, CancellationToken cancellationToken)
        {
            InternalHeartbeatRequest request = new InternalHeartbeatRequest();
            request.sessionId = sessionId;
            request.state = state;
            request.detail = detail;
            return await PostJsonAsync<InternalHeartbeatRequest, InternalHeartbeatResponse>(HeartbeatPath, request, DefaultHttpTimeoutMs, cancellationToken);
        }

        private static async Task<InternalUnregisterResponse> UnregisterOnceAsync(string sessionId, CancellationToken cancellationToken)
        {
            InternalUnregisterRequest request = new InternalUnregisterRequest();
            request.sessionId = sessionId;
            return await PostJsonAsync<InternalUnregisterRequest, InternalUnregisterResponse>(UnregisterPath, request, DefaultHttpTimeoutMs, cancellationToken);
        }

        /// <summary>
        /// 主动通知中心网关当前 Unity Agent 已断开，避免等待离线超时。
        /// </summary>
        private static void TryUnregisterSession(string sessionId)
        {
            if (string.IsNullOrWhiteSpace(sessionId) || _httpClient == null)
            {
                return;
            }

            try
            {
                Task<InternalUnregisterResponse> unregisterTask = Task.Run(() => UnregisterOnceAsync(sessionId, CancellationToken.None));
                unregisterTask.Wait(DefaultHttpTimeoutMs + 500);
            }
            catch (Exception ex)
            {
                Debug.LogWarning($"[UnityGateway] Unregister failed: {ex.Message}");
            }
        }

        private static async Task<InternalPullTaskResponse> PullTaskAsync(string sessionId, int maxWaitMs, CancellationToken cancellationToken)
        {
            InternalPullTaskRequest request = new InternalPullTaskRequest();
            request.sessionId = sessionId;
            request.maxWaitMs = Mathf.Clamp(maxWaitMs, 50, 5000);
            return await PostJsonAsync<InternalPullTaskRequest, InternalPullTaskResponse>(PullTaskPath, request, maxWaitMs + DefaultHttpTimeoutMs, cancellationToken);
        }

        private static async Task<InternalPushResultResponse> PushResultAsync(InternalPushResultRequest request, CancellationToken cancellationToken)
        {
            return await PostJsonAsync<InternalPushResultRequest, InternalPushResultResponse>(PushResultPath, request, DefaultHttpTimeoutMs, cancellationToken);
        }

        private static async Task<TResponse> PostJsonAsync<TRequest, TResponse>(string path, TRequest request, int timeoutMs, CancellationToken cancellationToken)
        {
            if (_httpClient == null)
            {
                throw new InvalidOperationException("HttpClient is not initialized");
            }

            string url = _gatewayBaseUrl + path;
            string requestJson = JsonConvert.SerializeObject(request);

            using (StringContent content = new StringContent(requestJson, Encoding.UTF8, "application/json"))
            using (CancellationTokenSource cts = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken))
            {
                cts.CancelAfter(Mathf.Max(500, timeoutMs));
                using (HttpResponseMessage response = await _httpClient.PostAsync(url, content, cts.Token))
                {
                    string responseJson = await response.Content.ReadAsStringAsync();

                    if (!response.IsSuccessStatusCode)
                    {
                        throw new Exception($"HTTP {(int)response.StatusCode}: {responseJson}");
                    }

                    TResponse parsed = JsonConvert.DeserializeObject<TResponse>(responseJson);
                    if (parsed == null)
                    {
                        throw new Exception($"Empty response at {path}");
                    }

                    return parsed;
                }
            }
        }

        private static string ResolveTransportHeartbeatState()
        {
            if (_activeTask != null || _isExecuting || _pendingTask != null)
            {
                return GatewayStateValues.Busy;
            }

            lock (TransportSync)
            {
                if (PendingPulledTasks.Count > 0 || PendingPushResults.Count > 0)
                {
                    return GatewayStateValues.Busy;
                }
            }

            return _agentState;
        }

        private static string GetSessionId()
        {
            lock (TransportSync)
            {
                return _sessionId;
            }
        }

        private static string ResolveTransportHeartbeatDetail()
        {
            if (_activeTask != null)
            {
                return _activeTask.detail ?? "等待 Unity 执行任务";
            }

            if (_pendingTask != null || _isExecuting)
            {
                return _stateDetail ?? "正在执行任务";
            }

            lock (TransportSync)
            {
                if (PendingPulledTasks.Count > 0)
                {
                    return "任务已拉取，等待主线程执行";
                }

                if (PendingPushResults.Count > 0)
                {
                    return "等待向网关回传执行结果";
                }
            }

            return _stateDetail;
        }

        private static string GetGatewayBaseUrl()
        {
            string fromEnv = Environment.GetEnvironmentVariable("UNITY_ROSLYN_GATEWAY_URL");
            string url = string.IsNullOrWhiteSpace(fromEnv) ? "http://127.0.0.1:19090" : fromEnv;
            return url.TrimEnd('/');
        }

        private static void SetState(string state, string detail)
        {
            string oldState = _agentState;
            string oldDetail = _stateDetail;
            _agentState = state;
            _stateDetail = detail ?? string.Empty;
            WriteStateAuditLog("set_state", oldState, _agentState, oldDetail, _stateDetail, "Local state updated");
        }

        private static void ResetSession(string reason)
        {
            Debug.LogWarning($"[UnityGateway] Reset session: {reason}");
            lock (TransportSync)
            {
                _sessionId = null;
                _lastLoggedHeartbeatState = string.Empty;
                _lastLoggedHeartbeatDetail = string.Empty;
                _nextRegisterAttemptUtc = DateTime.UtcNow.AddSeconds(RegisterRetrySeconds);
                _nextHeartbeatUtc = DateTime.UtcNow;
            }

            SetState(GatewayStateValues.Ready, "Waiting for registration");
        }

        /// <summary>
        /// 记录实际发送给中心网关的心跳状态，捕获由本地队列推导出的 Busy。
        /// </summary>
        private static void LogHeartbeatStateIfChanged(string sessionId, string state, string detail)
        {
            detail = detail ?? string.Empty;
            lock (TransportSync)
            {
                if (string.Equals(_lastLoggedHeartbeatState, state, StringComparison.Ordinal)
                    && string.Equals(_lastLoggedHeartbeatDetail, detail, StringComparison.Ordinal))
                {
                    return;
                }

                _lastLoggedHeartbeatState = state;
                _lastLoggedHeartbeatDetail = detail;
            }

            WriteStateAuditLog("heartbeat_send", string.Empty, state, string.Empty, detail, $"session={sessionId}");
        }

        /// <summary>
        /// 写入 Unity Agent 本地状态审计日志，日志失败不影响网关运行。
        /// </summary>
        private static void WriteStateAuditLog(string eventName, string oldState, string newState, string oldDetail, string newDetail, string reason)
        {
            try
            {
                string logPath = UnityGatewayPaths.UnityAgentStateLogFilePath;
                string directory = Path.GetDirectoryName(logPath);
                if (!string.IsNullOrWhiteSpace(directory))
                {
                    Directory.CreateDirectory(directory);
                }

                StringBuilder builder = new StringBuilder(512);
                builder.Append("utc=").Append(EscapeAuditLogValue(DateTime.UtcNow.ToString("O")));
                builder.Append(" event=").Append(EscapeAuditLogValue(eventName));
                builder.Append(" unity_id=").Append(EscapeAuditLogValue(_unityId));
                builder.Append(" session_id=").Append(EscapeAuditLogValue(GetSessionId()));
                builder.Append(" old_state=").Append(EscapeAuditLogValue(oldState));
                builder.Append(" new_state=").Append(EscapeAuditLogValue(newState));
                builder.Append(" old_detail=").Append(EscapeAuditLogValue(oldDetail));
                builder.Append(" new_detail=").Append(EscapeAuditLogValue(newDetail));
                builder.Append(" reason=").Append(EscapeAuditLogValue(reason));
                AppendRuntimeAuditContext(builder);

                lock (AuditLogSync)
                {
                    File.AppendAllText(logPath, builder.AppendLine().ToString(), Encoding.UTF8);
                }
            }
            catch
            {
            }
        }

        /// <summary>
        /// 追加定位 Busy 卡住问题所需的本地任务上下文。
        /// </summary>
        private static void AppendRuntimeAuditContext(StringBuilder builder)
        {
            int pulledCount;
            int pushResultCount;
            string activeRequestId = string.Empty;
            string activeStage = string.Empty;
            string pendingRequestId = string.Empty;

            lock (TransportSync)
            {
                pulledCount = PendingPulledTasks.Count;
                pushResultCount = PendingPushResults.Count;
                if (_pendingTask != null)
                {
                    pendingRequestId = _pendingTask.requestId ?? string.Empty;
                }
            }

            if (_activeTask != null)
            {
                activeRequestId = _activeTask.task != null ? _activeTask.task.requestId ?? string.Empty : string.Empty;
                activeStage = _activeTask.stage ?? string.Empty;
            }

            builder.Append(" is_executing=").Append(_isExecuting ? "true" : "false");
            builder.Append(" editor_paused=").Append(_isEditorPaused ? "true" : "false");
            builder.Append(" active_request_id=").Append(EscapeAuditLogValue(activeRequestId));
            builder.Append(" active_stage=").Append(EscapeAuditLogValue(activeStage));
            builder.Append(" pending_request_id=").Append(EscapeAuditLogValue(pendingRequestId));
            builder.Append(" pulled_count=").Append(pulledCount);
            builder.Append(" pending_push_result_count=").Append(pushResultCount);
        }

        private static string EscapeAuditLogValue(string value)
        {
            if (string.IsNullOrEmpty(value))
            {
                return string.Empty;
            }

            return value.Replace("\\", "\\\\").Replace("\r", "\\r").Replace("\n", "\\n").Replace(" ", "\\s");
        }

        private static void RecoverPersistedTask()
        {
            _activeTask = UnityGatewayCompilationCoordinator.LoadPersistedTask();
            if (_activeTask == null || _activeTask.task == null)
            {
                return;
            }

            if (string.Equals(_activeTask.stage, WaitingForAsyncExecutionStage, StringComparison.Ordinal))
            {
                _activeTask.detail = "已恢复等待中的异步执行任务";
                return;
            }

            if (!string.Equals(_activeTask.stage, UnityGatewayCompilationCoordinator.WaitingForCompilationStage, StringComparison.Ordinal))
            {
                ClearActiveTaskState();
                return;
            }

            bool includeDiagnostics = _activeTask.task.includeCompileDiagnostics;
            UnityGatewayCompilationCoordinator.RestoreRecoveredSession(includeDiagnostics, _activeTask.reloadObserved);
            _activeTask.detail = _activeTask.reloadObserved ? "已恢复等待中的编译任务" : "已恢复待执行编译任务";
        }

        private static bool ShouldHandleCompilation(GatewayTaskPayload task)
        {
            return task != null && (task.refreshAssets || task.requestScriptCompilation || task.waitForScriptCompilation);
        }

        private static void PrepareCompilationMetadata(GatewayTaskPayload task, GatewayDoCodeResult result)
        {
            int effectiveTimeoutSec = GetEffectiveCompileTimeoutSec(task, out bool usedEditorDefaultTimeout);
            result.compile.compilationRequested = task.requestScriptCompilation || task.refreshAssets || task.waitForScriptCompilation;
            result.compile.compilationCompleted = false;
            result.compile.compilationHadErrors = false;
            result.compile.usedEditorDefaultTimeout = usedEditorDefaultTimeout;
            result.compile.compileTimeoutSec = effectiveTimeoutSec;
            result.compile.compilationElapsedMs = 0;

            if (result.compile.compilationRequested)
            {
                result.compile.compilationSessionId = UnityGatewayCompilationCoordinator.BeginSession(task.includeCompileDiagnostics);
            }
        }

        private static void TriggerCompilation(GatewayTaskPayload task)
        {
            if (task == null)
            {
                return;
            }

            if (task.refreshAssets)
            {
                // 主动刷新资源，避免依赖 Unity 获得焦点。
                AssetDatabase.Refresh();
            }

            if (task.requestScriptCompilation || task.waitForScriptCompilation)
            {
                CompilationPipeline.RequestScriptCompilation();
            }
        }

        private static int GetEffectiveCompileTimeoutSec(GatewayTaskPayload task, out bool usedEditorDefaultTimeout)
        {
            int compileTimeoutSec = task != null ? task.compileTimeoutSec : 0;
            if (compileTimeoutSec > 0)
            {
                usedEditorDefaultTimeout = false;
                return Mathf.Clamp(compileTimeoutSec, 10, 600);
            }

            usedEditorDefaultTimeout = true;
            return UnityGatewayExecutionSettings.DefaultCompileTimeoutSec;
        }

        /// <summary>
        /// 获取异步 do-code 的有效超时时间。
        /// </summary>
        private static int GetEffectiveExecutionTimeoutSec(GatewayTaskPayload task)
        {
            return Mathf.Clamp(task != null ? task.timeoutSec : 30, 1, 300);
        }

        private static bool HasTaskTimedOut(GatewayPersistedTaskState taskState)
        {
            if (taskState == null || string.IsNullOrWhiteSpace(taskState.deadlineUtc))
            {
                return false;
            }

            if (!DateTime.TryParse(taskState.deadlineUtc, out DateTime deadlineUtc))
            {
                return false;
            }

            return DateTime.UtcNow > deadlineUtc.ToUniversalTime();
        }

        private static int CalculateWaitElapsedMilliseconds(GatewayPersistedTaskState taskState)
        {
            if (taskState == null || string.IsNullOrWhiteSpace(taskState.waitingStartedAtUtc))
            {
                return 0;
            }

            if (!DateTime.TryParse(taskState.waitingStartedAtUtc, out DateTime waitingStartedUtc))
            {
                return 0;
            }

            double elapsedMs = (DateTime.UtcNow - waitingStartedUtc.ToUniversalTime()).TotalMilliseconds;
            return Mathf.Max(0, (int)elapsedMs);
        }

        private static GatewayDoCodeResult BuildCompletedCompilationResult(GatewayPersistedTaskState taskState, GatewayCompilationSnapshot snapshot)
        {
            GatewayDoCodeResult result = taskState.result ?? new GatewayDoCodeResult();
            result.requestId = taskState.task.requestId;
            result.compile.compilationRequested = true;
            result.compile.compilationCompleted = snapshot != null && snapshot.completed;
            result.compile.compilationHadErrors = snapshot != null && snapshot.hadErrors;
            result.compile.compilationElapsedMs = snapshot != null && snapshot.elapsedMs > 0
                ? snapshot.elapsedMs
                : CalculateWaitElapsedMilliseconds(taskState);

            if (snapshot != null && !string.IsNullOrWhiteSpace(snapshot.sessionId))
            {
                result.compile.compilationSessionId = snapshot.sessionId;
            }

            if (snapshot != null && taskState.task.includeCompileDiagnostics)
            {
                result.compile.diagnostics.Clear();
                if (snapshot.diagnostics != null)
                {
                    for (int i = 0; i < snapshot.diagnostics.Count; i++)
                    {
                        GatewayDiagnosticEntry source = snapshot.diagnostics[i];
                        if (source == null)
                        {
                            continue;
                        }

                        GatewayDiagnosticEntry clone = new GatewayDiagnosticEntry();
                        clone.severity = source.severity;
                        clone.code = source.code;
                        clone.message = source.message;
                        clone.line = source.line;
                        clone.column = source.column;
                        result.compile.diagnostics.Add(clone);
                    }
                }
            }

            if (snapshot != null && snapshot.hadErrors)
            {
                result.success = false;
                result.state = "CompileError";
                result.error.type = "UnityCompileError";
                result.error.message = "Unity 脚本编译失败";
                result.error.stackTrace = string.Empty;
            }
            else
            {
                result.success = true;
                result.state = "Success";
                result.error.type = string.Empty;
                result.error.message = string.Empty;
                result.error.stackTrace = string.Empty;
            }

            return result;
        }

        /// <summary>
        /// 构造异步 do-code 超时结果。
        /// </summary>
        private static GatewayDoCodeResult CreateAsyncExecutionTimeoutResult(GatewayPersistedTaskState taskState)
        {
            GatewayDoCodeResult result = taskState != null && taskState.result != null
                ? taskState.result
                : new GatewayDoCodeResult();
            result.requestId = taskState != null && taskState.task != null ? taskState.task.requestId : string.Empty;
            result.success = false;
            result.state = "Timeout";
            result.error.type = "Timeout";
            result.error.message = $"等待异步代码执行超时（{GetEffectiveExecutionTimeoutSec(taskState != null ? taskState.task : null)} 秒）";
            result.error.stackTrace = string.Empty;
            ApplyAsyncExecutionElapsedTime(result, taskState);
            return result;
        }

        /// <summary>
        /// 构造异步 do-code 上下文丢失结果，通常由域重载导致。
        /// </summary>
        private static GatewayDoCodeResult CreateAsyncExecutionContextLostResult(GatewayPersistedTaskState taskState)
        {
            GatewayDoCodeResult result = taskState != null && taskState.result != null
                ? taskState.result
                : new GatewayDoCodeResult();
            result.requestId = taskState != null && taskState.task != null ? taskState.task.requestId : string.Empty;
            result.success = false;
            result.state = "RuntimeError";
            result.error.type = "ExecutionContextLost";
            result.error.message = "异步 do-code 执行上下文已丢失，通常是域重载或脚本重新编译导致";
            result.error.stackTrace = string.Empty;
            ApplyAsyncExecutionElapsedTime(result, taskState);
            return result;
        }

        /// <summary>
        /// 将异步等待耗时合并回 do-code 的总耗时统计。
        /// </summary>
        private static void ApplyAsyncExecutionElapsedTime(GatewayDoCodeResult result, GatewayPersistedTaskState taskState)
        {
            if (result == null || taskState == null)
            {
                return;
            }

            int waitElapsedMs = CalculateWaitElapsedMilliseconds(taskState);
            int baseElapsedMs = Mathf.Max(0, result.timingMs.compile + result.timingMs.execute);
            result.timingMs.total = Mathf.Max(result.timingMs.total, baseElapsedMs + waitElapsedMs);
        }

        private static void PersistActiveTask()
        {
            if (_activeTask == null)
            {
                return;
            }

            UnityGatewayCompilationCoordinator.SavePersistedTask(_activeTask);
        }

        private static void ClearActiveTaskState()
        {
            _activeTask = null;
            _activeExecutionState = null;
            UnityGatewayCompilationCoordinator.ClearPersistedTask();
            UnityGatewayCompilationCoordinator.ClearSession();
        }
    }
}
