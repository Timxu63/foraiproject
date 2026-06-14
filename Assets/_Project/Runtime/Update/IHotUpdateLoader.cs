using System.Threading;
using System.Threading.Tasks;

namespace ForAI.Project.Runtime.Update
{
    public interface IHotUpdateLoader
    {
        Task<HotUpdateLoadResult> LoadAsync(
            HotUpdateManifest manifest,
            byte[] hotUpdateAssembly,
            byte[][] aotMetadataAssemblies,
            CancellationToken cancellationToken);
    }
}
