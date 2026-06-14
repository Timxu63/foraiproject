using UnityEngine;

namespace ForAI.Project.Runtime.UI.Extensions
{
    public static class CanvasGroupExtensions
    {
        public static void SetVisible(this CanvasGroup canvasGroup, bool visible)
        {
            if (canvasGroup == null)
            {
                return;
            }

            canvasGroup.alpha = visible ? 1f : 0f;
            canvasGroup.blocksRaycasts = visible;
            canvasGroup.interactable = visible;
        }
    }
}
