namespace ForAI.Project.Runtime.UI.Components
{
    public interface IUIComponent
    {
        bool IsBound { get; }

        void Bind(object data);

        void Refresh();

        void Unbind();

        void DisposeComponent();
    }
}
