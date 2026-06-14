using System.Collections.Generic;
using UnityEngine;

namespace ForAI.Project.Runtime.UI.Management
{
    public sealed class UnityUIRoot : IUIRoot
    {
        private readonly Transform _defaultRoot;
        private readonly Dictionary<UILayerId, Transform> _layerRoots;

        public UnityUIRoot(Transform defaultRoot)
            : this(defaultRoot, null)
        {
        }

        public UnityUIRoot(
            Transform defaultRoot,
            IReadOnlyDictionary<UILayerId, Transform> layerRoots)
        {
            _defaultRoot = defaultRoot != null
                ? defaultRoot
                : throw new System.ArgumentNullException(nameof(defaultRoot));
            _layerRoots = layerRoots != null
                ? new Dictionary<UILayerId, Transform>(layerRoots)
                : new Dictionary<UILayerId, Transform>();
        }

        public Transform GetLayerRoot(UILayerId layerId)
        {
            return _layerRoots.TryGetValue(layerId, out Transform layerRoot) && layerRoot != null
                ? layerRoot
                : _defaultRoot;
        }
    }
}
