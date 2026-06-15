using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using UnityEditor;
using UnityEditor.AddressableAssets;
using UnityEditor.AddressableAssets.Settings;
using UnityEditor.AddressableAssets.Settings.GroupSchemas;
using UnityEngine;

namespace ForAI.Project.Editor.Addressables
{
    public static class AddressableLocalContentPostprocessor
    {
        private static readonly string[] RequiredFolders =
        {
            AddressableContentPlanner.ScanRoot + "/Shared",
            AddressableContentPlanner.ScanRoot + "/UI",
            AddressableContentPlanner.ScanRoot + "/Config",
            AddressableContentPlanner.ScanRoot + "/Features"
        };

        private static readonly string[] RequiredBaseGroups =
        {
            AddressableContentPlanner.GroupPrefix + "Shared",
            AddressableContentPlanner.GroupPrefix + "UI",
            AddressableContentPlanner.GroupPrefix + "Config"
        };

        [MenuItem("ForAI/Addressables/Dry Run Local Content Sync")]
        public static void DryRunLocalContent()
        {
            Debug.Log(BuildDryRunReport());
        }

        [MenuItem("ForAI/Addressables/Sync Local Content")]
        public static void SyncLocalContent()
        {
            SyncResult result = Sync();
            Debug.Log(result.ToLogString());
        }

        public static SyncResult Sync()
        {
            EnsureContentFolders();
            AssetDatabase.Refresh();

            AddressableAssetSettings settings = AddressableAssetSettingsDefaultObject.GetSettings(true);
            if (settings == null)
            {
                throw new InvalidOperationException("Unable to create or load Addressables settings.");
            }

            AddressableContentPlanEntry[] plannedEntries = PlanCurrentEntries().ToArray();
            string[] groupNames = RequiredBaseGroups
                .Concat(plannedEntries.Select(entry => entry.GroupName))
                .Distinct(StringComparer.Ordinal)
                .OrderBy(groupName => groupName, StringComparer.Ordinal)
                .ToArray();

            var groups = new Dictionary<string, AddressableAssetGroup>(StringComparer.Ordinal);
            int createdGroupCount = 0;
            foreach (string groupName in groupNames)
            {
                AddressableAssetGroup group = EnsureGroup(settings, groupName, out bool createdGroup);
                groups[groupName] = group;
                if (createdGroup)
                {
                    createdGroupCount++;
                }
            }

            int updatedEntryCount = 0;
            foreach (AddressableContentPlanEntry plannedEntry in plannedEntries)
            {
                string guid = AssetDatabase.AssetPathToGUID(plannedEntry.AssetPath);
                if (string.IsNullOrEmpty(guid))
                {
                    continue;
                }

                AddressableAssetGroup targetGroup = groups[plannedEntry.GroupName];
                AddressableAssetEntry addressableEntry = settings.CreateOrMoveEntry(
                    guid,
                    targetGroup,
                    false,
                    false);

                if (addressableEntry == null)
                {
                    continue;
                }

                if (!string.Equals(addressableEntry.address, plannedEntry.Address, StringComparison.Ordinal))
                {
                    addressableEntry.address = plannedEntry.Address;
                    updatedEntryCount++;
                }
            }

            settings.SetDirty(
                AddressableAssetSettings.ModificationEvent.BatchModification,
                plannedEntries.Select(entry => entry.AssetPath).ToArray(),
                true,
                true);
            EditorUtility.SetDirty(settings);
            AssetDatabase.SaveAssets();

            return new SyncResult(
                RequiredFolders,
                groupNames,
                plannedEntries,
                createdGroupCount,
                updatedEntryCount);
        }

        public static string BuildDryRunReport()
        {
            AddressableContentPlanEntry[] plannedEntries = PlanCurrentEntries().ToArray();
            string[] groupNames = RequiredBaseGroups
                .Concat(plannedEntries.Select(entry => entry.GroupName))
                .Distinct(StringComparer.Ordinal)
                .OrderBy(groupName => groupName, StringComparer.Ordinal)
                .ToArray();

            return new SyncResult(
                RequiredFolders,
                groupNames,
                plannedEntries,
                0,
                0).ToLogString();
        }

