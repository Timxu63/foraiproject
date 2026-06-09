using System;
using System.Collections.Generic;
using System.IO;
using System.Text;
using Newtonsoft.Json;
using UnityEditor;
using UnityEditor.Compilation;
using UnityEngine;

namespace ProjectMagicEscape.Editor.RoslynGateway
{
    [Serializable]
    internal sealed class GatewayCompilationSnapshot
    {
        public string sessionId = string.Empty;
        public bool includeDiagnostics = true;
        public bool started;
        public bool completed;
        public bool hadErrors;
        public bool reloadObserved;
        public string detail = string.Empty;
        public string startedAtUtc = string.Empty;
        public string finishedAtUtc = string.Empty;
        public int elapsedMs;
        public List<GatewayDiagnosticEntry> diagnostics = new List<GatewayDiagnosticEntry>();
    }

    [Serializable]
    internal sealed class GatewayPersistedTaskState
    {
        public GatewayTaskPayload task = new GatewayTaskPayload();
        public GatewayDoCodeResult result = new GatewayDoCodeResult();
        public string stage = string.Empty;
        public string waitingStartedAtUtc = string.Empty;
        public string deadlineUtc = string.Empty;
        public string detail = string.Empty;
        public bool reloadObserved;
    }

    internal static class UnityGatewayCompilationCoordinator
    {
        public const string WaitingForCompilationStage = "WaitingForCompilation";
        public const string PushingResultStage = "PushingResult";

        private const string StorageDirectoryName = "UnityRoslynGateway";
        private const string ActiveTaskFileName = "active_task.json";

        private static readonly UTF8Encoding Utf8Encoding = new UTF8Encoding(false);

        private static bool _initialized;
        private static GatewayCompilationSnapshot _snapshot;

        public static void Startup()
        {
            if (_initialized)
            {
                return;
            }

            CompilationPipeline.compilationStarted += OnCompilationStarted;
            CompilationPipeline.assemblyCompilationFinished += OnAssemblyCompilationFinished;
            CompilationPipeline.compilationFinished += OnCompilationFinished;
            _initialized = true;
        }

        public static void Shutdown()
        {
            if (!_initialized)
            {
                return;
            }

            CompilationPipeline.compilationStarted -= OnCompilationStarted;
            CompilationPipeline.assemblyCompilationFinished -= OnAssemblyCompilationFinished;
            CompilationPipeline.compilationFinished -= OnCompilationFinished;
            _initialized = false;
        }

        public static string BeginSession(bool includeDiagnostics)
        {
            Startup();

            GatewayCompilationSnapshot snapshot = new GatewayCompilationSnapshot();
            snapshot.sessionId = Guid.NewGuid().ToString("N");
            snapshot.includeDiagnostics = includeDiagnostics;
            snapshot.started = EditorApplication.isCompiling;
            snapshot.detail = EditorApplication.isCompiling ? "Unity 正在编译" : "等待 Unity 开始编译";
            snapshot.startedAtUtc = DateTime.UtcNow.ToString("O");

            _snapshot = snapshot;
            return snapshot.sessionId;
        }

        public static GatewayCompilationSnapshot GetSnapshot()
        {
            return CloneSnapshot(_snapshot);
        }

        public static void MarkReloadObserved()
        {
            if (_snapshot == null)
            {
                return;
            }

            _snapshot.reloadObserved = true;
            _snapshot.detail = "Unity 正在域重载";
        }

        public static void RestoreRecoveredSession(bool includeDiagnostics, bool reloadObserved)
        {
            Startup();

            if (_snapshot == null)
            {
                _snapshot = new GatewayCompilationSnapshot();
                _snapshot.sessionId = Guid.NewGuid().ToString("N");
                _snapshot.startedAtUtc = DateTime.UtcNow.ToString("O");
            }

            _snapshot.includeDiagnostics = includeDiagnostics;
            _snapshot.reloadObserved = reloadObserved;
            _snapshot.started = _snapshot.started || EditorApplication.isCompiling || reloadObserved;
            _snapshot.detail = EditorApplication.isCompiling
                ? "Unity 正在恢复编译状态"
                : reloadObserved
                    ? "Unity 已从域重载恢复"
                    : "等待 Unity 开始编译";
        }

        public static void ClearSession()
        {
            _snapshot = null;
        }

        public static GatewayPersistedTaskState LoadPersistedTask()
        {
            string filePath = GetActiveTaskFilePath();
            if (!File.Exists(filePath))
            {
                return null;
            }

            try
            {
                string json = File.ReadAllText(filePath, Utf8Encoding);
                if (string.IsNullOrWhiteSpace(json))
                {
                    return null;
                }

                return JsonConvert.DeserializeObject<GatewayPersistedTaskState>(json);
            }
            catch (Exception ex)
            {
                Debug.LogWarning($"[UnityGateway] 读取持久化任务失败: {ex.Message}");
                return null;
            }
        }

        public static void SavePersistedTask(GatewayPersistedTaskState state)
        {
            if (state == null)
            {
                return;
            }

            try
            {
                string directory = GetStorageDirectoryPath();
                Directory.CreateDirectory(directory);
                string filePath = GetActiveTaskFilePath();
                string json = JsonConvert.SerializeObject(state, Formatting.Indented);
                File.WriteAllText(filePath, json, Utf8Encoding);
            }
            catch (Exception ex)
            {
                Debug.LogWarning($"[UnityGateway] 保存持久化任务失败: {ex.Message}");
            }
        }

