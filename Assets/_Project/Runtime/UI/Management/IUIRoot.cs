using UnityEngine;

namespace ForAI.Project.Runtime.UI.Management
{
    public interface IUIRoot
    {
        Transform GetLayerRoot(UILayerId layerId);
    }
}
