using System;

namespace ForAI.Project.HotUpdate.Shared.ViewModels
{
    public abstract class ViewModelBase
    {
        public event Action Changed;

        protected void NotifyChanged()
        {
            Changed?.Invoke();
        }
    }
}
