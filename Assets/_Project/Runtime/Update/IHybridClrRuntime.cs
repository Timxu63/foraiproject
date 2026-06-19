namespace ForAI.Project.Runtime.Update
{
    public interface IHybridClrRuntime
    {
        HybridClrMetadataLoadResult LoadMetadata(byte[] metadataAssembly);
    }
}
