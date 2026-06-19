using System.IO;
using ForAI.Project.Editor.HybridCLR;
using NUnit.Framework;

namespace ForAI.Project.Tests.EditMode.HybridCLR
{
    public sealed class HybridClrContentStagerTests
    {
        [Test]
        public void BuildPlan_MapsHotUpdateAndAotDllsToStableContentPaths()
        {
            string root = Path.GetFullPath(Path.Combine("Temp", "ForAIHybridClrContentStagerTests"));
            string hotUpdateRoot = Path.Combine(root, "HotUpdateDlls", "StandaloneWindows64");
            string aotRoot = Path.Combine(root, "AssembliesPostIl2CppStrip", "StandaloneWindows64");
            Directory.CreateDirectory(hotUpdateRoot);
            Directory.CreateDirectory(aotRoot);
            File.WriteAllBytes(Path.Combine(hotUpdateRoot, "ForAI.Project.HotUpdate.dll"), new byte[] {1});
            File.WriteAllBytes(Path.Combine(aotRoot, "mscorlib.dll"), new byte[] {2});

            HybridClrContentStagePlan plan = HybridClrContentStager.BuildPlan(
                hotUpdateRoot,
                aotRoot,
                "Assets/_Project/Content/Local/HotUpdate/Windows");

            Assert.That(plan.Entries, Has.Length.EqualTo(2));
            Assert.That(
                plan.Entries[0].DestinationAssetPath,
                Is.EqualTo("Assets/_Project/Content/Local/HotUpdate/Windows/ForAI.Project.HotUpdate.dll.bytes"));
            Assert.That(
                plan.Entries[1].DestinationAssetPath,
                Is.EqualTo("Assets/_Project/Content/Local/HotUpdate/Windows/AOT/mscorlib.dll.bytes"));
        }
    }
}
