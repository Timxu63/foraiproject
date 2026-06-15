using System;
using System.Threading;
using UnityEditor;
using UnityEditor.PackageManager;
using UnityEditor.PackageManager.Requests;
using UnityEngine;

namespace ForAI.Project.Editor.Addressables
{
    public static class AddressablesPackageInstaller
    {
        public const string PackageId = "com.unity.addressables@1.21.21";

        [MenuItem("ForAI/Addressables/Install Package")]
        public static void InstallAddressables()
        {
            AddRequest request = Client.Add(PackageId);
            DateTime deadline = DateTime.UtcNow.AddMinutes(5);

            while (!request.IsCompleted)
            {
                if (DateTime.UtcNow > deadline)
                {
                    throw new TimeoutException($"Timed out installing {PackageId}.");
                }

                Thread.Sleep(100);
            }

            if (request.Status == StatusCode.Failure)
            {
                throw new InvalidOperationException(
                    $"Failed to install {PackageId}: {request.Error?.message}");
            }

            AssetDatabase.Refresh();
            Debug.Log($"Installed {PackageId}.");
        }
    }
}
