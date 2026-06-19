namespace ForAI.Project.Runtime.Update
{
    public readonly struct HybridClrMetadataLoadResult
    {
        private HybridClrMetadataLoadResult(bool isSuccess, string errorCode)
        {
            IsSuccess = isSuccess;
            ErrorCode = errorCode ?? string.Empty;
        }

        public bool IsSuccess { get; }

        public string ErrorCode { get; }

        public static HybridClrMetadataLoadResult Success()
        {
            return new HybridClrMetadataLoadResult(true, string.Empty);
        }

        public static HybridClrMetadataLoadResult Failure(string errorCode)
        {
            return new HybridClrMetadataLoadResult(false, errorCode);
        }
    }
}
