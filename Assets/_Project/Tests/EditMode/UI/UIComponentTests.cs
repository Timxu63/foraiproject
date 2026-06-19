using ForAI.Project.Runtime.UI.Components;
using NUnit.Framework;
using UnityEngine;

namespace ForAI.Project.Tests.EditMode.UI
{
    public sealed class UIComponentTests
    {
        [Test]
        public void Bind_CallsBindCoreAndMarksComponentBound()
        {
            GameObject gameObject = new GameObject("Component");
            var component = gameObject.AddComponent<TestComponent>();

            component.Bind("payload");

            Assert.That(component.IsBound, Is.True);
            Assert.That(component.BoundData, Is.EqualTo("payload"));
            Assert.That(component.BindCount, Is.EqualTo(1));

            Object.DestroyImmediate(gameObject);
        }

        [Test]
        public void Bind_WhenAlreadyBound_UnbindsPreviousDataBeforeRebinding()
        {
            GameObject gameObject = new GameObject("Component");
            var component = gameObject.AddComponent<TestComponent>();

            component.Bind("first");
            component.Bind("second");

            Assert.That(component.IsBound, Is.True);
            Assert.That(component.BoundData, Is.EqualTo("second"));
            Assert.That(component.BindCount, Is.EqualTo(2));
            Assert.That(component.UnbindCount, Is.EqualTo(1));

            Object.DestroyImmediate(gameObject);
        }

        [Test]
        public void DisposeComponent_UnbindsOnceAndCallsDisposeCore()
        {
            GameObject gameObject = new GameObject("Component");
            var component = gameObject.AddComponent<TestComponent>();
            component.Bind("payload");

            component.DisposeComponent();
            component.DisposeComponent();

            Assert.That(component.IsBound, Is.False);
            Assert.That(component.UnbindCount, Is.EqualTo(1));
            Assert.That(component.DisposeCount, Is.EqualTo(1));

            Object.DestroyImmediate(gameObject);
        }

        private sealed class TestComponent : UIComponentBase
        {
            public int BindCount { get; private set; }
            public int UnbindCount { get; private set; }
            public int DisposeCount { get; private set; }
            public object BoundData { get; private set; }

            protected override void OnBind(object data)
            {
                BindCount++;
                BoundData = data;
            }

            protected override void OnUnbind()
            {
                UnbindCount++;
                BoundData = null;
            }

            protected override void OnDispose()
            {
                DisposeCount++;
            }
        }
    }
}
