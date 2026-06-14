using System.Threading;
using System.Threading.Tasks;
using ForAI.Project.Runtime.Assets;
using ForAI.Project.Runtime.Update;
using NUnit.Framework;

namespace ForAI.Project.Tests.EditMode.Update
{
    public sealed class HybridClrUpdateServiceTests
    {
        [Test]
        public void LoadHotUpdateAsync_ReturnsBlockedResultWhenNoLoaderIsConfigured()
        {
            var service = new HybridClrUpdateService(new AddressablesAssetService(), null);
            var manifest = HotUpdateManifest.Create(
                "hotupdate/main.dll",
                new[] {"aot/mscorlib.dll.bytes"});

            HotUpdateLoadResult result = service.LoadHotUpdateAsync(
                manifest,
                CancellationToken.None).GetAwaiter().GetResult();

            Assert.That(result.IsSuccess, Is.False);
            Assert.That(result.ErrorKind, Is.EqualTo(HotUpdateLoadErrorKind.LoaderUnavailable));
            Assert.That(result.Message, Does.Contain("HybridCLR"));
        }
    }
}
