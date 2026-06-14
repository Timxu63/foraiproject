using System.Threading;
using System.Threading.Tasks;

namespace ForAI.Project.Runtime.Network
{
    public interface INetworkClient
    {
        Task<ApiResult<T>> SendAsync<T>(RequestContext request, CancellationToken cancellationToken);
    }
}