        private static IEnumerable<AddressableContentPlanEntry> PlanCurrentEntries()
        {
            if (!AssetDatabase.IsValidFolder(AddressableContentPlanner.ScanRoot))
            {
                return Enumerable.Empty<AddressableContentPlanEntry>();
            }

            string[] assetPaths = AssetDatabase
                .FindAssets(string.Empty, new[] { AddressableContentPlanner.ScanRoot })
                .Select(AssetDatabase.GUIDToAssetPath)
                .Where(path => !AssetDatabase.IsValidFolder(path))
                .ToArray();

            return AddressableContentPlanner.PlanEntries(assetPaths);
        }

        private static void EnsureContentFolders()
        {
            EnsureFolder("Assets/_Project", "Content");
            EnsureFolder("Assets/_Project/Content", "Local");
            EnsureFolder(AddressableContentPlanner.ScanRoot, "Shared");
            EnsureFolder(AddressableContentPlanner.ScanRoot, "UI");
            EnsureFolder(AddressableContentPlanner.ScanRoot, "Config");
            EnsureFolder(AddressableContentPlanner.ScanRoot, "Features");
        }

        private static void EnsureFolder(string parent, string child)
        {
            string path = parent + "/" + child;
            if (AssetDatabase.IsValidFolder(path))
            {
                return;
            }

            AssetDatabase.CreateFolder(parent, child);
        }

        private static AddressableAssetGroup EnsureGroup(
            AddressableAssetSettings settings,
            string groupName,
            out bool created)
        {
            AddressableAssetGroup group = settings.FindGroup(groupName);
            created = group == null;
            if (group == null)
            {
                group = settings.CreateGroup(
                    groupName,
                    false,
                    false,
                    false,
                    null,
                    typeof(ContentUpdateGroupSchema),
                    typeof(BundledAssetGroupSchema));
            }

            ConfigureLocalGroup(settings, group);
            return group;
        }

        private static void ConfigureLocalGroup(
            AddressableAssetSettings settings,
            AddressableAssetGroup group)
        {
            BundledAssetGroupSchema bundledSchema =
                group.GetSchema<BundledAssetGroupSchema>() ??
                group.AddSchema<BundledAssetGroupSchema>();
            bundledSchema.BuildPath.SetVariableByName(settings, AddressableAssetSettings.kLocalBuildPath);
            bundledSchema.LoadPath.SetVariableByName(settings, AddressableAssetSettings.kLocalLoadPath);
            bundledSchema.BundleMode = BundledAssetGroupSchema.BundlePackingMode.PackTogether;

            ContentUpdateGroupSchema contentUpdateSchema =
                group.GetSchema<ContentUpdateGroupSchema>() ??
                group.AddSchema<ContentUpdateGroupSchema>();
            contentUpdateSchema.StaticContent = false;

            group.SetDirty(
                AddressableAssetSettings.ModificationEvent.GroupSchemaModified,
                group,
                false,
                true);
        }
    }

    public sealed class SyncResult
    {
        public SyncResult(
            IEnumerable<string> folders,
            IEnumerable<string> groups,
            IEnumerable<AddressableContentPlanEntry> entries,
            int createdGroupCount,
            int updatedEntryCount)
        {
            Folders = folders.ToArray();
            Groups = groups.ToArray();
            Entries = entries.ToArray();
            CreatedGroupCount = createdGroupCount;
            UpdatedEntryCount = updatedEntryCount;
        }

        public string[] Folders { get; }

        public string[] Groups { get; }

        public AddressableContentPlanEntry[] Entries { get; }

        public int CreatedGroupCount { get; }

        public int UpdatedEntryCount { get; }

        public string ToLogString()
        {
            var builder = new StringBuilder();
            builder.AppendLine("ForAI Addressables local content sync preview/result");
            builder.AppendLine("Folders:");
            foreach (string folder in Folders)
            {
                builder.AppendLine("- " + folder);
            }

            builder.AppendLine("Groups:");
            foreach (string group in Groups)
            {
                builder.AppendLine("- " + group);
            }

            builder.AppendLine("Entries:");
            foreach (AddressableContentPlanEntry entry in Entries)
            {
                builder.AppendLine("- " + entry.AssetPath + " => " + entry.GroupName + " :: " + entry.Address);
            }

            builder.AppendLine("CreatedGroups: " + CreatedGroupCount);
            builder.AppendLine("UpdatedEntries: " + UpdatedEntryCount);
            return builder.ToString();
        }
    }
}
