using System.Collections.Generic;
using ForAI.Project.HotUpdate.Features.Inventory.Application;
using NUnit.Framework;

namespace ForAI.Project.Tests.EditMode.HotUpdate
{
    public sealed class InventoryViewModelTests
    {
        [Test]
        public void SetItems_ReplacesItemsAndNotifiesChanged()
        {
            var viewModel = new InventoryViewModel();
            int changedCount = 0;
            viewModel.Changed += () => changedCount++;

            viewModel.SetItems(new List<InventoryItemViewData>
            {
                new InventoryItemViewData("coin", "Coin", 10)
            });

            Assert.That(viewModel.HasItems, Is.True);
            Assert.That(viewModel.Items.Count, Is.EqualTo(1));
            Assert.That(viewModel.Items[0].Id, Is.EqualTo("coin"));
            Assert.That(changedCount, Is.EqualTo(1));
        }

        [Test]
        public void SetItems_WithNullClearsItems()
        {
            var viewModel = new InventoryViewModel();
            viewModel.SetItems(new[]
            {
                new InventoryItemViewData("coin", "Coin", 10)
            });

            viewModel.SetItems(null);

            Assert.That(viewModel.HasItems, Is.False);
            Assert.That(viewModel.Items.Count, Is.EqualTo(0));
        }
    }
}
