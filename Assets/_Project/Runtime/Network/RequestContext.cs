using System;
using System.Collections.Generic;

namespace ForAI.Project.Runtime.Network
{
    public sealed class RequestContext
    {
        private RequestContext(string method, string url)
        {
            Method = string.IsNullOrWhiteSpace(method)
                ? throw new ArgumentException("HTTP method cannot be empty.", nameof(method))
                : method;
            Url = string.IsNullOrWhiteSpace(url)
                ? throw new ArgumentException("URL cannot be empty.", nameof(url))
                : url;
            Headers = new Dictionary<string, string>();
            TimeoutSeconds = 15;
        }

        public string Method { get; }

        public string Url { get; }

        public string Body { get; private set; }

        public Dictionary<string, string> Headers { get; }

        public int TimeoutSeconds { get; set; }

        public int RetryCount { get; set; }

        public static RequestContext Get(string url)
        {
            return new RequestContext("GET", url);
        }

        public static RequestContext PostJson(string url, string body)
        {
            return new RequestContext("POST", url).WithBody(body);
        }

        public RequestContext WithBody(string body)
        {
            Body = body ?? string.Empty;
            return this;
        }

        public RequestContext WithHeader(string name, string value)
        {
            Headers[name] = value;
            return this;
        }
    }
}
