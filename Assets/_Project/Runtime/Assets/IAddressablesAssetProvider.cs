using System.Threading;
using System.Threading.Tasks;
using UnityEngine;

namespace ForAI.Project.Runtime.Assets
{
    public interface IAddressablesAssetProvider
    {
        Task<IAddressablesAssetProviderHandle<T>> LoadAsync<T>(
            string key,
            CancellationToken cancellationToken)
            where T : Object;
    }

    public interface IAddressablesAssetProviderHandle<out T>
        where T : Object
    {
        T Asset { get; }

        void Release();
    }
}
