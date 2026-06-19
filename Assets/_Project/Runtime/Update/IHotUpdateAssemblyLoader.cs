using System.Reflection;

namespace ForAI.Project.Runtime.Update
{
    public interface IHotUpdateAssemblyLoader
    {
        Assembly Load(byte[] assemblyBytes);
    }
}
