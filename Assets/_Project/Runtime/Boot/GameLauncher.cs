using System.Threading;
using System.Threading.Tasks;
using ForAI.Project.Runtime.Assets;
using ForAI.Project.Runtime.Network;
using ForAI.Project.Runtime.UI.Management;
using ForAI.Project.Runtime.Update;
using UnityEngine;

namespace ForAI.Project.Runtime.Boot
{
    public sealed class GameLauncher : MonoBehaviour
    {
        [SerializeField]
        private Transform uiRoot;

        public IAssetService AssetService { get; private set; }

        public INetworkClient NetworkClient { get; private set; }

        public UIManager UIManager { get; private set; }

        public HybridClrUpdateService UpdateService { get; private set; }

        public HotUpdateLoadResult LastHotUpdateLoadResult { get; private set; }

        private CancellationTokenSource _shutdownTokenSource;

        private async void Awake()
        {
            _shutdownTokenSource = new CancellationTokenSource();
            ConfigureAotServices();
            await InitializeAsync(_shutdownTokenSource.Token);
        }

        public void ConfigureAotServices()
        {
            AssetService = new AddressablesAssetService();
            NetworkClient = new HttpNetworkClient(
                new UnityWebRequestTransport(),
                new UnityJsonSerializer());

            var registry = new InMemoryUIPrefabRegistry();
            Transform root = uiRoot != null ? uiRoot : transform;
            UIManager = new UIManager(AssetService, registry, new UnityUIRoot(root));
            UpdateService = new HybridClrUpdateService(AssetService, new HybridClrRuntimeLoader());
        }

        public async Task InitializeAsync(CancellationToken cancellationToken)
        {
            LastHotUpdateLoadResult = await UpdateService.LoadHotUpdateAsync(
                HotUpdateManifest.CreateWindowsStandaloneDefault(),
                cancellationToken);

            if (!LastHotUpdateLoadResult.IsSuccess)
            {
                Debug.LogWarning(LastHotUpdateLoadResult.Message);
                return;
            }

            if (!string.IsNullOrWhiteSpace(LastHotUpdateLoadResult.Message))
            {
                Debug.Log($"HybridCLR hot update loaded: {LastHotUpdateLoadResult.Message}");
            }
        }

        private void OnDestroy()
        {
            _shutdownTokenSource?.Cancel();
            _shutdownTokenSource?.Dispose();
            _shutdownTokenSource = null;
        }
    }
}
