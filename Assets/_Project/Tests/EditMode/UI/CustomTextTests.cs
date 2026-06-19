using ForAI.Project.Runtime.UI.Components;
using NUnit.Framework;
using TMPro;
using UnityEngine;

namespace ForAI.Project.Tests.EditMode.UI
{
    public sealed class CustomTextTests
    {
        [Test]
        public void BindString_UpdatesLabelText()
        {
            GameObject gameObject = new GameObject("Text");
            var label = gameObject.AddComponent<TextMeshProUGUI>();
            var component = gameObject.AddComponent<CustomText>();

            component.Bind("Coins");

            Assert.That(label.text, Is.EqualTo("Coins"));

            Object.DestroyImmediate(gameObject);
        }

        [Test]
        public void BindNull_ClearsLabelText()
        {
            GameObject gameObject = new GameObject("Text");
            var label = gameObject.AddComponent<TextMeshProUGUI>();
            var component = gameObject.AddComponent<CustomText>();

            component.Bind(null);

            Assert.That(label.text, Is.Empty);

            Object.DestroyImmediate(gameObject);
        }

        [Test]
        public void Unbind_ClearsPreviousText()
        {
            GameObject gameObject = new GameObject("Text");
            var label = gameObject.AddComponent<TextMeshProUGUI>();
            var component = gameObject.AddComponent<CustomText>();

            component.Bind("Coins");
            component.Unbind();

            Assert.That(label.text, Is.Empty);

            Object.DestroyImmediate(gameObject);
        }
    }
}
