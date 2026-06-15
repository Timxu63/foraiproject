#if FORAI_ADDRESSABLES
using System;
using System.Threading;
using System.Threading.Tasks;
using UnityEngine.AddressableAssets;
using UnityEngine.ResourceManagement.AsyncOperations;
using UnityObject = UnityEngine.Object;

namespace ForAI.Project.Runtime.Assets
{
    public sealed class UnityAddressablesAssetProvider : IAddressablesAssetProvider
    {
        public async Task<IAddressablesAssetProviderHandle<T>> LoadAsync<T>(
            string key,
            CancellationToken cancellationToken)
            where T : UnityObject
        {
            AsyncOperationHandle<T> handle = Addressables.LoadAssetAsync<T>(key);

            using (cancellationToken.Register(() => ReleaseIfValid(handle)))
            {
                try
                {
                    await handle.Task;
                }
                catch (OperationCanceledException)
                {
                    ReleaseIfValid(handle);
                    throw;
                }
                catch (Exception exception)
                {
                    ReleaseIfValid(handle);
                    if (cancellationToken.IsCancellationRequested)
                    {
                        throw new OperationCanceledException(cancellationToken);
                    }

                    throw new AssetServiceException(
                        $"Addressables failed while loading '{key}': {exception.Message}",
                        exception);
                }
            }

            cancellationToken.ThrowIfCancellationRequested();

            if (handle.Status != AsyncOperationStatus.Succeeded || handle.Result == null)
            {
                string status = handle.Status.ToString();
                ReleaseIfValid(handle);
                throw new AssetServiceException(
                    $"Addressables load for '{key}' did not succeed. Status: {status}.");
            }

            return new UnityAddressablesAssetProviderHandle<T>(handle);
        }

        private static void ReleaseIfValid<T>(AsyncOperationHandle<T> handle)
            where T : UnityObject
        {
            if (handle.IsValid())
            {
                Addressables.Release(handle);
            }
        }
    }

    internal sealed class UnityAddressablesAssetProviderHandle<T> : IAddressablesAssetProviderHandle<T>
        where T : UnityObject
    {
        private AsyncOperationHandle<T> _handle;
        private bool _released;

        public UnityAddressablesAssetProviderHandle(AsyncOperationHandle<T> handle)
        {
            _handle = handle;
        }

        public T Asset => !_released && _handle.IsValid() ? _handle.Result : null;

        public void Release()
        {
            if (_released || !_handle.IsValid())
            {
                return;
            }

            _released = true;
            Addressables.Release(_handle);
        }
    }
}
#endif
