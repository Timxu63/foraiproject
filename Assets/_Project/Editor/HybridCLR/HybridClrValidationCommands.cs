using System;
using System.Collections.Generic;
using System.IO;
using System.Text;
using UnityEditor;
using UnityEditor.AddressableAssets;
using UnityEditor.AddressableAssets.Build;
using UnityEditor.AddressableAssets.Settings;
using UnityEditor.SceneManagement;
using UnityEditor.TestTools.TestRunner.Api;
using UnityEngine;
using UnityEngine.TestTools;
using UnityEngine.SceneManagement;

namespace ForAI.Project.Editor.HybridCLR
{
    public static class HybridClrValidationCommands
    {
        private const string RunId = "change-20260615-173400";
        private const string ArtifactRoot = "artifacts/ai-runs/" + RunId;
        private const string SampleScenePath = "Assets/Scenes/SampleScene.unity";
        private const string LauncherTypeName = "ForAI.Project.Runtime.Boot.GameLauncher, ForAI.Project.Runtime";

        [MenuItem("ForAI/HybridCLR/Validation/Ensure Launcher Scene Object")]
        public static void EnsureLauncherSceneObject()
        {
            Directory.CreateDirectory(ArtifactRoot);

            Type launcherType = Type.GetType(LauncherTypeName);
            if (launcherType == null)
            {
                throw new InvalidOperationException("Cannot resolve launcher type: " + LauncherTypeName);
            }

            Scene scene = EditorSceneManager.OpenScene(SampleScenePath, OpenSceneMode.Single);
            Component launcher = UnityEngine.Object.FindObjectOfType(launcherType) as Component;
            bool createdObject = false;
            bool addedComponent = false;

            if (launcher == null)
            {
                GameObject launcherObject = GameObject.Find("GameLauncher");
                if (launcherObject == null)
                {
                    launcherObject = new GameObject("GameLauncher");
                    createdObject = true;
                }

                launcher = launcherObject.GetComponent(launcherType) as Component;
                if (launcher == null)
                {
                    launcher = launcherObject.AddComponent(launcherType);
                    addedComponent = true;
                }
            }

            EditorSceneManager.MarkSceneDirty(scene);
            bool saved = EditorSceneManager.SaveScene(scene);
            string path = Path.Combine(ArtifactRoot, "launcher-scene-result.json");
            File.WriteAllText(
                path,
                "{\n"
                + $"  \"success\": {Bool(saved && launcher != null)},\n"
                + $"  \"scenePath\": \"{Escape(scene.path)}\",\n"
                + $"  \"createdObject\": {Bool(createdObject)},\n"
                + $"  \"addedComponent\": {Bool(addedComponent)},\n"
                + $"  \"launcherName\": \"{Escape(launcher != null ? launcher.gameObject.name : string.Empty)}\"\n"
                + "}\n",
                Encoding.UTF8);

            if (!saved || launcher == null)
            {
                throw new InvalidOperationException("Failed to ensure GameLauncher in " + SampleScenePath);
            }
        }

        [MenuItem("ForAI/HybridCLR/Validation/Build Addressables")]
        public static void BuildAddressables()
        {
            Directory.CreateDirectory(ArtifactRoot);

            AddressableAssetSettings.CleanPlayerContent();
            AddressableAssetSettings.BuildPlayerContent(out AddressablesPlayerBuildResult result);

            bool success = result != null && string.IsNullOrEmpty(result.Error);
            string path = Path.Combine(ArtifactRoot, "addressables-build-result.json");
            File.WriteAllText(
                path,
                "{\n"
                + $"  \"success\": {Bool(success)},\n"
                + $"  \"outputPath\": \"{Escape(result?.OutputPath)}\",\n"
                + $"  \"error\": \"{Escape(result?.Error)}\",\n"
                + $"  \"duration\": {SafeDouble(result?.Duration ?? 0d)}\n"
                + "}\n",
                Encoding.UTF8);

            if (!success)
            {
                throw new InvalidOperationException("Addressables build failed: " + result?.Error);
            }
        }