        public static void ClearPersistedTask()
        {
            try
            {
                string filePath = GetActiveTaskFilePath();
                if (File.Exists(filePath))
                {
                    File.Delete(filePath);
                }
            }
            catch (Exception ex)
            {
                Debug.LogWarning($"[UnityGateway] 清理持久化任务失败: {ex.Message}");
            }
        }

        private static void OnCompilationStarted(object _)
        {
            if (_snapshot == null)
            {
                return;
            }

            _snapshot.started = true;
            _snapshot.detail = "Unity 正在编译脚本";
            if (string.IsNullOrWhiteSpace(_snapshot.startedAtUtc))
            {
                _snapshot.startedAtUtc = DateTime.UtcNow.ToString("O");
            }
        }

        private static void OnAssemblyCompilationFinished(string assemblyPath, CompilerMessage[] messages)
        {
            if (_snapshot == null || !_snapshot.includeDiagnostics || messages == null)
            {
                return;
            }

            int maxDiagnostics = Mathf.Max(1, UnityGatewayExecutionSettings.MaxCompileDiagnostics);
            foreach (CompilerMessage message in messages)
            {
                if (message.type != CompilerMessageType.Error && message.type != CompilerMessageType.Warning)
                {
                    continue;
                }

                if (_snapshot.diagnostics.Count >= maxDiagnostics)
                {
                    break;
                }

                GatewayDiagnosticEntry entry = new GatewayDiagnosticEntry();
                entry.severity = message.type == CompilerMessageType.Error ? "Error" : "Warning";
                entry.code = string.Empty;
                entry.message = string.IsNullOrWhiteSpace(message.file)
                    ? message.message ?? string.Empty
                    : $"{message.file}({message.line},{message.column}): {message.message}";
                entry.line = Mathf.Max(0, message.line);
                entry.column = Mathf.Max(0, message.column);
                _snapshot.diagnostics.Add(entry);
            }
        }

        private static void OnCompilationFinished(object _)
        {
            if (_snapshot == null)
            {
                return;
            }

            _snapshot.started = true;
            _snapshot.completed = true;
            _snapshot.hadErrors = EditorUtility.scriptCompilationFailed || HasErrorDiagnostic(_snapshot.diagnostics);
            _snapshot.finishedAtUtc = DateTime.UtcNow.ToString("O");
            _snapshot.elapsedMs = CalculateElapsedMilliseconds(_snapshot.startedAtUtc, _snapshot.finishedAtUtc);
            _snapshot.detail = _snapshot.hadErrors ? "Unity 编译完成，存在错误" : "Unity 编译完成";
        }

        private static bool HasErrorDiagnostic(List<GatewayDiagnosticEntry> diagnostics)
        {
            if (diagnostics == null)
            {
                return false;
            }

            for (int i = 0; i < diagnostics.Count; i++)
            {
                GatewayDiagnosticEntry entry = diagnostics[i];
                if (entry != null && string.Equals(entry.severity, "Error", StringComparison.OrdinalIgnoreCase))
                {
                    return true;
                }
            }

            return false;
        }

        private static int CalculateElapsedMilliseconds(string startedAtUtc, string finishedAtUtc)
        {
            if (!DateTime.TryParse(startedAtUtc, out DateTime startedUtc))
            {
                return 0;
            }

            if (!DateTime.TryParse(finishedAtUtc, out DateTime finishedUtc))
            {
                finishedUtc = DateTime.UtcNow;
            }

            double elapsedMs = (finishedUtc.ToUniversalTime() - startedUtc.ToUniversalTime()).TotalMilliseconds;
            return Mathf.Max(0, (int)elapsedMs);
        }

        private static GatewayCompilationSnapshot CloneSnapshot(GatewayCompilationSnapshot snapshot)
        {
            if (snapshot == null)
            {
                return null;
            }

            GatewayCompilationSnapshot clone = new GatewayCompilationSnapshot();
            clone.sessionId = snapshot.sessionId;
            clone.includeDiagnostics = snapshot.includeDiagnostics;
            clone.started = snapshot.started;
            clone.completed = snapshot.completed;
            clone.hadErrors = snapshot.hadErrors;
            clone.reloadObserved = snapshot.reloadObserved;
            clone.detail = snapshot.detail;
            clone.startedAtUtc = snapshot.startedAtUtc;
            clone.finishedAtUtc = snapshot.finishedAtUtc;
            clone.elapsedMs = snapshot.elapsedMs;

            if (snapshot.diagnostics != null)
            {
                for (int i = 0; i < snapshot.diagnostics.Count; i++)
                {
                    GatewayDiagnosticEntry entry = snapshot.diagnostics[i];
                    if (entry == null)
                    {
                        continue;
                    }

                    GatewayDiagnosticEntry entryClone = new GatewayDiagnosticEntry();
                    entryClone.severity = entry.severity;
                    entryClone.code = entry.code;
                    entryClone.message = entry.message;
                    entryClone.line = entry.line;
                    entryClone.column = entry.column;
                    clone.diagnostics.Add(entryClone);
                }
            }

            return clone;
        }

        private static string GetStorageDirectoryPath()
        {
            string projectRoot = Path.GetFullPath(Path.Combine(Application.dataPath, ".."));
            return Path.Combine(projectRoot, "Library", StorageDirectoryName);
        }

        private static string GetActiveTaskFilePath()
        {
            return Path.Combine(GetStorageDirectoryPath(), ActiveTaskFileName);
        }
    }
}
