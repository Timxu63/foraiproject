using System;
using System.Collections.Generic;

namespace ProjectMagicEscape.Editor.RoslynGateway
{
    internal static class GatewayStateValues
    {
        public const string Ready = "Ready";
        public const string Busy = "Busy";
        public const string Reloading = "Reloading";
    }

    [Serializable]
    internal sealed class InternalRegisterRequest
    {
        /// <summary>
        /// Unity Agent 的显示名称。
        /// </summary>
        public string agentName = "unity-editor";

        /// <summary>
        /// 当前 Unity 工程根目录的绝对路径。
        /// </summary>
        public string projectRoot;

        /// <summary>
        /// 当前 Unity 实例的稳定身份 ID。
        /// </summary>
        public string unityId;

        /// <summary>
        /// 当前 Unity 工程 Assets 目录的绝对路径。
        /// </summary>
        public string dataPath;

        /// <summary>
        /// 当前 Unity Editor 进程 ID。
        /// </summary>
        public int unityProcessId;

        /// <summary>
        /// 当前 Unity Editor 版本号。
        /// </summary>
        public string editorVersion;
    }

    [Serializable]
    internal sealed class InternalRegisterResponse
    {
        public bool accepted;
        public string sessionId;
        public float heartbeatIntervalSec = 1f;
        public float pollIntervalSec = 0.2f;
        public string message;
    }

    [Serializable]
    internal sealed class InternalHeartbeatRequest
    {
        public string sessionId;
        public string state;
        public string detail;
    }

    [Serializable]
    internal sealed class InternalHeartbeatResponse
    {
        public bool accepted;
        public string message;
    }

    [Serializable]
    internal sealed class InternalUnregisterRequest
    {
        /// <summary>
        /// 当前 Unity Agent 的 Session ID。
        /// </summary>
        public string sessionId;
    }

    [Serializable]
    internal sealed class InternalUnregisterResponse
    {
        public bool accepted;
        public string message;
    }

    [Serializable]
    internal sealed class GatewayTaskPayload
    {
        public string requestId;
        public string code;
        public int timeoutSec;
        public bool refreshAssets;
        public bool requestScriptCompilation;
        public bool waitForScriptCompilation;
        public int compileTimeoutSec;
        public bool includeCompileDiagnostics = true;
        public string createdAtUtc;
    }

    [Serializable]
    internal sealed class InternalPullTaskRequest
    {
        public string sessionId;
        public int maxWaitMs;
    }

    [Serializable]
    internal sealed class InternalPullTaskResponse
    {
        public bool accepted;
        public bool hasTask;
        public GatewayTaskPayload task;
        public string message;
    }

    [Serializable]
    internal sealed class InternalPushResultRequest
    {
        public string sessionId;
        public string requestId;
        public GatewayDoCodeResult result;
    }

    [Serializable]
    internal sealed class InternalPushResultResponse
    {
        public bool accepted;
        public string message;
    }

    [Serializable]
    internal sealed class GatewayDoCodeResult
    {
        public string requestId;
        public bool success;
        public string state;
        public GatewayResultPayload result = new GatewayResultPayload();
        public GatewayCompilePayload compile = new GatewayCompilePayload();
        public GatewayErrorPayload error = new GatewayErrorPayload();
        public GatewayTimingPayload timingMs = new GatewayTimingPayload();
    }

    [Serializable]
    internal sealed class GatewayResultPayload
    {
        public string resultJson;
        public string resultText;
        public string resultType;
    }

    [Serializable]
    internal sealed class GatewayCompilePayload
    {
        public string usedMode = "none";
        public bool compilationRequested;
        public bool compilationCompleted;
        public bool compilationHadErrors;
        public bool usedEditorDefaultTimeout;
        public int compileTimeoutSec;
        public int compilationElapsedMs;
        public string compilationSessionId = string.Empty;
        public List<GatewayDiagnosticEntry> diagnostics = new List<GatewayDiagnosticEntry>();
    }

    [Serializable]
    internal sealed class GatewayDiagnosticEntry
    {
        public string severity;
        public string code;
        public string message;
        public int line;
        public int column;
    }

    [Serializable]
    internal sealed class GatewayErrorPayload
    {
        public string type;
        public string message;
        public string stackTrace;
    }

    [Serializable]
    internal sealed class GatewayTimingPayload
    {
        public int queue;
        public int compile;
        public int execute;
        public int total;
    }
}
