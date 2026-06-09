# Unity 代码配方

以下片段可作为 `--code '...'` 的基础模板。
每次调用保持单一意图。
当多个 Unity 在线时，命令需要添加 `--project-root "/path/to/UnityProject"` 指定目标工程。

## 1）在激活场景中创建 GameObject
```csharp
var go = new GameObject("AI_运行时创建");
go.transform.position = new Vector3(0f, 1f, 0f);
Debug.Log(go.name);
```

## 2）查找并重命名 GameObject
```csharp
var go = GameObject.Find("OldName");
if (go == null) throw new Exception("未找到 GameObject: OldName");
go.name = "新名称";
Debug.Log(go.name);
```

## 3）安全删除 GameObject
```csharp
var go = GameObject.Find("NeedDelete");
if (go != null)
{
    UnityEngine.Object.DestroyImmediate(go);
    Debug.Log("已删除 NeedDelete");
}
```

## 4）创建项目目录
```csharp
if (!UnityEditor.AssetDatabase.IsValidFolder("Assets/AI_Temp"))
{
    UnityEditor.AssetDatabase.CreateFolder("Assets", "AI_Temp");
}
UnityEditor.AssetDatabase.Refresh();
```

## 5）将资源移动到目标目录
```csharp
var error = UnityEditor.AssetDatabase.MoveAsset("Assets/OldPath/My.asset", "Assets/AI_Temp/My.asset");
if (!string.IsNullOrEmpty(error)) throw new Exception(error);
UnityEditor.AssetDatabase.SaveAssets();
UnityEditor.AssetDatabase.Refresh();
```

## 6）从已有 GameObject 创建 Prefab
```csharp
var go = GameObject.Find("CharacterRoot");
if (go == null) throw new Exception("未找到 CharacterRoot");
if (!UnityEditor.AssetDatabase.IsValidFolder("Assets/AI_Temp"))
{
    UnityEditor.AssetDatabase.CreateFolder("Assets", "AI_Temp");
}
UnityEditor.PrefabUtility.SaveAsPrefabAsset(go, "Assets/AI_Temp/CharacterRoot.prefab");
UnityEditor.AssetDatabase.SaveAssets();
UnityEditor.AssetDatabase.Refresh();
```

## 7）查询已加载场景与根对象数量
```csharp
var scene = UnityEngine.SceneManagement.SceneManager.GetActiveScene();
var roots = scene.GetRootGameObjects();
Debug.Log($"Scene={scene.path}, Roots={roots.Length}");
```

## 7.1）查询当前场景名（返回值模式）
```csharp
Debug.Log("Test");
return UnityEngine.SceneManagement.SceneManager.GetActiveScene().name;
```
建议命令：
```bash
python3 Packages/com.forai.roslyn-gateway/Python~/ai_gateway_client.py do-code --project-root "/path/to/UnityProject" --code 'Debug.Log("Test");return UnityEngine.SceneManagement.SceneManager.GetActiveScene().name;' --timeout 30
```

## 8）查询当前选择集
```csharp
var selected = UnityEditor.Selection.objects;
Debug.Log($"SelectionCount={selected.Length}");
for (int i = 0; i < selected.Length; i++)
{
    Debug.Log(selected[i].name);
}
```

## 9）触发脚本编译
```csharp
UnityEditor.Compilation.CompilationPipeline.RequestScriptCompilation();
Debug.Log("已请求编译");
```

此配方建议使用 `--timeout 120` 或更高。
编译在域重载期间可能导致短暂 `Busy` 或超时现象。

## 10）批量整理目录结构
```csharp
string[] folders = new string[]
{
    "Assets/AI_Temp",
    "Assets/AI_Temp/Prefabs",
    "Assets/AI_Temp/Materials",
    "Assets/AI_Temp/Scenes"
};

for (int i = 0; i < folders.Length; i++)
{
    var folder = folders[i];
    if (UnityEditor.AssetDatabase.IsValidFolder(folder)) continue;

    var parts = folder.Split('/');
    string parent = parts[0];
    for (int p = 1; p < parts.Length; p++)
    {
        string child = parts[p];
        string candidate = parent + "/" + child;
        if (!UnityEditor.AssetDatabase.IsValidFolder(candidate))
        {
            UnityEditor.AssetDatabase.CreateFolder(parent, child);
        }
        parent = candidate;
    }
}

UnityEditor.AssetDatabase.SaveAssets();
UnityEditor.AssetDatabase.Refresh();
```

## 11）查询资源依赖数量
```csharp
var deps = UnityEditor.AssetDatabase.GetDependencies("Assets/SomePrefab.prefab", true);
Debug.Log($"DependencyCount={deps.Length}");
```

## 12）强制保存已打开场景
```csharp
bool ok = UnityEditor.SceneManagement.EditorSceneManager.SaveOpenScenes();
Debug.Log($"SaveOpenScenes={ok}");
```

## 执行破坏性配方前
1. 先确认目标名称与路径存在。
2. 对缺失对象优先使用显式保护和异常提示。
3. 广泛操作拆成多次调用，并做中间验证。
4. 对高影响变更预先准备回滚策略。
