using System;
using System.IO;
using UnityEngine;

namespace ProjectMagicEscape.Editor.RoslynGateway
{
    internal static class UnityGatewaySkillInstaller
    {
        public static GatewayProcessOperationResult InstallSkillToCodex()
        {
            return InstallSkill(UnityGatewayPaths.CodexSkillInstallDirectory, "Codex");
        }

        public static GatewayProcessOperationResult InstallSkillToClaudeCode()
        {
            return InstallSkill(UnityGatewayPaths.ClaudeSkillInstallDirectory, "Claude Code");
        }

        private static GatewayProcessOperationResult InstallSkill(string targetDirectory, string platformName)
        {
            try
            {
                string sourceDirectory = UnityGatewayPaths.SkillSourceDirectory;
                if (!Directory.Exists(sourceDirectory))
                {
                    return new GatewayProcessOperationResult
                    {
                        success = false,
                        message = $"未找到 Skill 源目录: {sourceDirectory}",
                    };
                }

                if (!UnityGatewayPaths.IsPathUnderSkillInstallProjectRoot(targetDirectory))
                {
                    return new GatewayProcessOperationResult
                    {
                        success = false,
                        message = $"目标目录不在 Skill 项目根目录内，已取消安装: {targetDirectory}",
                    };
                }

                string parentDirectory = Path.GetDirectoryName(targetDirectory);
                if (string.IsNullOrWhiteSpace(parentDirectory))
                {
                    return new GatewayProcessOperationResult
                    {
                        success = false,
                        message = $"无法确定目标父目录: {targetDirectory}",
                    };
                }

                Directory.CreateDirectory(parentDirectory);

                if (Directory.Exists(targetDirectory))
                {
                    Directory.Delete(targetDirectory, true);
                }

                CopyDirectory(sourceDirectory, targetDirectory);

                return new GatewayProcessOperationResult
                {
                    success = true,
                    message = $"已安装 Skill 到 {platformName}: {targetDirectory}",
                };
            }
            catch (Exception ex)
            {
                Debug.LogException(ex);
                return new GatewayProcessOperationResult
                {
                    success = false,
                    message = $"安装 Skill 到 {platformName} 失败: {ex.GetType().Name}: {ex.Message}",
                };
            }
        }

        private static void CopyDirectory(string sourceDirectory, string targetDirectory)
        {
            Directory.CreateDirectory(targetDirectory);

            string[] files = Directory.GetFiles(sourceDirectory);
            for (int i = 0; i < files.Length; i++)
            {
                string sourceFile = files[i];
                if (sourceFile.EndsWith(".meta", StringComparison.OrdinalIgnoreCase))
                {
                    continue;
                }

                string targetFile = Path.Combine(targetDirectory, Path.GetFileName(sourceFile));
                File.Copy(sourceFile, targetFile, true);
            }

            string[] directories = Directory.GetDirectories(sourceDirectory);
            for (int i = 0; i < directories.Length; i++)
            {
                string sourceSubdirectory = directories[i];
                string targetSubdirectory = Path.Combine(targetDirectory, Path.GetFileName(sourceSubdirectory));
                CopyDirectory(sourceSubdirectory, targetSubdirectory);
            }
        }
    }
}
