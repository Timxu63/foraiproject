using System;
using UnityObject = UnityEngine.Object;

namespace ForAI.Project.Runtime.Assets
{
    public sealed class AssetHandle<T> : IAssetHandle<T>
        where T : UnityObject
    {
        private readonly Action<AssetHandle<T>> _release;

        public AssetHandle(string key, T asset, Action<AssetHandle<T>> release)
        {
            Key = string.IsNullOrWhiteSpace(key)
                ? throw new ArgumentException("Asset key cannot be empty.", nameof(key))
                : key;
            Asset = asset != null
                ? asset
                : throw new ArgumentNullException(nameof(asset));
            _release = release;
        }

        public string Key { get; }

        public T Asset { get; }

        public UnityObject UntypedAsset => Asset;

        public bool IsReleased { get; private set; }

        public void Dispose()
        {
            if (IsReleased)
            {
                return;
            }

            IsReleased = true;
            _release?.Invoke(this);
        }
    }
}
