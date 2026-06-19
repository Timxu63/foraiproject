using ForAI.Project.Runtime.UI.Components;
using NUnit.Framework;
using UnityEngine;

namespace ForAI.Project.Tests.EditMode.UI
{
    public sealed class UIComponentRegistryTests
    {
        [Test]
        public void RegisterAndGetDescriptor_ReturnsRegisteredDescriptor()
        {
            var registry = new InMemoryUIComponentRegistry();
            var descriptor = new UIComponentDescriptor(
                "common/item_cell",
                "ui/common/item_cell",
                typeof(TestComponent),
                UIComponentPoolPolicy.Reuse);

            registry.Register(descriptor);

            UIComponentDescriptor actual = registry.GetDescriptor("common/item_cell");
            Assert.That(actual.AssetKey, Is.EqualTo("ui/common/item_cell"));
            Assert.That(actual.ComponentType, Is.EqualTo(typeof(TestComponent)));
            Assert.That(actual.PoolPolicy, Is.EqualTo(UIComponentPoolPolicy.Reuse));
        }

        [Test]
        public void Register_WithDuplicateKey_Throws()
        {
            var registry = new InMemoryUIComponentRegistry();
            var descriptor = new UIComponentDescriptor(
                "common/item_cell",
                "ui/common/item_cell",
                typeof(TestComponent));
            registry.Register(descriptor);

            Assert.Throws<UIComponentRegistryException>(() => registry.Register(descriptor));
        }

        [Test]
        public void Descriptor_RejectsTypeThatDoesNotImplementIUIComponent()
        {
            Assert.Throws<UIComponentRegistryException>(
                () => new UIComponentDescriptor(
                    "invalid",
                    "ui/invalid",
                    typeof(Transform)));
        }

        private sealed class TestComponent : UIComponentBase
        {
        }
    }
}
