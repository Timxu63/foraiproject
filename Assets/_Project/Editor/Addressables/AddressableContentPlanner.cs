using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;

namespace ForAI.Project.Editor.Addressables
{
    public readonly struct AddressableContentPlanEntry
    {
        public AddressableContentPlanEntry(string assetPath, string groupName, string address)
        {
            AssetPath = assetPath;
            GroupName = groupName;
            Address = address;
        }

        public string AssetPath { get; }

        public string GroupName { get; }

        public string Address { get; }
    }

    public static class AddressableContentPlanner
    {
        public const string ScanRoot = "Assets/_Project/Content/Local";
        public const string GroupPrefix = "ForAI_Local_";

        private static readonly HashSet<string> IgnoredExtensions =
            new HashSet<string>(StringComparer.OrdinalIgnoreCase)
            {
                ".asmdef",
                ".cs",
                ".meta"
            };

        private static readonly HashSet<string> IgnoredSegments =
            new HashSet<string>(StringComparer.OrdinalIgnoreCase)
            {
                "Editor",
                "HotUpdate",
                "Runtime",
                "Tests"
            };

        public static IEnumerable<AddressableContentPlanEntry> PlanEntries(IEnumerable<string> assetPaths)
        {
            if (assetPaths == null)
            {
                throw new ArgumentNullException(nameof(assetPaths));
            }

            return assetPaths
                .Select(NormalizePath)
                .Where(IsAddressableCandidate)
                .Select(CreateEntry)
                .Where(entry => !string.IsNullOrWhiteSpace(entry.GroupName))
                .OrderBy(entry => entry.GroupName, StringComparer.Ordinal)
                .ThenBy(entry => entry.Address, StringComparer.Ordinal);
        }

        private static AddressableContentPlanEntry CreateEntry(string assetPath)
        {
            string relativePath = assetPath.Substring(ScanRoot.Length + 1);
            string[] segments = relativePath.Split('/');
            string topLevel = segments[0];
            string groupName = GroupNameForSegments(segments);
            string address = BuildAddress(segments);

            if (string.Equals(topLevel, "Features", StringComparison.OrdinalIgnoreCase) &&
                segments.Length > 1)
            {
                address = "features/" + BuildAddress(segments.Skip(1).ToArray());
            }

            return new AddressableContentPlanEntry(assetPath, groupName, address);
        }

        private static string BuildAddress(string[] segments)
        {
            return string.Join(
                "/",
                segments.Select((segment, index) =>
                    NormalizeAddressSegment(segment, index == segments.Length - 1)));
        }

        private static string NormalizeAddressSegment(string segment, bool stripExtension)
        {
            string withoutExtension = stripExtension ? Path.ChangeExtension(segment, null) : segment;
            var builder = new StringBuilder(withoutExtension.Length);

            for (int index = 0; index < withoutExtension.Length; index++)
            {
                char current = withoutExtension[index];
                if (!char.IsLetterOrDigit(current))
                {
                    AppendSeparator(builder);
                    continue;
                }

                if (char.IsUpper(current) && ShouldInsertWordSeparator(withoutExtension, index, builder))
                {
                    AppendSeparator(builder);
                }

                builder.Append(char.ToLowerInvariant(current));
            }

            return builder.ToString().Trim('_');
        }

        private static bool ShouldInsertWordSeparator(
            string value,
            int index,
            StringBuilder builder)
        {
            if (index == 0 || builder.Length == 0 || builder[builder.Length - 1] == '_')
            {
                return false;
            }

            char previous = value[index - 1];
            char? next = index + 1 < value.Length ? value[index + 1] : (char?)null;
            return char.IsLower(previous) ||
                char.IsDigit(previous) ||
                (char.IsUpper(previous) && next.HasValue && char.IsLower(next.Value));
        }

        private static void AppendSeparator(StringBuilder builder)
        {
            if (builder.Length > 0 && builder[builder.Length - 1] != '_')
            {
                builder.Append('_');
            }
        }

        private static string GroupNameForSegments(string[] segments)
        {
            string topLevel = segments[0];
            if (string.Equals(topLevel, "Shared", StringComparison.OrdinalIgnoreCase))
            {
                return GroupPrefix + "Shared";
            }

            if (string.Equals(topLevel, "UI", StringComparison.OrdinalIgnoreCase))
            {
                return GroupPrefix + "UI";
            }

            if (string.Equals(topLevel, "Config", StringComparison.OrdinalIgnoreCase))
            {
                return GroupPrefix + "Config";
            }

            if (string.Equals(topLevel, "Features", StringComparison.OrdinalIgnoreCase) &&
                segments.Length > 1 &&
                !string.IsNullOrWhiteSpace(segments[1]))
            {
                return GroupPrefix + "Feature_" + segments[1];
            }

            return string.Empty;
        }

        private static bool IsAddressableCandidate(string assetPath)
        {
            if (!assetPath.StartsWith(ScanRoot + "/", StringComparison.OrdinalIgnoreCase))
            {
                return false;
            }

            string extension = Path.GetExtension(assetPath);
            if (IgnoredExtensions.Contains(extension))
            {
                return false;
            }

            string relativePath = assetPath.Substring(ScanRoot.Length + 1);
            string[] segments = relativePath.Split('/');
            return !segments.Any(segment => IgnoredSegments.Contains(segment));
        }

        private static string NormalizePath(string path)
        {
            return (path ?? string.Empty).Replace('\\', '/').Trim();
        }
    }
}
