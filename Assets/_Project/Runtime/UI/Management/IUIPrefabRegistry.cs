using System;
using ForAI.Project.Runtime.UI.Core;

namespace ForAI.Project.Runtime.UI.Management
{
    public interface IUIPrefabRegistry
    {
        UIPrefabDescriptor GetDescriptor<TView>(string key)
            where TView : IUIView;

        UIPrefabDescriptor GetDescriptor(Type viewType, string key);
    }
}
