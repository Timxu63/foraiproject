using ForAI.Project.Runtime.UI.Components;
using NUnit.Framework;
using UnityEngine;

namespace ForAI.Project.Tests.EditMode.UI
{
    public sealed class UIListItemTests
    {
        [Test]
        public void BindTypedData_StoresDataAndInvokesTypedBind()
        {
            GameObject gameObject = new GameObject("Item");
            var item = gameObject.AddComponent<TestItem>();

            item.Bind(new ItemData("coin", 3));

            Assert.That(item.IsBound, Is.True);
            Assert.That(item.Data.Id, Is.EqualTo("coin"));
            Assert.That(item.Data.Count, Is.EqualTo(3));
            Assert.That(item.BindCount, Is.EqualTo(1));

            Object.DestroyImmediate(gameObject);
        }

        [Test]
        public void Recycle_UnbindsAndInvokesRecycleCore()
        {
            GameObject gameObject = new GameObject("Item");
            var item = gameObject.AddComponent<TestItem>();
            item.Bind(new ItemData("coin", 3));

            item.Recycle();

            Assert.That(item.IsBound, Is.False);
            Assert.That(item.UnbindCount, Is.EqualTo(1));
            Assert.That(item.Data.Id, Is.Null);
            Assert.That(item.Data.Count, Is.EqualTo(0));
            Assert.That(item.RecycleCount, Is.EqualTo(1));

            Object.DestroyImmediate(gameObject);
        }

        private readonly struct ItemData
        {
            public ItemData(string id, int count)
            {
                Id = id;
                Count = count;
            }

            public string Id { get; }

            public int Count { get; }
        }

        private sealed class TestItem : UIListItemBase<ItemData>
        {
            public int BindCount { get; private set; }
            public int UnbindCount { get; private set; }
            public int RecycleCount { get; private set; }

            protected override void OnBind(ItemData data)
            {
                BindCount++;
            }

            protected override void OnUnbind(ItemData data)
            {
                UnbindCount++;
            }

            protected override void OnRecycle()
            {
                RecycleCount++;
            }
        }
    }
}