        [MenuItem("ForAI/HybridCLR/Validation/Build Windows IL2CPP")]
        public static void BuildWindowsIl2Cpp()
        {
            Directory.CreateDirectory(ArtifactRoot);
            HybridClrIntegrationCommands.ConfigureWindowsStandalone();

            string outputDirectory = Path.Combine(ArtifactRoot, "WindowsPlayer").Replace('\\', '/');
            Directory.CreateDirectory(outputDirectory);
            string outputPath = Path.Combine(outputDirectory, "ForAIHybridCLR.exe").Replace('\\', '/');

            List<string> scenes = new List<string>();
            foreach (EditorBuildSettingsScene scene in EditorBuildSettings.scenes)
            {
                if (scene.enabled && !string.IsNullOrWhiteSpace(scene.path))
                {
                    scenes.Add(scene.path);
                }
            }

            if (scenes.Count == 0)
            {
                throw new InvalidOperationException("No enabled scenes are configured for player build.");
            }

            BuildPlayerOptions options = new BuildPlayerOptions
            {
                scenes = scenes.ToArray(),
                locationPathName = outputPath,
                target = BuildTarget.StandaloneWindows64,
                targetGroup = BuildTargetGroup.Standalone,
                options = BuildOptions.None,
            };

            UnityEditor.Build.Reporting.BuildReport report = BuildPipeline.BuildPlayer(options);
            UnityEditor.Build.Reporting.BuildSummary summary = report.summary;
            bool success = summary.result == UnityEditor.Build.Reporting.BuildResult.Succeeded;
            string path = Path.Combine(ArtifactRoot, "windows-il2cpp-build-result.json");
            File.WriteAllText(
                path,
                "{\n"
                + $"  \"success\": {Bool(success)},\n"
                + $"  \"result\": \"{Escape(summary.result.ToString())}\",\n"
                + $"  \"outputPath\": \"{Escape(outputPath)}\",\n"
                + $"  \"totalErrors\": {summary.totalErrors},\n"
                + $"  \"totalWarnings\": {summary.totalWarnings},\n"
                + $"  \"totalSize\": {summary.totalSize},\n"
                + $"  \"totalTime\": \"{Escape(summary.totalTime.ToString())}\"\n"
                + "}\n",
                Encoding.UTF8);

            if (!success)
            {
                throw new InvalidOperationException(
                    $"Windows IL2CPP build failed: {summary.result}, errors={summary.totalErrors}.");
            }
        }

        [MenuItem("ForAI/HybridCLR/Validation/Run EditMode Tests")]
        public static void RunEditModeTests()
        {
            Directory.CreateDirectory(ArtifactRoot);
            string jsonPath = Path.Combine(ArtifactRoot, "editmode-test-result.json");
            string xmlPath = Path.Combine(ArtifactRoot, "editmode-test-result.xml");
            string startedPath = Path.Combine(ArtifactRoot, "editmode-test-started.txt");
            File.WriteAllText(startedPath, DateTime.UtcNow.ToString("O") + "\n", Encoding.UTF8);

            TestRunnerApi api = ScriptableObject.CreateInstance<TestRunnerApi>();
            api.RegisterCallbacks(new ArtifactTestCallbacks(jsonPath, xmlPath));
            api.Execute(new ExecutionSettings(new Filter
            {
                testMode = TestMode.EditMode,
                assemblyNames = new[] {"ForAI.Project.Tests.EditMode"},
            }));
        }

        private static string Bool(bool value)
        {
            return value ? "true" : "false";
        }

        private static string SafeDouble(double value)
        {
            return double.IsNaN(value) || double.IsInfinity(value)
                ? "0"
                : value.ToString(System.Globalization.CultureInfo.InvariantCulture);
        }

        private static string Escape(string value)
        {
            if (string.IsNullOrEmpty(value))
            {
                return string.Empty;
            }

            return value
                .Replace("\\", "\\\\")
                .Replace("\"", "\\\"")
                .Replace("\r", "\\r")
                .Replace("\n", "\\n");
        }

        private sealed class ArtifactTestCallbacks : ICallbacks
        {
            private readonly string _jsonPath;
            private readonly string _xmlPath;

            public ArtifactTestCallbacks(string jsonPath, string xmlPath)
            {
                _jsonPath = jsonPath;
                _xmlPath = xmlPath;
            }

            public void RunStarted(ITestAdaptor testsToRun)
            {
            }

            public void RunFinished(ITestResultAdaptor result)
            {
                File.WriteAllText(_xmlPath, result.ToXml().OuterXml, Encoding.UTF8);
                File.WriteAllText(
                    _jsonPath,
                    "{\n"
                    + $"  \"success\": {Bool(result.FailCount == 0)},\n"
                    + $"  \"resultState\": \"{Escape(result.ResultState)}\",\n"
                    + $"  \"passCount\": {result.PassCount},\n"
                    + $"  \"failCount\": {result.FailCount},\n"
                    + $"  \"skipCount\": {result.SkipCount},\n"
                    + $"  \"inconclusiveCount\": {result.InconclusiveCount},\n"
                    + $"  \"duration\": {SafeDouble(result.Duration)}\n"
                    + "}\n",
                    Encoding.UTF8);
            }

            public void TestStarted(ITestAdaptor test)
            {
            }

            public void TestFinished(ITestResultAdaptor result)
            {
            }
        }
    }
}
