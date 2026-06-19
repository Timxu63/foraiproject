using System;
using System.Reflection;
using System.Threading;
using ForAI.Project.Editor.Addressables;
using UnityEditor;
using UnityEditor.PackageManager;
using UnityEditor.PackageManager.Requests;
using UnityEngine;

namespace ForAI.Project.Editor.HybridCLR
{
    public static class HybridClrIntegrationCommands
    {
        public const string PackageId =
            "https://github.com/focus-creative-games/hybridclr_unity.git#v8.12.0";

        private const string HotUpdateAssemblyName = "ForAI.Project.HotUpdate";

        [MenuItem("ForAI/HybridCLR/Install Package")]
        public static void InstallPackage()
        {
            AddRequest request = Client.Add(PackageId);
            DateTime deadline = DateTime.UtcNow.AddMinutes(5);

            while (!request.IsCompleted)
            {
                if (DateTime.UtcNow > deadline)
                {
                    throw new TimeoutException($"Timed out installing {PackageId}.");
                }

                Thread.Sleep(100);
            }

            if (request.Status == StatusCode.Failure)
            {
                throw new InvalidOperationException(
                    $"Failed to install {PackageId}: {request.Error?.message}");
            }

            AssetDatabase.Refresh();
            Debug.Log("HybridCLR package install requested: " + PackageId);
        }

        [MenuItem("ForAI/HybridCLR/Configure Windows Standalone")]
        public static void ConfigureWindowsStandalone()
        {
            EditorUserBuildSettings.SwitchActiveBuildTarget(
                BuildTargetGroup.Standalone,
                BuildTarget.StandaloneWindows64);
            PlayerSettings.SetScriptingBackend(
                BuildTargetGroup.Standalone,
                ScriptingImplementation.IL2CPP);
            if (Enum.TryParse("NET_Standard_2_1", out ApiCompatibilityLevel apiCompatibilityLevel))
            {
                PlayerSettings.SetApiCompatibilityLevel(
                    BuildTargetGroup.Standalone,
                    apiCompatibilityLevel);
            }

            ConfigureHybridClrSettings();
            AssetDatabase.SaveAssets();
        }

        [MenuItem("ForAI/HybridCLR/Install Runtime Data")]
        public static void InstallRuntimeData()
        {
            object installer = CreateHybridClrInstaller();
            bool hasInstalled = (bool)InvokeHybridClrInstanceMethod(
                installer,
                "HasInstalledHybridCLR");
            if (hasInstalled)
            {
                Debug.Log("HybridCLR runtime data is already installed.");
                return;
            }

            InvokeHybridClrInstanceMethod(installer, "InstallDefaultHybridCLR");
        }

        [MenuItem("ForAI/HybridCLR/Generate And Stage Windows Content")]
        public static void GenerateAndStageWindowsContent()
        {
            ConfigureWindowsStandalone();
            InstallRuntimeData();
            InvokeHybridClrStaticMethod(
                "HybridCLR.Editor.Commands.PrebuildCommand, HybridCLR.Editor",
                "GenerateAll");

            string hotUpdateRoot = InvokeHybridClrStringMethod(
                "HybridCLR.Editor.SettingsUtil, HybridCLR.Editor",
                "GetHotUpdateDllsOutputDirByTarget",
                BuildTarget.StandaloneWindows64);
            string aotRoot = InvokeHybridClrStringMethod(
                "HybridCLR.Editor.SettingsUtil, HybridCLR.Editor",
                "GetAssembliesPostIl2CppStripDir",
                BuildTarget.StandaloneWindows64);

            HybridClrContentStager.Stage(
                hotUpdateRoot,
                aotRoot,
                HybridClrContentStager.WindowsContentRoot);
            AddressableLocalContentPostprocessor.Sync();
            Debug.Log("HybridCLR Windows content generated and staged.");
        }

        private static void ConfigureHybridClrSettings()
        {
            Type settingsType = Type.GetType(
                "HybridCLR.Editor.Settings.HybridCLRSettings, HybridCLR.Editor");
            if (settingsType == null)
            {
                throw new InvalidOperationException("HybridCLR.Editor is not installed.");
            }

            PropertyInfo instanceProperty = settingsType.GetProperty(
                "Instance",
                BindingFlags.Public | BindingFlags.Static);
            object settings = instanceProperty?.GetValue(null);
            if (settings == null)
            {
                throw new InvalidOperationException("Unable to load HybridCLR settings.");
            }

            SetField(settings, "enable", true);
            SetField(settings, "hotUpdateAssemblies", new[] {HotUpdateAssemblyName});
            SetField(settings, "patchAOTAssemblies", new[] {"mscorlib", "System", "System.Core"});

            MethodInfo saveMethod = settingsType.GetMethod(
                "Save",
                BindingFlags.Public | BindingFlags.Static);
            saveMethod?.Invoke(null, null);
        }

        private static object CreateHybridClrInstaller()
        {
            Type installerType = Type.GetType(
                "HybridCLR.Editor.Installer.InstallerController, HybridCLR.Editor");
            if (installerType == null)
            {
                throw new InvalidOperationException("HybridCLR installer is unavailable.");
            }

            return Activator.CreateInstance(installerType);
        }

        private static void SetField(object target, string fieldName, object value)
        {
            FieldInfo field = target.GetType().GetField(
                fieldName,
                BindingFlags.Public | BindingFlags.Instance);
            if (field == null)
            {
                throw new MissingFieldException(target.GetType().FullName, fieldName);
            }

            field.SetValue(target, value);
        }

        private static void InvokeHybridClrStaticMethod(string typeName, string methodName)
        {
            Type type = Type.GetType(typeName);
            MethodInfo method = type?.GetMethod(methodName, BindingFlags.Public | BindingFlags.Static);
            if (method == null)
            {
                throw new InvalidOperationException("HybridCLR method is unavailable: " + typeName + "." + methodName);
            }

            method.Invoke(null, null);
        }

        private static object InvokeHybridClrInstanceMethod(object target, string methodName)
        {
            MethodInfo method = target.GetType().GetMethod(
                methodName,
                BindingFlags.Public | BindingFlags.Instance);
            if (method == null)
            {
                throw new InvalidOperationException(
                    "HybridCLR method is unavailable: " + target.GetType().FullName + "." + methodName);
            }

            return method.Invoke(target, null);
        }

        private static string InvokeHybridClrStringMethod(
            string typeName,
            string methodName,
            BuildTarget target)
        {
            Type type = Type.GetType(typeName);
            MethodInfo method = type?.GetMethod(
                methodName,
                BindingFlags.Public | BindingFlags.Static,
                null,
                new[] {typeof(BuildTarget)},
                null);
            if (method == null)
            {
                throw new InvalidOperationException("HybridCLR method is unavailable: " + typeName + "." + methodName);
            }

            return ((string)method.Invoke(null, new object[] {target})).Replace('\\', '/');
        }
    }
}
