namespace ForAI.Project.HotUpdate.Features.Inventory.Application
{
    public readonly struct InventoryItemViewData
    {
        public InventoryItemViewData(string id, string displayName, int count)
        {
            Id = id;
            DisplayName = displayName;
            Count = count;
        }

        public string Id { get; }

        public string DisplayName { get; }

        public int Count { get; }
    }
}
