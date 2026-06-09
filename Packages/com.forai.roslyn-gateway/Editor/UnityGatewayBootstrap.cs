using UnityEditor;

namespace ProjectMagicEscape.Editor.RoslynGateway
{
    [InitializeOnLoad]
    internal static class UnityGatewayBootstrap
    {
        static UnityGatewayBootstrap()
        {
            AssemblyReloadEvents.beforeAssemblyReload += OnBeforeAssemblyReload;
            EditorApplication.quitting += OnEditorQuitting;
            EditorApplication.delayCall += OnEditorDelayCall;
        }

        private static void OnEditorDelayCall()
        {
            EditorApplication.delayCall -= OnEditorDelayCall;
            UnityGatewayProcessController.TryAutoStartGatewayOnEditorLaunch();
        }

        private static void OnBeforeAssemblyReload()
        {
            UnityGatewayAgent.OnBeforeAssemblyReload();
        }

        private static void OnEditorQuitting()
        {
            UnityGatewayAgent.Shutdown();
        }
    }
}
