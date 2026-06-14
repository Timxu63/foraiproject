using System;

namespace ForAI.Project.Runtime.UI.Management
{
    public sealed class UIPrefabDescriptor
    {
        public UIPrefabDescriptor(
            string key,
            string assetKey,
            UILayerId layerId,
            bool allowMultiple = false)
        {
            Key = string.IsNullOrWhiteSpace(key)
                ? throw new ArgumentException("UI key cannot be empty.", nameof(key))
                : key;
            AssetKey = string.IsNullOrWhiteSpace(assetKey)
                ? throw new ArgumentException("UI asset key cannot be empty.", nameof(assetKey))
                : assetKey;
            LayerId = layerId;
            AllowMultiple = allowMultiple;
        }

        public string Key { get; }

        public string AssetKey { get; }

        public UILayerId LayerId { get; }

        public bool AllowMultiple { get; }
    }
}
