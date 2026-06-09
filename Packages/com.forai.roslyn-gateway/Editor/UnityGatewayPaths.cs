using System;
using System.IO;
using System.Reflection;
using UnityEngine;

namespace ProjectMagicEscape.Editor.RoslynGateway
{
    internal static class UnityGatewayPaths
    {
        private const string PackageProjectRelativePath = "Packages/com.forai.roslyn-gateway";
        private const string GatewayCliPackageRelativePath = PackageProjectRelativePath + "/Python~/ai_gateway_client.py";

        public static string UnityProjectRoot => Path.GetFullPath(Path.Combine(Application.dataPath, ".."));

        public static string RepositoryRoot => UnityProjectRoot;

        public static string RoslynGatewayRoot => ResolvePackageRoot();

        public static string GatewayToolDirectory => Path.GetFullPath(Path.Combine(RoslynGatewayRoot, "Python~"));

        public static string SkillSourceDirectory => Path.GetFullPath(Path.Combine(RoslynGatewayRoot, "Documentation~", "skill", "unity-roslyn-gateway"));

        /// <summary>
        /// Unity Roslyn Gateway 在 Library 下保存本机运行状态数据的目录。
        /// </summary>
        public static string GatewayLibraryDirectory => Path.GetFullPath(Path.Combine(UnityProjectRoot, "Library", "UnityRoslynGateway"));

        /// <summary>
        /// 当前 Unity 实例稳定身份 ID 的持久化文件路径。
        /// </summary>
        public static string UnityIdFilePath => Path.GetFullPath(Path.Combine(GatewayLibraryDirectory, "unity_id.txt"));

        /// <summary>
        /// Unity Agent 本地状态审计日志路径。
        /// </summary>
        public static string UnityAgentStateLogFilePath => Path.GetFullPath(Path.Combine(GatewayLibraryDirectory, "unity_agent_state.log"));

        /// <summary>
        /// Skill 安装使用的项目根目录，允许在控制面板中手动覆盖。
        /// </summary>
        public static string SkillInstallProjectRoot => Path.GetFullPath(UnityGatewayExecutionSettings.SkillInstallProjectRoot);

        public static string CodexSkillInstallDirectory => Path.GetFullPath(Path.Combine(SkillInstallProjectRoot, ".codex", "skills", "unity-roslyn-gateway"));

        public static string ClaudeSkillInstallDirectory => Path.GetFullPath(Path.Combine(SkillInstallProjectRoot, ".claude", "skills", "unity-roslyn-gateway"));

        public static string GatewayCliProjectRelativePath => GatewayCliPackageRelativePath;

        /// <summary>
        /// 判断路径是否位于当前 Skill 安装项目根目录内，避免误删到其他位置。
        /// </summary>
        public static bool IsPathUnderSkillInstallProjectRoot(string path)
        {
            if (string.IsNullOrWhiteSpace(path))
            {
                return false;
            }

            string fullPath = AppendDirectorySeparator(Path.GetFullPath(path));
            string projectRoot = AppendDirectorySeparator(SkillInstallProjectRoot);
            return fullPath.StartsWith(projectRoot, StringComparison.OrdinalIgnoreCase);
        }

        private static string ResolvePackageRoot()
        {
            string packageRoot = Path.GetFullPath(Path.Combine(UnityProjectRoot, PackageProjectRelativePath));
            if (Directory.Exists(packageRoot))
            {
                return packageRoot;
            }

            string assemblyLocation = typeof(UnityGatewayPaths).Assembly.Location;
            if (!string.IsNullOrWhiteSpace(assemblyLocation))
            {
                DirectoryInfo directory = Directory.GetParent(assemblyLocation);
                while (directory != null)
                {
                    string candidate = Path.Combine(directory.FullName, "package.json");
                    if (File.Exists(candidate))
                    {
                        return directory.FullName;
                    }

                    directory = directory.Parent;
                }
            }

            string codeBase = Assembly.GetExecutingAssembly().CodeBase;
            if (!string.IsNullOrWhiteSpace(codeBase))
            {
                try
                {
                    string localPath = new Uri(codeBase).LocalPath;
                    DirectoryInfo directory = Directory.GetParent(localPath);
                    while (directory != null)
                    {
                        string candidate = Path.Combine(directory.FullName, "package.json");
                        if (File.Exists(candidate))
                        {
                            return directory.FullName;
                        }

                        directory = directory.Parent;
                    }
                }
                catch
                {
                }
            }

            return packageRoot;
        }

        private static string AppendDirectorySeparator(string path)
        {
            if (string.IsNullOrEmpty(path))
            {
                return string.Empty;
            }

            return path.EndsWith(Path.DirectorySeparatorChar.ToString(), StringComparison.Ordinal)
                ? path
                : path + Path.DirectorySeparatorChar;
        }
    }
}
