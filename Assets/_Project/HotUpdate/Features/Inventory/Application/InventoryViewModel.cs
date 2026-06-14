using System.Collections.Generic;
using ForAI.Project.HotUpdate.Shared.ViewModels;

namespace ForAI.Project.HotUpdate.Features.Inventory.Application
{
    public sealed class InventoryViewModel : ViewModelBase
    {
        private readonly List<InventoryItemViewData> _items = new List<InventoryItemViewData>();

        public IReadOnlyList<InventoryItemViewData> Items => _items;

        public bool HasItems => _items.Count > 0;

        public void SetItems(IEnumerable<InventoryItemViewData> items)
        {
            _items.Clear();
            if (items != null)
            {
                _items.AddRange(items);
            }

            NotifyChanged();
        }
    }
}
