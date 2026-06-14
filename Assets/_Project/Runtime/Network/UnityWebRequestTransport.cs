using System;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using UnityEngine.Networking;

namespace ForAI.Project.Runtime.Network
{
    public sealed class UnityWebRequestTransport : IHttpTransport
    {
        public async Task<HttpTransportResponse> SendAsync(
            HttpTransportRequest request,
            CancellationToken cancellationToken)
        {
            using UnityWebRequest unityRequest = CreateRequest(request);
            unityRequest.timeout = request.TimeoutSeconds;

            foreach (var header in request.Headers)
            {
                unityRequest.SetRequestHeader(header.Key, header.Value);
            }

            UnityWebRequestAsyncOperation operation = unityRequest.SendWebRequest();
            while (!operation.isDone)
            {
                if (cancellationToken.IsCancellationRequested)
                {
                    unityRequest.Abort();
                    cancellationToken.ThrowIfCancellationRequested();
                }

                await Task.Yield();
            }

            string error = unityRequest.result == UnityWebRequest.Result.Success
                ? string.Empty
                : unityRequest.error;
            return new HttpTransportResponse(
                (int)unityRequest.responseCode,
                unityRequest.downloadHandler?.text,
                error);
        }

        private static UnityWebRequest CreateRequest(HttpTransportRequest request)
        {
            var unityRequest = new UnityWebRequest(request.Url, request.Method);
            unityRequest.downloadHandler = new DownloadHandlerBuffer();

            if (!string.IsNullOrEmpty(request.Body))
            {
                byte[] body = Encoding.UTF8.GetBytes(request.Body);
                unityRequest.uploadHandler = new UploadHandlerRaw(body);
            }

            return unityRequest;
        }
    }
}
