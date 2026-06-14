using System;

namespace ForAI.Project.Runtime.UI.Management
{
    public sealed class UIManagerException : Exception
    {
        public UIManagerException(string message)
            : base(message)
        {
        }
    }
}
