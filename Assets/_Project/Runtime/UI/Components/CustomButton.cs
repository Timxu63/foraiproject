using System;
using UnityEngine.UI;

namespace ForAI.Project.Runtime.UI.Components
{
    public sealed class CustomButton : UIComponentBase
    {
        private Button _button;
        private Action _clickHandler;

        private Button Button => _button ??= GetComponent<Button>();

        public void Bind(Action clickHandler)
        {
            Bind((object)clickHandler);
        }

        protected override void OnBind(object data)
        {
            _clickHandler = data as Action;
            if (_clickHandler != null && Button != null)
            {
                Button.onClick.AddListener(HandleClick);
            }
        }

        protected override void OnUnbind()
        {
            if (Button != null)
            {
                Button.onClick.RemoveListener(HandleClick);
            }

            _clickHandler = null;
        }

        private void HandleClick()
        {
            _clickHandler?.Invoke();
        }
    }
}
