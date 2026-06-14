namespace ForAI.Project.Runtime.Network
{
    public enum ApiErrorKind
    {
        None,
        Transport,
        Http,
        Timeout,
        Cancelled,
        Serialization
    }
}
