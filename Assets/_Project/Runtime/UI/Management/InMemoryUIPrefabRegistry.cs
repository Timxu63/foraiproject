using System;
using System.Collections.Generic;
using ForAI.Project.Runtime.UI.Core;

namespace ForAI.Project.Runtime.UI.Management
{
    public sealed class InMemoryUIPrefabRegistry : IUIPrefabRegistry
    {
        private readonly Dictionary<string, UIPrefabDescriptor> _descriptors =
            new Dictionary<string, UIPrefabDescriptor>();

        public void Register<TView>(UIPrefabDescriptor descriptor)
            where TView : IUIView
        {
            if (descriptor == null)
            {
                throw new ArgumentNullException(nameof(descriptor));
            }

            _descriptors[BuildKey(typeof(TView), descriptor.Key)] = descriptor;
        }

        public UIPrefabDescriptor GetDescriptor<TView>(string key)
            where TView : IUIView
        {
            return GetDescriptor(typeof(TView), key);
        }

        public UIPrefabDescriptor GetDescriptor(Type viewType, string key)
        {
            if (!_descriptors.TryGetValue(BuildKey(viewType, key), out UIPrefabDescriptor descriptor))
            {
                throw new UIManagerException(
                    $"No UI prefab descriptor registered for {viewType.Name} with key '{key}'.");
            }

            return descriptor;
        }

        private static string BuildKey(Type viewType, string key)
        {
            return $"{viewType.FullName}:{key}";
        }
    }
}
