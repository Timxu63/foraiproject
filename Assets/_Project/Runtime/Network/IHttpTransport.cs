using System.Collections.Generic;
using System.Threading;
using System.Threading.Tasks;

namespace ForAI.Project.Runtime.Network
{
    public interface IHttpTransport
    {
        Task<HttpTransportResponse> SendAsync(
            HttpTransportRequest request,
            CancellationToken cancellationToken);
    }

    public readonly struct HttpTransportRequest
    {
        public HttpTransportRequest(
            string method,
            string url,
            string body,
            int timeoutSeconds,
            IReadOnlyDictionary<string, string> headers)
        {
            Method = method;
            Url = url;
            Body = body;
            TimeoutSeconds = timeoutSeconds;
            Headers = headers;
        }

        public string Method { get; }

        public string Url { get; }

        public string Body { get; }

        public int TimeoutSeconds { get; }

        public IReadOnlyDictionary<string, string> Headers { get; }
    }

    public readonly struct HttpTransportResponse
    {
        public HttpTransportResponse(int statusCode, string body, string error)
        {
            StatusCode = statusCode;
            Body = body;
            Error = error;
        }

        public int StatusCode { get; }

        public string Body { get; }

        public string Error { get; }
    }
}
