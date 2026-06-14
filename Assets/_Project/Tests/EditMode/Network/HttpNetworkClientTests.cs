using System;
using System.Threading;
using System.Threading.Tasks;
using ForAI.Project.Runtime.Network;
using NUnit.Framework;

namespace ForAI.Project.Tests.EditMode.Network
{
    public sealed class HttpNetworkClientTests
    {
        [Test]
        public void SendAsync_AddsDefaultJsonHeadersAndDeserializesSuccessfulResponse()
        {
            var transport = new RecordingTransport(
                new HttpTransportResponse(200, "{\"Name\":\"Ada\"}", null));
            var client = new HttpNetworkClient(transport, new UnityJsonSerializer());

            ApiResult<NameDto> result = client.SendAsync<NameDto>(
                RequestContext.Get("https://example.test/profile"),
                CancellationToken.None).GetAwaiter().GetResult();

            Assert.That(result.IsSuccess, Is.True);
            Assert.That(result.Value.Name, Is.EqualTo("Ada"));
            Assert.That(transport.LastRequest.Headers["Accept"], Is.EqualTo("application/json"));
            Assert.That(transport.LastRequest.Headers["Content-Type"], Is.EqualTo("application/json"));
        }

        [Test]
        public void SendAsync_RetriesTransientServerFailureBeforeReturningSuccess()
        {
            var transport = new RecordingTransport(
                new HttpTransportResponse(503, "unavailable", null),
                new HttpTransportResponse(200, "{\"Name\":\"Recovered\"}", null));
            var client = new HttpNetworkClient(transport, new UnityJsonSerializer());
            var request = RequestContext.Get("https://example.test/profile");
            request.RetryCount = 1;

            ApiResult<NameDto> result = client.SendAsync<NameDto>(
                request,
                CancellationToken.None).GetAwaiter().GetResult();

            Assert.That(result.IsSuccess, Is.True);
            Assert.That(result.Value.Name, Is.EqualTo("Recovered"));
            Assert.That(transport.SendCount, Is.EqualTo(2));
        }

        [Test]
        public void SendAsync_ReturnsCancelledResultWhenCancellationIsRequested()
        {
            var transport = new RecordingTransport(new OperationCanceledException());
            var client = new HttpNetworkClient(transport, new UnityJsonSerializer());

            ApiResult<NameDto> result = client.SendAsync<NameDto>(
                RequestContext.Get("https://example.test/profile"),
                CancellationToken.None).GetAwaiter().GetResult();

            Assert.That(result.IsSuccess, Is.False);
            Assert.That(result.ErrorKind, Is.EqualTo(ApiErrorKind.Cancelled));
        }

        [Serializable]
        private sealed class NameDto
        {
            public string Name;
        }

        private sealed class RecordingTransport : IHttpTransport
        {
            private readonly object[] _responses;
            private int _next;

            public RecordingTransport(params object[] responses)
            {
                _responses = responses;
            }

            public int SendCount { get; private set; }

            public HttpTransportRequest LastRequest { get; private set; }

            public Task<HttpTransportResponse> SendAsync(
                HttpTransportRequest request,
                CancellationToken cancellationToken)
            {
                SendCount++;
                LastRequest = request;

                object response = _responses[Math.Min(_next, _responses.Length - 1)];
                _next++;

                if (response is Exception exception)
                {
                    throw exception;
                }

                return Task.FromResult((HttpTransportResponse)response);
            }
        }
    }
}
