using System;
using System.Reflection;

namespace ForAI.Project.Runtime.Update
{
    public sealed class HybridClrReflectionRuntime : IHybridClrRuntime
    {
        private const string RuntimeApiTypeName = "HybridCLR.RuntimeApi, HybridCLR.Runtime";
        private const string HomologousImageModeTypeName = "HybridCLR.HomologousImageMode, HybridCLR.Runtime";

        public HybridClrMetadataLoadResult LoadMetadata(byte[] metadataAssembly)
        {
            if (metadataAssembly == null || metadataAssembly.Length == 0)
            {
                return HybridClrMetadataLoadResult.Failure("EMPTY_METADATA");
            }

            try
            {
                Type runtimeApiType = Type.GetType(RuntimeApiTypeName);
                Type homologousImageModeType = Type.GetType(HomologousImageModeTypeName);
                if (runtimeApiType == null || homologousImageModeType == null)
                {
                    return HybridClrMetadataLoadResult.Failure("HYBRIDCLR_RUNTIME_UNAVAILABLE");
                }

                MethodInfo method = runtimeApiType.GetMethod(
                    "LoadMetadataForAOTAssembly",
                    BindingFlags.Public | BindingFlags.Static,
                    null,
                    new[] {typeof(byte[]), homologousImageModeType},
                    null);
                if (method == null)
                {
                    return HybridClrMetadataLoadResult.Failure("LOAD_METADATA_METHOD_UNAVAILABLE");
                }

                object mode = Enum.Parse(homologousImageModeType, "SuperSet");
                object result = method.Invoke(null, new[] {metadataAssembly, mode});
                string errorCode = result?.ToString() ?? "UNKNOWN";
                return string.Equals(errorCode, "OK", StringComparison.Ordinal)
                    ? HybridClrMetadataLoadResult.Success()
                    : HybridClrMetadataLoadResult.Failure(errorCode);
            }
            catch (TargetInvocationException exception)
            {
                return HybridClrMetadataLoadResult.Failure(
                    exception.InnerException?.Message ?? exception.Message);
            }
            catch (Exception exception)
            {
                return HybridClrMetadataLoadResult.Failure(exception.Message);
            }
        }
    }
}
