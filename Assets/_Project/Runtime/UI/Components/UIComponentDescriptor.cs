using System;

namespace ForAI.Project.Runtime.UI.Components
{
    public sealed class UIComponentDescriptor
    {
        public UIComponentDescriptor(
            string key,
            string assetKey,
            Type componentType,
            UIComponentPoolPolicy poolPolicy = UIComponentPoolPolicy.None)
        {
            Key = string.IsNullOrWhiteSpace(key)
                ? throw new UIComponentRegistryException("UI component key cannot be empty.")
                : key;
            AssetKey = string.IsNullOrWhiteSpace(assetKey)
                ? throw new UIComponentRegistryException("UI component asset key cannot be empty.")
                : assetKey;
            ComponentType = ValidateComponentType(componentType);
            PoolPolicy = poolPolicy;
        }

        public string Key { get; }

        public string AssetKey { get; }

        public Type ComponentType { get; }

        public UIComponentPoolPolicy PoolPolicy { get; }

        private static Type ValidateComponentType(Type componentType)
        {
            if (componentType == null)
            {
                throw new UIComponentRegistryException("UI component type cannot be null.");
            }

            if (!typeof(IUIComponent).IsAssignableFrom(componentType))
            {
                throw new UIComponentRegistryException(
                    $"UI component type '{componentType.FullName}' must implement {nameof(IUIComponent)}.");
            }

            return componentType;
        }
    }
}
