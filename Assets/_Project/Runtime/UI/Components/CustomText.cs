using TMPro;

namespace ForAI.Project.Runtime.UI.Components
{
    public sealed class CustomText : UIComponentBase
    {
        private TMP_Text _label;

        private TMP_Text Label => _label ??= GetComponent<TMP_Text>();

        public void Bind(string text)
        {
            Bind((object)text);
        }

        protected override void OnBind(object data)
        {
            SetText(data as string);
        }

        protected override void OnUnbind()
        {
            SetText(string.Empty);
        }

        public void SetText(string text)
        {
            if (Label != null)
            {
                Label.text = text ?? string.Empty;
            }
        }
    }
}
