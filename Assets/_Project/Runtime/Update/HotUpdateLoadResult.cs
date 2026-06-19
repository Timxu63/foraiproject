namespace ForAI.Project.Runtime.Update
{
    public readonly struct HotUpdateLoadResult
    {
        private HotUpdateLoadResult(
            bool isSuccess,
            HotUpdateLoadErrorKind errorKind,
            string message)
        {
            IsSuccess = isSuccess;
            ErrorKind = errorKind;
            Message = message;
        }

        public bool IsSuccess { get; }

        public HotUpdateLoadErrorKind ErrorKind { get; }

        public string Message { get; }

        public static HotUpdateLoadResult Success(string message = "")
        {
            return new HotUpdateLoadResult(true, HotUpdateLoadErrorKind.None, message ?? string.Empty);
        }

        public static HotUpdateLoadResult Failure(
            HotUpdateLoadErrorKind errorKind,
            string message)
        {
            return new HotUpdateLoadResult(false, errorKind, message);
        }
    }
}
