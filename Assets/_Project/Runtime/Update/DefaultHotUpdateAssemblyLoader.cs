using System.Reflection;

namespace ForAI.Project.Runtime.Update
{
    public sealed class DefaultHotUpdateAssemblyLoader : IHotUpdateAssemblyLoader
    {
        public Assembly Load(byte[] assemblyBytes)
        {
            return Assembly.Load(assemblyBytes);
        }
    }
}
