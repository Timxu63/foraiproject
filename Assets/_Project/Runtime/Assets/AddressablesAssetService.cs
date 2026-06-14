using System.Threading;
using System.Threading.Tasks;
using UnityEngine;

namespace ForAI.Project.Runtime.Assets
{
    public sealed class AddressablesAssetService : IAssetService
    {
        public bool IsAvailable
        {
            get
            {
#if FORAI_ADDRESSABLES
                return true;
#else
                return false;
#endif
            }
        }

        public Task<IAssetHandle<T>> LoadAsync<T>(string key, CancellationToken cancellationToken)
            where T : Object
        {
#if FORAI_ADDRESSABLES
            return LoadAddressableAsync<T>(key, cancellationToken);
#else
            throw new AssetServiceException(
                "Addressables package is not installed or FORAI_ADDRESSABLES is not defined. " +
                "Install Addressables through an approved package change before using AddressablesAssetService.");
#endif
        }

        public void Release(IAssetHandle handle)
        {
            handle?.Dispose();
        }

#if FORAI_ADDRESSABLES
        private Task<IAssetHandle<T>> LoadAddressableAsync<T>(string key, CancellationToken cancellationToken)
            where T : Object
        {
            throw new AssetServiceException(
                "Addressables runtime bridge is intentionally deferred until the package dependency is approved.");
        }
#endif
    }
}
