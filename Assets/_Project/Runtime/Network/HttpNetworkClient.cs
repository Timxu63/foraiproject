using System;
using System.Collections.Generic;
using System.Threading;
using System.Threading.Tasks;

namespace ForAI.Project.Runtime.Network
{
    public sealed class HttpNetworkClient : INetworkClient
    {
        private readonly IHttpTransport _transport;
        private readonly IJsonSerializer _serializer;

        public HttpNetworkClient(IHttpTransport transport, IJsonSerializer serializer)
        {
            _transport = transport ?? throw new ArgumentNullException(nameof(transport));
            _serializer = serializer ?? throw new ArgumentNullException(nameof(serializer));
        }

        public async Task<ApiResult<T>> SendAsync<T>(
            RequestContext request,
            CancellationToken cancellationToken)
        {
            if (request == null)
            {
                throw new ArgumentNullException(nameof(request));
            }

            int maxAttempts = Math.Max(1, request.RetryCount + 1);
            for (int attempt = 1; attempt <= maxAttempts; attempt++)
            {
                try
                {
                    HttpTransportResponse response = await _transport.SendAsync(
                        BuildTransportRequest(request),
                        cancellationToken);

                    if (IsTransient(response.StatusCode) && attempt < maxAttempts)
                    {
                        continue;
                    }

                    if (response.StatusCode < 200 || response.StatusCode >= 300)
                    {
                        return ApiResult<T>.Failure(
                            ApiErrorKind.Http,
                            response.Error ?? response.Body ?? $"HTTP {response.StatusCode}",
                            response.StatusCode,
                            rawBody: response.Body);
                    }

                    T value = string.IsNullOrWhiteSpace(response.Body)
                        ? default
                        : _serializer.Deserialize<T>(response.Body);
                    return ApiResult<T>.Success(value, response.StatusCode, response.Body);
                }
                catch (OperationCanceledException)
                {
                    return ApiResult<T>.Failure(ApiErrorKind.Cancelled, "Request was cancelled.");
                }
                catch (TimeoutException exception)
                {
                    if (attempt < maxAttempts)
                    {
                        continue;
                    }

                    return ApiResult<T>.Failure(ApiErrorKind.Timeout, exception.Message);
                }
                catch (Exception exception)
                {
                    if (attempt < maxAttempts)
                    {
                        continue;
                    }

                    return ApiResult<T>.Failure(ApiErrorKind.Transport, exception.Message);
                }
            }

            return ApiResult<T>.Failure(ApiErrorKind.Transport, "Request failed without a response.");
        }

        private static HttpTransportRequest BuildTransportRequest(RequestContext request)
        {
            var headers = new Dictionary<string, string>(request.Headers);
            if (!headers.ContainsKey("Accept"))
            {
                headers["Accept"] = "application/json";
            }

            if (!headers.ContainsKey("Content-Type"))
            {
                headers["Content-Type"] = "application/json";
            }

            return new HttpTransportRequest(
                request.Method,
                request.Url,
                request.Body,
                request.TimeoutSeconds,
                headers);
        }

        private static bool IsTransient(int statusCode)
        {
            return statusCode == 408 || statusCode == 429 || statusCode >= 500;
        }
    }
}
