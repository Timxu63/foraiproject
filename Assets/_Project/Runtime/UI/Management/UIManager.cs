using System;
using System.Collections.Generic;
using System.Threading;
using System.Threading.Tasks;
using ForAI.Project.Runtime.Assets;
using ForAI.Project.Runtime.UI.Core;
using UnityEngine;

namespace ForAI.Project.Runtime.UI.Management
{
    public sealed class UIManager
    {
        private readonly IAssetService _assetService;
        private readonly IUIPrefabRegistry _prefabRegistry;
        private readonly IUIRoot _root;
        private readonly Dictionary<IUIView, OpenViewRecord> _recordsByView =
            new Dictionary<IUIView, OpenViewRecord>();
        private readonly Dictionary<string, IUIView> _singletonsByKey =
            new Dictionary<string, IUIView>();

        public UIManager(
            IAssetService assetService,
            IUIPrefabRegistry prefabRegistry,
            IUIRoot root)
        {
            _assetService = assetService ?? throw new ArgumentNullException(nameof(assetService));
            _prefabRegistry = prefabRegistry ?? throw new ArgumentNullException(nameof(prefabRegistry));
            _root = root ?? throw new ArgumentNullException(nameof(root));
        }

        public int OpenViewCount => _recordsByView.Count;

        public async Task<TView> OpenAsync<TView>(
            string key,
            object args,
            CancellationToken cancellationToken)
            where TView : Component, IUIView
        {
            UIPrefabDescriptor descriptor = _prefabRegistry.GetDescriptor<TView>(key);
            string singletonKey = BuildSingletonKey(typeof(TView), descriptor.Key);

            if (!descriptor.AllowMultiple &&
                _singletonsByKey.TryGetValue(singletonKey, out IUIView existing))
            {
                return (TView)existing;
            }

            IAssetHandle<GameObject> handle = await _assetService.LoadAsync<GameObject>(
                descriptor.AssetKey,
                cancellationToken);
            GameObject instance = UnityEngine.Object.Instantiate(
                handle.Asset,
                _root.GetLayerRoot(descriptor.LayerId),
                false);
            var view = instance.GetComponent<TView>();

            if (view == null)
            {
                _assetService.Release(handle);
                UnityEngine.Object.DestroyImmediate(instance);
                throw new UIManagerException(
                    $"Loaded UI prefab '{descriptor.AssetKey}' does not contain {typeof(TView).Name}.");
            }

            await view.OpenAsync(new UIOpenContext(descriptor.Key, args), cancellationToken);
            var record = new OpenViewRecord(descriptor, instance, handle, singletonKey);
            _recordsByView[view] = record;

            if (!descriptor.AllowMultiple)
            {
                _singletonsByKey[singletonKey] = view;
            }

            return view;
        }

        public async Task CloseAsync(
            IUIView view,
            UICloseReason reason,
            CancellationToken cancellationToken)
        {
            if (view == null || !_recordsByView.TryGetValue(view, out OpenViewRecord record))
            {
                return;
            }

            await view.CloseAsync(reason, cancellationToken);
            _recordsByView.Remove(view);
            _singletonsByKey.Remove(record.SingletonKey);
            _assetService.Release(record.AssetHandle);
            UnityEngine.Object.DestroyImmediate(record.Instance);
        }

        private static string BuildSingletonKey(Type viewType, string key)
        {
            return $"{viewType.FullName}:{key}";
        }

        private sealed class OpenViewRecord
        {
            public OpenViewRecord(
                UIPrefabDescriptor descriptor,
                GameObject instance,
                IAssetHandle assetHandle,
                string singletonKey)
            {
                Descriptor = descriptor;
                Instance = instance;
                AssetHandle = assetHandle;
                SingletonKey = singletonKey;
            }

            public UIPrefabDescriptor Descriptor { get; }

            public GameObject Instance { get; }

            public IAssetHandle AssetHandle { get; }

            public string SingletonKey { get; }
        }
    }
}
