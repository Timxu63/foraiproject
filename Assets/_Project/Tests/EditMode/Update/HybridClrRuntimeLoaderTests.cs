using System;
using System.Reflection;
using System.Threading;
using System.Threading.Tasks;
using ForAI.Project.Runtime.Update;
using NUnit.Framework;

namespace ForAI.Project.Tests.EditMode.Update
{
    public sealed class HybridClrRuntimeLoaderTests
    {
        [Test]
        public void HybridClrRuntimeLoader_ReturnsMetadataFailureWhenRuntimeApiReportsError()
        {
            var runtime = new FakeHybridClrRuntime
            {
                MetadataLoadResult = HybridClrMetadataLoadResult.Failure("BAD_IMAGE")
            };
            var loader = new HybridClrRuntimeLoader(runtime, new FakeAssemblyLoader());
            var manifest = HotUpdateManifest.Create(
                "hot_update/windows/for_ai_project_hot_update",
                new[] {"hot_update/windows/aot/mscorlib"});

            HotUpdateLoadResult result = loader.LoadAsync(
                    manifest,
                    new byte[] {1, 2, 3},
                    new[] {new byte[] {4, 5, 6}},
                    CancellationToken.None)
                .GetAwaiter()
                .GetResult();

            Assert.That(result.IsSuccess, Is.False);
            Assert.That(result.ErrorKind, Is.EqualTo(HotUpdateLoadErrorKind.MetadataLoadFailed));
            Assert.That(result.Message, Does.Contain("BAD_IMAGE"));
        }

        [Test]
        public void HybridClrRuntimeLoader_LoadsMetadataBeforeHotUpdateAssembly()
        {
            var runtime = new FakeHybridClrRuntime();
            var assemblyLoader = new FakeAssemblyLoader(runtime);
            var loader = new HybridClrRuntimeLoader(runtime, assemblyLoader);
            var manifest = HotUpdateManifest.Create(
                "hot_update/windows/for_ai_project_hot_update",
                new[] {"hot_update/windows/aot/mscorlib", "hot_update/windows/aot/system_core"});

            HotUpdateLoadResult result = loader.LoadAsync(
                    manifest,
                    new byte[] {9, 8, 7},
                    new[] {new byte[] {1}, new byte[] {2}},
                    CancellationToken.None)
                .GetAwaiter()
                .GetResult();

            Assert.That(result.IsSuccess, Is.True);
            Assert.That(runtime.LoadedMetadataCount, Is.EqualTo(2));
            Assert.That(assemblyLoader.LoadedAssemblyCount, Is.EqualTo(1));
            Assert.That(assemblyLoader.LoadedAfterMetadataCount, Is.EqualTo(2));
            Assert.That(result.Message, Is.EqualTo("ForAI.Project.HotUpdate loaded"));
        }

        [Test]
        public void HybridClrRuntimeLoader_ReturnsAssemblyFailureWhenAssemblyLoadThrows()
        {
            var assemblyLoader = new FakeAssemblyLoader
            {
                Exception = new BadImageFormatException("invalid hot update dll")
            };
            var loader = new HybridClrRuntimeLoader(new FakeHybridClrRuntime(), assemblyLoader);
            var manifest = HotUpdateManifest.Create(
                "hot_update/windows/for_ai_project_hot_update",
                Array.Empty<string>());

            HotUpdateLoadResult result = loader.LoadAsync(
                    manifest,
                    new byte[] {9, 8, 7},
                    Array.Empty<byte[]>(),
                    CancellationToken.None)
                .GetAwaiter()
                .GetResult();

            Assert.That(result.IsSuccess, Is.False);
            Assert.That(result.ErrorKind, Is.EqualTo(HotUpdateLoadErrorKind.AssemblyLoadFailed));
            Assert.That(result.Message, Does.Contain("invalid hot update dll"));
        }

        private sealed class FakeHybridClrRuntime : IHybridClrRuntime
        {
            public HybridClrMetadataLoadResult MetadataLoadResult { get; set; } =
                HybridClrMetadataLoadResult.Success();

            public int LoadedMetadataCount { get; private set; }

            public HybridClrMetadataLoadResult LoadMetadata(byte[] metadataAssembly)
            {
                LoadedMetadataCount++;
                return MetadataLoadResult;
            }
        }

        private sealed class FakeAssemblyLoader : IHotUpdateAssemblyLoader
        {
            private readonly FakeHybridClrRuntime _runtime;

            public FakeAssemblyLoader()
            {
            }

            public FakeAssemblyLoader(FakeHybridClrRuntime runtime)
            {
                _runtime = runtime;
            }

            public Exception Exception { get; set; }

            public int LoadedAssemblyCount { get; private set; }

            public int LoadedAfterMetadataCount { get; private set; }

            public Assembly Load(byte[] assemblyBytes)
            {
                if (Exception != null)
                {
                    throw Exception;
                }

                LoadedAssemblyCount++;
                LoadedAfterMetadataCount = _runtime?.LoadedMetadataCount ?? 2;
                return typeof(ForAI.Project.HotUpdate.HotUpdateEntry).Assembly;
            }
        }
    }
}
