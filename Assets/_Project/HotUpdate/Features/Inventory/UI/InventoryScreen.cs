using System.Threading;
using System.Threading.Tasks;
using ForAI.Project.HotUpdate.Features.Inventory.Application;
using ForAI.Project.Runtime.UI.Core;

namespace ForAI.Project.HotUpdate.Features.Inventory.UI
{
    public sealed class InventoryScreen : UIPanelBase
    {
        public InventoryViewModel ViewModel { get; private set; }

        public InventoryScreenArgs Args { get; private set; }

        protected override Task OnOpenCoreAsync(
            UIOpenContext context,
            CancellationToken cancellationToken)
        {
            Args = context.GetArgs<InventoryScreenArgs>();
            ViewModel = new InventoryViewModel();
            return Task.CompletedTask;
        }
    }
}
