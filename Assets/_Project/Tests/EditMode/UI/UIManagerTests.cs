using System.Threading;
using System.Threading.Tasks;
using ForAI.Project.Runtime.Assets;
using ForAI.Project.Runtime.UI.Core;
using ForAI.Project.Runtime.UI.Management;
using NUnit.Framework;
using UnityEngine;

namespace ForAI.Project.Tests.EditMode.UI
{
    public sealed class UIManagerTests
    {
        [Test]
        public void OpenAsync_LoadsPrefabFromRegistryAndCallsViewOpen()
        {
            GameObject rootObject = new GameObject("UIRoot");
            GameObject prefab = new GameObject("InventoryScreenPrefab");
            var view = prefab.AddComponent<TestView>();
            var registry = new InMemoryUIPrefabRegistry();
            registry.Register<TestView>(
                new UIPrefabDescriptor("inventory", "ui/inventory", UILayerId.Screen));
            var assetService = new FakeAssetService(prefab);
            var manager = new UIManager(assetService, registry, new UnityUIRoot(rootObject.transform));

            TestView opened = manager.OpenAsync<TestView>(
                "inventory",
                "payload",
                CancellationToken.None).GetAwaiter().GetResult();

            Assert.That(opened, Is.Not.SameAs(view));
            Assert.That(opened.OpenCount, Is.EqualTo(1));
            Assert.That(opened.LastContext.Key, Is.EqualTo("inventory"));
            Assert.That(opened.LastContext.Args, Is.EqualTo("payload"));
            Assert.That(opened.transform.parent, Is.EqualTo(rootObject.transform));

            Object.DestroyImmediate(rootObject);
            Object.DestroyImmediate(prefab);
        }

        [Test]
        public void OpenAsync_ReturnsExistingViewWhenDescriptorDoesNotAllowMultiple()
        {
            GameObject rootObject = new GameObject("UIRoot");
            GameObject prefab = new GameObject("InventoryScreenPrefab");
            prefab.AddComponent<TestView>();
            var registry = new InMemoryUIPrefabRegistry();
            registry.Register<TestView>(
                new UIPrefabDescriptor("inventory", "ui/inventory", UILayerId.Screen));
            var manager = new UIManager(
                new FakeAssetService(prefab),
                registry,
                new UnityUIRoot(rootObject.transform));

            TestView first = manager.OpenAsync<TestView>(
                "inventory",
                null,
                CancellationToken.None).GetAwaiter().GetResult();
            TestView second = manager.OpenAsync<TestView>(
                "inventory",
                null,
                CancellationToken.None).GetAwaiter().GetResult();

            Assert.That(second, Is.SameAs(first));
            Assert.That(manager.OpenViewCount, Is.EqualTo(1));

            Object.DestroyImmediate(rootObject);
            Object.DestroyImmediate(prefab);
        }

        [Test]
        public void CloseAsync_CallsViewCloseDestroysInstanceAndReleasesAssetHandle()
        {
            GameObject rootObject = new GameObject("UIRoot");
            GameObject prefab = new GameObject("InventoryScreenPrefab");
            prefab.AddComponent<TestView>();
            var registry = new InMemoryUIPrefabRegistry();
            registry.Register<TestView>(
                new UIPrefabDescriptor("inventory", "ui/inventory", UILayerId.Screen));
            var assetService = new FakeAssetService(prefab);
            var manager = new UIManager(assetService, registry, new UnityUIRoot(rootObject.transform));
            TestView opened = manager.OpenAsync<TestView>(
                "inventory",
                null,
                CancellationToken.None).GetAwaiter().GetResult();

            manager.CloseAsync(
                opened,
                UICloseReason.Requested,
                CancellationToken.None).GetAwaiter().GetResult();

            Assert.That(opened.CloseCount, Is.EqualTo(1));
            Assert.That(assetService.ReleaseCount, Is.EqualTo(1));
            Assert.That(manager.OpenViewCount, Is.EqualTo(0));

            Object.DestroyImmediate(rootObject);
            Object.DestroyImmediate(prefab);
        }

        private sealed class TestView : UIPanelBase
        {
            public int OpenCount { get; private set; }
            public int CloseCount { get; private set; }
            public UIOpenContext LastContext { get; private set; }

            protected override Task OnOpenCoreAsync(
                UIOpenContext context,
                CancellationToken cancellationToken)
            {
                OpenCount++;
                LastContext = context;
                return Task.CompletedTask;
            }

            protected override Task OnCloseCoreAsync(
                UICloseReason reason,
                CancellationToken cancellationToken)
            {
                CloseCount++;
                return Task.CompletedTask;
            }
        }

        private sealed class FakeAssetService : IAssetService
        {
            private readonly GameObject _prefab;

            public FakeAssetService(GameObject prefab)
            {
                _prefab = prefab;
            }

            public int ReleaseCount { get; private set; }

            public Task<IAssetHandle<T>> LoadAsync<T>(
                string key,
                CancellationToken cancellationToken)
                where T : Object
            {
                IAssetHandle<T> handle = new AssetHandle<T>(key, (T)(Object)_prefab, _ => ReleaseCount++);
                return Task.FromResult(handle);
            }

            public void Release(IAssetHandle handle)
            {
                handle.Dispose();
            }
        }
    }
}
