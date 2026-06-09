using UnityEditor;

namespace ProjectMagicEscape.Editor.RoslynGateway
{
    internal static class UnityGatewayExecutionSettings
    {
        private const string TrustedModePrefKey = "ProjectMagicEscape.UnityRoslynGateway.TrustedModeEnabled";
        private const string DefaultRefreshAssetsPrefKey = "ProjectMagicEscape.UnityRoslynGateway.DefaultRefreshAssets";
        private const string DefaultRequestCompilationPrefKey = "ProjectMagicEscape.UnityRoslynGateway.DefaultRequestCompilation";
        private const string DefaultWaitForCompilationPrefKey = "ProjectMagicEscape.UnityRoslynGateway.DefaultWaitForCompilation";
        private const string DefaultCompileTimeoutPrefKey = "ProjectMagicEscape.UnityRoslynGateway.DefaultCompileTimeoutSec";
        private const string MaxCompileDiagnosticsPrefKey = "ProjectMagicEscape.UnityRoslynGateway.MaxCompileDiagnostics";
        private const string SkillInstallProjectRootPrefKey = "ProjectMagicEscape.UnityRoslynGateway.SkillInstallProjectRoot";

        public static bool TrustedModeEnabled
        {
            get => EditorPrefs.GetBool(TrustedModePrefKey, false);
            set => EditorPrefs.SetBool(TrustedModePrefKey, value);
        }

        public static bool DefaultRefreshAssets
        {
            get => EditorPrefs.GetBool(DefaultRefreshAssetsPrefKey, true);
            set => EditorPrefs.SetBool(DefaultRefreshAssetsPrefKey, value);
        }

        public static bool DefaultRequestCompilation
        {
            get => EditorPrefs.GetBool(DefaultRequestCompilationPrefKey, true);
            set => EditorPrefs.SetBool(DefaultRequestCompilationPrefKey, value);
        }

        public static bool DefaultWaitForCompilation
        {
            get => EditorPrefs.GetBool(DefaultWaitForCompilationPrefKey, true);
            set => EditorPrefs.SetBool(DefaultWaitForCompilationPrefKey, value);
        }

        public static int DefaultCompileTimeoutSec
        {
            get => ClampCompileTimeout(EditorPrefs.GetInt(DefaultCompileTimeoutPrefKey, 180));
            set => EditorPrefs.SetInt(DefaultCompileTimeoutPrefKey, ClampCompileTimeout(value));
        }

        public static int MaxCompileDiagnostics
        {
            get => ClampDiagnosticCount(EditorPrefs.GetInt(MaxCompileDiagnosticsPrefKey, 200));
            set => EditorPrefs.SetInt(MaxCompileDiagnosticsPrefKey, ClampDiagnosticCount(value));
        }

        /// <summary>
        /// Skill 安装使用的项目根目录，默认回退到当前 Unity 工程根目录。
        /// </summary>
        public static string SkillInstallProjectRoot
        {
            get
            {
                string savedPath = EditorPrefs.GetString(SkillInstallProjectRootPrefKey, string.Empty);
                return string.IsNullOrWhiteSpace(savedPath)
                    ? UnityGatewayPaths.UnityProjectRoot
                    : savedPath;
            }
            set
            {
                if (string.IsNullOrWhiteSpace(value))
                {
                    EditorPrefs.DeleteKey(SkillInstallProjectRootPrefKey);
                    return;
                }

                EditorPrefs.SetString(SkillInstallProjectRootPrefKey, value);
            }
        }

        public static string SecurityModeLabel
        {
            get
            {
                return TrustedModeEnabled
                    ? "Trusted (EnsureLoad)"
                    : "Restricted (UseSettings)";
            }
        }

        private static int ClampCompileTimeout(int value)
        {
            if (value < 10)
            {
                return 10;
            }

            if (value > 600)
            {
                return 600;
            }

            return value;
        }

        private static int ClampDiagnosticCount(int value)
        {
            if (value < 1)
            {
                return 1;
            }

            if (value > 1000)
            {
                return 1000;
            }

            return value;
        }
    }
}
