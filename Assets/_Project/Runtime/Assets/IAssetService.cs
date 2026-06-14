using System;
using System.Threading;
using System.Threading.Tasks;
using UnityObject = UnityEngine.Object;

namespace ForAI.Project.Runtime.Assets
{
    public interface IAssetService
    {
        Task<IAssetHandle<T>> LoadAsync<T>(string key, CancellationToken cancellationToken)
            where T : UnityObject;

        void Release(IAssetHandle handle);
    }

    public interface IAssetHandle : IDisposable
    {
        string Key { get; }

        UnityObject UntypedAsset { get; }

        bool IsReleased { get; }
    }

    public interface IAssetHandle<out T> : IAssetHandle
        where T : UnityObject
    {
        T Asset { get; }
    }
}
