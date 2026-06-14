using UnityEngine;

namespace ForAI.Project.Runtime.Network
{
    public sealed class UnityJsonSerializer : IJsonSerializer
    {
        public T Deserialize<T>(string json)
        {
            if (typeof(T) == typeof(string))
            {
                return (T)(object)(json ?? string.Empty);
            }

            return JsonUtility.FromJson<T>(json);
        }

        public string Serialize<T>(T value)
        {
            if (value is string text)
            {
                return text;
            }

            return JsonUtility.ToJson(value);
        }
    }
}
