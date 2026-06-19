using ForAI.Project.Runtime.Update;
using NUnit.Framework;

namespace ForAI.Project.Tests.EditMode.Update
{
    public sealed class HotUpdateManifestTests
    {
        [Test]
        public void CreateWindowsStandaloneDefault_UsesStableAddressableKeys()
        {
            HotUpdateManifest manifest = HotUpdateManifest.CreateWindowsStandaloneDefault();

            Assert.That(
                manifest.HotUpdateAssemblyKey,
                Is.EqualTo("hot_update/windows/for_ai_project_hot_update"));
            Assert.That(
                manifest.AotMetadataKeys,
                Does.Contain("hot_update/windows/aot/mscorlib"));
        }
    }
}
