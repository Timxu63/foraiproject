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
            var service = new AddressablesAssetService(null);

            Assert.That(service.IsAvailable, Is.False);
            AssetServiceException exception = Assert.Throws<AssetServiceException>(() =>
            {
                _ = service.LoadAsync<GameObject>("ui/missing", CancellationToken.None)
                    .GetAwaiter()
                    .GetResult();
            });

            Assert.That(exception.Message, Does.Contain("Addressables"));
        }

        [Test]
        public void AddressablesAssetService_LoadAsyncReturnsHandleAndReleaseDisposesProviderHandle()
        {
            var asset = ScriptableObject.CreateInstance<ScriptableObject>();
            var provider = new FakeAddressablesProvider(asset);
            var service = new AddressablesAssetService(provider);

            IAssetHandle<ScriptableObject> handle = service
                .LoadAsync<ScriptableObject>("ui/common/test_asset", CancellationToken.None)
                .GetAwaiter()
                .GetResult();

            Assert.That(service.IsAvailable, Is.True);
            Assert.That(handle.Key, Is.EqualTo("ui/common/test_asset"));
            Assert.That(handle.Asset, Is.SameAs(asset));

            service.Release(handle);
            service.Release(handle);

            Assert.That(handle.IsReleased, Is.True);
            Assert.That(provider.ReleaseCount, Is.EqualTo(1));
            Object.DestroyImmediate(asset);
        }

        [Test]
        public void AddressablesAssetService_LoadAsyncWrapsProviderFailureWithRequestedKey()
        {
            var provider = new FakeAddressablesProvider(null)
            {
                Exception = new AssetServiceException("provider failed")
            };
            var service = new AddressablesAssetService(provider);

            AssetServiceException exception = null;
            try
            {
                _ = service.LoadAsync<GameObject>("features/inventory/missing", CancellationToken.None)
                    .GetAwaiter()
                    .GetResult();
            }
            catch (AssetServiceException caught)
            {
                exception = caught;
            }

            Assert.That(exception, Is.Not.Null);
            Assert.That(exception.Message, Does.Contain("features/inventory/missing"));
            Assert.That(exception.Message, Does.Contain("provider failed"));
        }

        private sealed class FakeAddressablesProvider : IAddressablesAssetProvider
        {
            private readonly Object _asset;

            public FakeAddressablesProvider(Object asset)
            {
                _asset = asset;
            }

            public AssetServiceException Exception { get; set; }

            public int ReleaseCount { get; private set; }

            public Task<IAddressablesAssetProviderHandle<T>> LoadAsync<T>(
                string key,
                CancellationToken cancellationToken)
                where T : Object
            {
                if (Exception != null)
                {
                    throw Exception;
                }

                return Task.FromResult<IAddressablesAssetProviderHandle<T>>(
                    new FakeAddressablesProviderHandle<T>((T)_asset, _ => ReleaseCount++));
            }
        }

        private sealed class FakeAddressablesProviderHandle<T> : IAddressablesAssetProviderHandle<T>
            where T : Object
        {
            private readonly System.Action<FakeAddressablesProviderHandle<T>> _release;

            public FakeAddressablesProviderHandle(
                T asset,
                System.Action<FakeAddressablesProviderHandle<T>> release)
            {
                Asset = asset;
                _release = release;
            }

            public T Asset { get; }

            public void Release()
            {
                _release(this);
            }
        }
    }
}
