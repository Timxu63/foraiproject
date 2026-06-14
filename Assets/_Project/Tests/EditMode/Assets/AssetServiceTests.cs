using System.Threading;
using System.Threading.Tasks;
using ForAI.Project.Runtime.Assets;
using NUnit.Framework;
using UnityEngine;

namespace ForAI.Project.Tests.EditMode.Assets
{
    public sealed class AssetServiceTests
    {
        [Test]
        public void AssetHandle_ReleaseMarksHandleReleasedOnlyOnce()
        {
            var asset = ScriptableObject.CreateInstance<ScriptableObject>();
            int releaseCount = 0;
            var handle = new AssetHandle<ScriptableObject>("ui/test", asset, _ => releaseCount++);

            handle.Dispose();
            handle.Dispose();

            Assert.That(handle.IsReleased, Is.True);
            Assert.That(releaseCount, Is.EqualTo(1));
            Object.DestroyImmediate(asset);
        }

        [Test]
        public void AddressablesAssetService_ReportsPackageBoundaryWhenPackageIsNotInstalled()
        {
            var service = new AddressablesAssetService();

            Assert.That(service.IsAvailable, Is.False);
            AssetServiceException exception = Assert.Throws<AssetServiceException>(() =>
            {
                _ = service.LoadAsync<GameObject>("ui/missing", CancellationToken.None);
            });
            Assert.That(exception.Message, Does.Contain("Addressables"));
        }
    }
}
