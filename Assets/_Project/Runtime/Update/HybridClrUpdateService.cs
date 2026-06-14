using System;
using System.Collections.Generic;
using System.Threading;
using System.Threading.Tasks;
using ForAI.Project.Runtime.Assets;
using UnityEngine;

namespace ForAI.Project.Runtime.Update
{
    public sealed class HybridClrUpdateService
    {
        private readonly IAssetService _assetService;
        private readonly IHotUpdateLoader _loader;

        public HybridClrUpdateService(IAssetService assetService, IHotUpdateLoader loader)
        {
            _assetService = assetService ?? throw new ArgumentNullException(nameof(assetService));
            _loader = loader;
        }

        public async Task<HotUpdateLoadResult> LoadHotUpdateAsync(
            HotUpdateManifest manifest,
            CancellationToken cancellationToken)
        {
            if (manifest == null)
            {
                throw new ArgumentNullException(nameof(manifest));
            }

            if (_loader == null)
            {
                return HotUpdateLoadResult.Failure(
                    HotUpdateLoadErrorKind.LoaderUnavailable,
                    "HybridCLR loader is not configured. Install and configure HybridCLR through an approved package and build pipeline change.");
            }

            var handles = new List<IAssetHandle>();
            try
            {
                IAssetHandle<TextAsset> hotUpdateAssembly = await _assetService.LoadAsync<TextAsset>(
                    manifest.HotUpdateAssemblyKey,
                    cancellationToken);
                handles.Add(hotUpdateAssembly);

                var metadata = new List<byte[]>();
                foreach (string metadataKey in manifest.AotMetadataKeys)
                {
                    IAssetHandle<TextAsset> metadataAsset = await _assetService.LoadAsync<TextAsset>(
                        metadataKey,
                        cancellationToken);
                    handles.Add(metadataAsset);
                    metadata.Add(metadataAsset.Asset.bytes);
                }

                return await _loader.LoadAsync(
                    manifest,
                    hotUpdateAssembly.Asset.bytes,
                    metadata.ToArray(),
                    cancellationToken);
            }
            catch (AssetServiceException exception)
            {
                return HotUpdateLoadResult.Failure(
                    HotUpdateLoadErrorKind.AssetLoadFailed,
                    exception.Message);
            }
            finally
            {
                foreach (IAssetHandle handle in handles)
                {
                    _assetService.Release(handle);
                }
            }
        }
    }
}
