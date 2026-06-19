using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEditor;

namespace ForAI.Project.Editor.HybridCLR
{
    public readonly struct HybridClrContentStageEntry
    {
        public HybridClrContentStageEntry(string sourcePath, string destinationAssetPath)
        {
            SourcePath = sourcePath;
            DestinationAssetPath = destinationAssetPath;
        }

        public string SourcePath { get; }

        public string DestinationAssetPath { get; }
    }

    public sealed class HybridClrContentStagePlan
    {
        public HybridClrContentStagePlan(IEnumerable<HybridClrContentStageEntry> entries)
        {
            Entries = entries.ToArray();
        }

        public HybridClrContentStageEntry[] Entries { get; }
    }

    public static class HybridClrContentStager
    {
        public const string WindowsContentRoot = "Assets/_Project/Content/Local/HotUpdate/Windows";
        public const string HotUpdateAssemblyName = "ForAI.Project.HotUpdate.dll";

        private static readonly string[] AotMetadataAssemblyNames =
        {
            "mscorlib.dll",
            "System.dll",
            "System.Core.dll"
        };

        public static HybridClrContentStagePlan BuildPlan(
            string hotUpdateDllRoot,
            string aotMetadataRoot,
            string destinationAssetRoot)
        {
            if (string.IsNullOrWhiteSpace(hotUpdateDllRoot))
            {
                throw new ArgumentException("Hot update dll root cannot be empty.", nameof(hotUpdateDllRoot));
            }

            if (string.IsNullOrWhiteSpace(aotMetadataRoot))
            {
                throw new ArgumentException("AOT metadata root cannot be empty.", nameof(aotMetadataRoot));
            }

            if (string.IsNullOrWhiteSpace(destinationAssetRoot))
            {
                throw new ArgumentException("Destination asset root cannot be empty.", nameof(destinationAssetRoot));
            }

            var entries = new List<HybridClrContentStageEntry>();
            string hotUpdateDll = Path.Combine(hotUpdateDllRoot, HotUpdateAssemblyName);
            if (File.Exists(hotUpdateDll))
            {
                entries.Add(new HybridClrContentStageEntry(
                    hotUpdateDll,
                    NormalizeAssetPath(destinationAssetRoot + "/" + HotUpdateAssemblyName + ".bytes")));
            }

            foreach (string aotAssemblyName in AotMetadataAssemblyNames)
            {
                string source = Path.Combine(aotMetadataRoot, aotAssemblyName);
                if (!File.Exists(source))
                {
                    continue;
                }

                entries.Add(new HybridClrContentStageEntry(
                    source,
                    NormalizeAssetPath(destinationAssetRoot + "/AOT/" + aotAssemblyName + ".bytes")));
            }

            return new HybridClrContentStagePlan(entries);
        }

        public static HybridClrContentStagePlan Stage(
            string hotUpdateDllRoot,
            string aotMetadataRoot,
            string destinationAssetRoot)
        {
            HybridClrContentStagePlan plan = BuildPlan(
                hotUpdateDllRoot,
                aotMetadataRoot,
                destinationAssetRoot);

            foreach (HybridClrContentStageEntry entry in plan.Entries)
            {
                string fullDestinationPath = Path.GetFullPath(entry.DestinationAssetPath);
                string directory = Path.GetDirectoryName(fullDestinationPath);
                if (!string.IsNullOrEmpty(directory))
                {
                    Directory.CreateDirectory(directory);
                }

                File.Copy(entry.SourcePath, fullDestinationPath, true);
            }

            AssetDatabase.Refresh();
            return plan;
        }

        private static string NormalizeAssetPath(string path)
        {
            return path.Replace('\\', '/').Trim();
        }
    }
}
