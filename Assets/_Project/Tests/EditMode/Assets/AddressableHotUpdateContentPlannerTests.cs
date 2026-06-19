using System.Linq;
using ForAI.Project.Editor.Addressables;
using NUnit.Framework;

namespace ForAI.Project.Tests.EditMode.Assets
{
    public sealed class AddressableHotUpdateContentPlannerTests
    {
        [Test]
        public void PlanEntries_AssignsHotUpdateBytesToHotUpdateGroup()
        {
            var assetPaths = new[]
            {
                "Assets/_Project/Content/Local/HotUpdate/Windows/ForAI.Project.HotUpdate.dll.bytes",
                "Assets/_Project/Content/Local/HotUpdate/Windows/AOT/mscorlib.dll.bytes"
            };

            AddressableContentPlanEntry[] entries = AddressableContentPlanner
                .PlanEntries(assetPaths)
                .ToArray();

            AssertEntry(
                entries,
                "Assets/_Project/Content/Local/HotUpdate/Windows/ForAI.Project.HotUpdate.dll.bytes",
                "ForAI_Local_HotUpdate",
                "hot_update/windows/for_ai_project_hot_update");
            AssertEntry(
                entries,
                "Assets/_Project/Content/Local/HotUpdate/Windows/AOT/mscorlib.dll.bytes",
                "ForAI_Local_HotUpdate",
                "hot_update/windows/aot/mscorlib");
        }

        private static void AssertEntry(
            AddressableContentPlanEntry[] entries,
            string assetPath,
            string groupName,
            string address)
        {
            AddressableContentPlanEntry entry = entries.Single(candidate => candidate.AssetPath == assetPath);
            Assert.That(entry.GroupName, Is.EqualTo(groupName));
            Assert.That(entry.Address, Is.EqualTo(address));
        }
    }
}
