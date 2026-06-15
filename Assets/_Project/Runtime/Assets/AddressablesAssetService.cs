using System;
using System.Threading;
using System.Threading.Tasks;
using UnityObject = UnityEngine.Object;

namespace ForAI.Project.Runtime.Assets
{
    public sealed class AddressablesAssetService : IAssetService
    {
        private readonly IAddressablesAssetProvider _provider;

        public AddressablesAssetService()
            : this(CreateDefaultProvider())
        {
        }

        public AddressablesAssetService(IAddressablesAssetProvider provider)
        {
            _provider = provider;
        }

        public bool IsAvailable => _provider != null;

        public async Task<IAssetHandle<T>> LoadAsync<T>(string key, CancellationToken cancellationToken)
            where T : UnityObject
        {
            if (string.IsNullOrWhiteSpace(key))
            {
                throw new AssetServiceException("Addressables asset key cannot be empty.");
            }

            if (_provider == null)
            {
                throw new AssetServiceException(
                    "Addressables package is not installed or FORAI_ADDRESSABLES is not defined. " +
                    "Install Addressables through an approved package change before using AddressablesAssetService.");
            }

            try
            {
                IAddressablesAssetProviderHandle<T> providerHandle =
                    await _provider.LoadAsync<T>(key, cancellationToken);

                if (providerHandle == null || providerHandle.Asset == null)
                {
                    providerHandle?.Release();
                    throw new AssetServiceException($"Addressable asset '{key}' loaded as null.");
                }

                return new AssetHandle<T>(
                    key,
                    providerHandle.Asset,
                    _ => providerHandle.Release());
            }
            catch (OperationCanceledException)
            {
                throw;
            }
            catch (AssetServiceException exception)
            {
                throw new AssetServiceException(
                    $"Failed to load Addressable asset '{key}': {exception.Message}",
                    exception);
            }
            catch (Exception exception)
            {
                throw new AssetServiceException(
                    $"Failed to load Addressable asset '{key}': {exception.Message}",
                    exception);
            }
        }

        public void Release(IAssetHandle handle)
        {
            handle?.Dispose();
        }

        private static IAddressablesAssetProvider CreateDefaultProvider()
        {
#if FORAI_ADDRESSABLES
            return new UnityAddressablesAssetProvider();
#else
            return null;
#endif
        }
    }
}
