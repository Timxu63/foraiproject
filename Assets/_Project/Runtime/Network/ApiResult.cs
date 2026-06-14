namespace ForAI.Project.Runtime.Network
{
    public readonly struct ApiResult<T>
    {
        private ApiResult(
            bool isSuccess,
            T value,
            int statusCode,
            ApiErrorKind errorKind,
            string errorCode,
            string message,
            string rawBody)
        {
            IsSuccess = isSuccess;
            Value = value;
            StatusCode = statusCode;
            ErrorKind = errorKind;
            ErrorCode = errorCode;
            Message = message;
            RawBody = rawBody;
        }

        public bool IsSuccess { get; }

        public T Value { get; }

        public int StatusCode { get; }

        public ApiErrorKind ErrorKind { get; }

        public string ErrorCode { get; }

        public string Message { get; }

        public string RawBody { get; }

        public static ApiResult<T> Success(T value, int statusCode, string rawBody)
        {
            return new ApiResult<T>(true, value, statusCode, ApiErrorKind.None, string.Empty, string.Empty, rawBody);
        }

        public static ApiResult<T> Failure(
            ApiErrorKind errorKind,
            string message,
            int statusCode = 0,
            string errorCode = "",
            string rawBody = "")
        {
            return new ApiResult<T>(false, default, statusCode, errorKind, errorCode, message, rawBody);
        }
    }
}
