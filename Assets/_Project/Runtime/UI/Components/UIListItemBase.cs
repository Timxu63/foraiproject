namespace ForAI.Project.Runtime.UI.Components
{
    public abstract class UIListItemBase<TData> : UIComponentBase
    {
        public TData Data { get; private set; }

        public void Bind(TData data)
        {
            Bind((object)data);
        }

        public void Recycle()
        {
            Unbind();
            OnRecycle();
        }

        protected sealed override void OnBind(object data)
        {
            Data = data is TData typed ? typed : default;
            OnBind(Data);
        }

        protected sealed override void OnUnbind()
        {
            OnUnbind(Data);
            Data = default;
        }

        protected virtual void OnBind(TData data)
        {
        }

        protected virtual void OnUnbind(TData data)
        {
        }

        protected virtual void OnRecycle()
        {
        }
    }
}
