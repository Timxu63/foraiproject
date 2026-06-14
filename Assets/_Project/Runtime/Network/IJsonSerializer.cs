namespace ForAI.Project.Runtime.Network
{
    public interface IJsonSerializer
    {
        T Deserialize<T>(string json);

        string Serialize<T>(T value);
    }
}
