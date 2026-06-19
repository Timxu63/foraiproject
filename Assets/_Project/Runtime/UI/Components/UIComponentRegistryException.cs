using System;

namespace ForAI.Project.Runtime.UI.Components
{
    public sealed class UIComponentRegistryException : Exception
    {
        public UIComponentRegistryException(string message)
            : base(message)
        {
        }
    }
}
