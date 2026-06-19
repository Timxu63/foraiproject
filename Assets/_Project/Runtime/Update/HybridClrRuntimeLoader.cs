using System;
using System.Reflection;
using System.Threading;
using System.Threading.Tasks;

namespace ForAI.Project.Runtime.Update
{
    public sealed class HybridClrRuntimeLoader : IHotUpdateLoader
    {
        private readonly IHybridClrRuntime _runtime;
        private readonly IHotUpdateAssemblyLoader _assemblyLoader;

        public HybridClrRuntimeLoader()
            : this(new HybridClrReflectionRuntime(), new DefaultHotUpdateAssemblyLoader())
        {
        }

        public HybridClrRuntimeLoader(
            IHybridClrRuntime runtime,
            IHotUpdateAssemblyLoader assemblyLoader)
        {
            _runtime = runtime ?? throw new ArgumentNullException(nameof(runtime));
            _assemblyLoader = assemblyLoader ?? throw new ArgumentNullException(nameof(assemblyLoader));
        }

        public Task<HotUpdateLoadResult> LoadAsync(
            HotUpdateManifest manifest,
            byte[] hotUpdateAssembly,
            byte[][] aotMetadataAssemblies,
            CancellationToken cancellationToken)
        {
            if (manifest == null)
            {
                throw new ArgumentNullException(nameof(manifest));
            }

            cancellationToken.ThrowIfCancellationRequested();

            byte[][] metadataAssemblies = aotMetadataAssemblies ?? Array.Empty<byte[]>();
            for (int index = 0; index < metadataAssemblies.Length; index++)
            {
                cancellationToken.ThrowIfCancellationRequested();
                HybridClrMetadataLoadResult metadataResult = _runtime.LoadMetadata(metadataAssemblies[index]);
                if (!metadataResult.IsSuccess)
                {
                    return Task.FromResult(HotUpdateLoadResult.Failure(
                        HotUpdateLoadErrorKind.MetadataLoadFailed,
                        $"HybridCLR failed to load AOT metadata at index {index}: {metadataResult.ErrorCode}"));
                }
            }

            try
            {
                cancellationToken.ThrowIfCancellationRequested();
                Assembly assembly = _assemblyLoader.Load(hotUpdateAssembly);
                string entryResult = InvokeHotUpdateEntry(assembly);
                return Task.FromResult(HotUpdateLoadResult.Success(entryResult));
            }
            catch (Exception exception) when (!(exception is OperationCanceledException))
            {
                return Task.FromResult(HotUpdateLoadResult.Failure(
                    HotUpdateLoadErrorKind.AssemblyLoadFailed,
                    $"HybridCLR failed to load hot update assembly '{manifest.HotUpdateAssemblyKey}': {exception.Message}"));
            }
        }

        private static string InvokeHotUpdateEntry(Assembly assembly)
        {
            if (assembly == null)
            {
                return string.Empty;
            }

            Type entryType = assembly.GetType("ForAI.Project.HotUpdate.HotUpdateEntry", false);
            MethodInfo method = entryType?.GetMethod(
                "Run",
                BindingFlags.Public | BindingFlags.Static,
                null,
                Type.EmptyTypes,
                null);
            object result = method?.Invoke(null, null);
            return result?.ToString() ?? string.Empty;
        }
    }
}
