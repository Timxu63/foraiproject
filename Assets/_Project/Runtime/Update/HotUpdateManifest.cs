using System;
using System.Collections.Generic;

namespace ForAI.Project.Runtime.Update
{
    public sealed class HotUpdateManifest
    {
        private static readonly string[] WindowsStandaloneAotMetadataKeys =
        {
            "hot_update/windows/aot/mscorlib",
            "hot_update/windows/aot/system",
            "hot_update/windows/aot/system_core"
        };

        private HotUpdateManifest(string hotUpdateAssemblyKey, IReadOnlyList<string> aotMetadataKeys)
        {
            HotUpdateAssemblyKey = hotUpdateAssemblyKey;
            AotMetadataKeys = aotMetadataKeys;
        }

        public string HotUpdateAssemblyKey { get; }

        public IReadOnlyList<string> AotMetadataKeys { get; }

        public static HotUpdateManifest Create(
            string hotUpdateAssemblyKey,
            IEnumerable<string> aotMetadataKeys)
        {
            if (string.IsNullOrWhiteSpace(hotUpdateAssemblyKey))
            {
                throw new ArgumentException(
                    "HotUpdate assembly key cannot be empty.",
                    nameof(hotUpdateAssemblyKey));
            }

            return new HotUpdateManifest(
                hotUpdateAssemblyKey,
                new List<string>(aotMetadataKeys ?? Array.Empty<string>()));
        }

        public static HotUpdateManifest CreateWindowsStandaloneDefault()
        {
            return Create(
                "hot_update/windows/for_ai_project_hot_update",
                WindowsStandaloneAotMetadataKeys);
        }
    }
}
