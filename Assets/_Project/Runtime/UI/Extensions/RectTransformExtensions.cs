using UnityEngine;

namespace ForAI.Project.Runtime.UI.Extensions
{
    public static class RectTransformExtensions
    {
        public static void SetAnchoredX(this RectTransform transform, float x)
        {
            if (transform == null)
            {
                return;
            }

            Vector2 position = transform.anchoredPosition;
            position.x = x;
            transform.anchoredPosition = position;
        }

        public static void SetAnchoredY(this RectTransform transform, float y)
        {
            if (transform == null)
            {
                return;
            }

            Vector2 position = transform.anchoredPosition;
            position.y = y;
            transform.anchoredPosition = position;
        }
    }
}
