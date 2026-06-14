using System.Threading;
using System.Threading.Tasks;
using UnityEngine;

namespace ForAI.Project.Runtime.UI.Core
{
    public abstract class UIPanelBase : MonoBehaviour, IUIView
    {
        public bool IsOpen { get; private set; }

        public async Task OpenAsync(UIOpenContext context, CancellationToken cancellationToken)
        {
            if (IsOpen)
            {
                return;
            }

            gameObject.SetActive(true);
            await OnOpenCoreAsync(context, cancellationToken);
            IsOpen = true;
        }

        public async Task CloseAsync(UICloseReason reason, CancellationToken cancellationToken)
        {
            if (!IsOpen)
            {
                return;
            }

            await OnCloseCoreAsync(reason, cancellationToken);
            IsOpen = false;
        }

        protected virtual Task OnOpenCoreAsync(
            UIOpenContext context,
            CancellationToken cancellationToken)
        {
            return Task.CompletedTask;
        }

        protected virtual Task OnCloseCoreAsync(
            UICloseReason reason,
            CancellationToken cancellationToken)
        {
            return Task.CompletedTask;
        }
    }
}
