using ForAI.Project.Runtime.UI.Components;
using NUnit.Framework;
using UnityEngine;
using UnityEngine.UI;

namespace ForAI.Project.Tests.EditMode.UI
{
    public sealed class CustomButtonTests
    {
        [Test]
        public void BindAction_InvokesClickHandler()
        {
            GameObject gameObject = new GameObject("Button");
            var button = gameObject.AddComponent<Button>();
            var component = gameObject.AddComponent<CustomButton>();
            int clickCount = 0;

            component.Bind(() => clickCount++);
            button.onClick.Invoke();

            Assert.That(clickCount, Is.EqualTo(1));

            Object.DestroyImmediate(gameObject);
        }

        [Test]
        public void Unbind_RemovesClickHandler()
        {
            GameObject gameObject = new GameObject("Button");
            var button = gameObject.AddComponent<Button>();
            var component = gameObject.AddComponent<CustomButton>();
            int clickCount = 0;

            component.Bind(() => clickCount++);
            component.Unbind();
            button.onClick.Invoke();

            Assert.That(clickCount, Is.EqualTo(0));

            Object.DestroyImmediate(gameObject);
        }

        [Test]
        public void BindAgain_ReplacesPreviousClickHandler()
        {
            GameObject gameObject = new GameObject("Button");
            var button = gameObject.AddComponent<Button>();
            var component = gameObject.AddComponent<CustomButton>();
            int firstClickCount = 0;
            int secondClickCount = 0;

            component.Bind(() => firstClickCount++);
            component.Bind(() => secondClickCount++);
            button.onClick.Invoke();

            Assert.That(firstClickCount, Is.EqualTo(0));
            Assert.That(secondClickCount, Is.EqualTo(1));

            Object.DestroyImmediate(gameObject);
        }
    }
}
