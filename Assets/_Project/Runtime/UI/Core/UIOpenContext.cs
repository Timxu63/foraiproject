namespace ForAI.Project.Runtime.UI.Core
{
    public sealed class UIOpenContext
    {
        public UIOpenContext(string key, object args)
        {
            Key = key;
            Args = args;
        }

        public string Key { get; }

        public object Args { get; }

        public T GetArgs<T>()
        {
            return Args is T typed ? typed : default;
        }
    }
}
