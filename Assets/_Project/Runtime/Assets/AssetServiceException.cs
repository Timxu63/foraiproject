using System;

namespace ForAI.Project.Runtime.Assets
{
    public sealed class AssetServiceException : Exception
    {
        public AssetServiceException(string message)
            : base(message)
        {
        }

        public AssetServiceException(string message, Exception innerException)
            : base(message, innerException)
        {
        }
    }
}
