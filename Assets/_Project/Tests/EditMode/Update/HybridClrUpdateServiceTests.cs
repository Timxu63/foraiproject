using System.Threading;
using System.Threading.Tasks;
using ForAI.Project.Runtime.Assets;
using ForAI.Project.Runtime.Update;
using NUnit.Framework;
using UnityEngine;

namespace ForAI.Project.Tests.EditMode.Update
{
    public sealed class HybridClrUpdateServiceTests
    {
        [Test]
        public void LoadHotUpdateAsync_ReturnsBlockedResultWhenNoLoaderIsConfigured()
        {
            var service = new HybridClrUpdateService(new AddressablesAssetService(), null);
            var manifest = HotUpdateManifest.Create(
                "hotupdate/main.dll",
                new[] {"aot/mscorlib.dll.bytes"});

            HotUpdateLoadResult result = service.LoadHotUpdateAsync(
                manifest,
                CancellationToken.None).GetAwaiter().GetResult();

            Assert.That(result.IsSuccess, Is.False);
            Assert.That(result.ErrorKind, Is.EqualTo(HotUpdateLoadErrorKind.LoaderUnavailable));
            Assert.That(result.Message, Does.Contain("HybridCLR"));
        }

        [Test]
        public void LoadHotUpdateAsync_ReturnsAssetLoadFailedWhenAddressableKeyIsMissing()
        {
            var service = new HybridClrUpdateService(
                new MissingAssetService(),
                new NoOpHotUpdateLoader());
            var manifest = HotUpdateManifest.Create(
                "hot_update/windows/for_ai_project_hot_update",
                new[] {"hot_update/windows/aot/mscorlib"});

            HotUpdateLoadResult result = service.LoadHotUpdateAsync(
                    manifest,
                    CancellationToken.None)
                .GetAwaiter()
                .GetResult();

            Assert.That(result.IsSuccess, Is.False);
            Assert.That(result.ErrorKind, Is.EqualTo(HotUpdateLoadErrorKind.AssetLoadFailed));
            Assert.That(result.Message, Does.Contain("hot_update/windows/for_ai_project_hot_update"));
        }

        private sealed class MissingAssetService : IAssetService
        {
            public Task<IAssetHandle<T>> LoadAsync<T>(
                string key,
                CancellationToken cancellationToken)
                where T : Object
            {
                throw new AssetServiceException("Missing addressable key: " + key);
            }

            public void Release(IAssetHandle handle)
            {
            }
        }

        private sealed class NoOpHotUpdateLoader : IHotUpdateLoader
        {
            public Task<HotUpdateLoadResult> LoadAsync(
                HotUpdateManifest manifest,
                byte[] hotUpdateAssembly,
                byte[][] aotMetadataAssemblies,
                CancellationToken cancellationToken)
            {
                return Task.FromResult(HotUpdateLoadResult.Success());
            }
        }
    }
}
