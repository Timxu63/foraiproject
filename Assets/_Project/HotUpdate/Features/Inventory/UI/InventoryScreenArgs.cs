namespace ForAI.Project.HotUpdate.Features.Inventory.UI
{
    public readonly struct InventoryScreenArgs
    {
        public InventoryScreenArgs(string source)
        {
            Source = source;
        }

        public string Source { get; }
    }
}
