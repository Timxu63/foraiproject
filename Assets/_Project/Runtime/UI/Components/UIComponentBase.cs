using UnityEngine;

namespace ForAI.Project.Runtime.UI.Components
{
    public abstract class UIComponentBase : MonoBehaviour, IUIComponent
    {
        private bool _disposed;

        public bool IsBound { get; private set; }

        public void Bind(object data)
        {
            if (_disposed)
            {
                _disposed = false;
            }

            if (IsBound)
            {
                Unbind();
            }

            OnBind(data);
            IsBound = true;
        }

        public void Refresh()
        {
            if (!IsBound || _disposed)
            {
                return;
            }

            OnRefresh();
        }

        public void Unbind()
        {
            if (!IsBound)
            {
                return;
            }

            OnUnbind();
            IsBound = false;
        }

        public void DisposeComponent()
        {
            if (_disposed)
            {
                return;
            }

            Unbind();
            OnDispose();
            _disposed = true;
        }

        protected virtual void OnBind(object data)
        {
        }

        protected virtual void OnRefresh()
        {
        }

        protected virtual void OnUnbind()
        {
        }

        protected virtual void OnDispose()
        {
        }
    }
}
