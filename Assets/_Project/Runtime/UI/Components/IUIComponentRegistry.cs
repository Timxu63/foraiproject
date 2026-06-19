namespace ForAI.Project.Runtime.UI.Components
{
    public interface IUIComponentRegistry
    {
        UIComponentDescriptor GetDescriptor(string key);
    }
}
