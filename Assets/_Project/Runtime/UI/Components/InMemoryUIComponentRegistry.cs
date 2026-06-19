using System;
using System.Collections.Generic;

namespace ForAI.Project.Runtime.UI.Components
{
    public sealed class InMemoryUIComponentRegistry : IUIComponentRegistry
    {
        private readonly Dictionary<string, UIComponentDescriptor> _descriptors =
            new Dictionary<string, UIComponentDescriptor>(StringComparer.Ordinal);

        public void Register(UIComponentDescriptor descriptor)
        {
            if (descriptor == null)
            {
                throw new ArgumentNullException(nameof(descriptor));
            }

            if (_descriptors.ContainsKey(descriptor.Key))
            {
                throw new UIComponentRegistryException(
                    $"UI component descriptor already registered for key '{descriptor.Key}'.");
            }

            _descriptors.Add(descriptor.Key, descriptor);
        }

        public UIComponentDescriptor GetDescriptor(string key)
        {
            if (string.IsNullOrWhiteSpace(key))
            {
                throw new UIComponentRegistryException("UI component key cannot be empty.");
            }

            if (!_descriptors.TryGetValue(key, out UIComponentDescriptor descriptor))
            {
                throw new UIComponentRegistryException(
                    $"No UI component descriptor registered for key '{key}'.");
            }

            return descriptor;
        }
    }
}
