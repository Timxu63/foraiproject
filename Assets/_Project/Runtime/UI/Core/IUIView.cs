using System.Threading;
using System.Threading.Tasks;

namespace ForAI.Project.Runtime.UI.Core
{
    public interface IUIView
    {
        bool IsOpen { get; }

        Task OpenAsync(UIOpenContext context, CancellationToken cancellationToken);

        Task CloseAsync(UICloseReason reason, CancellationToken cancellationToken);
    }
}
