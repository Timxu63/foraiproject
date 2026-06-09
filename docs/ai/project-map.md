# AI 项目地图

本文件描述当前项目结构，以及 AI 工作流应逐步迁移到的目标结构。

## 当前基线

- 项目根目录：`D:\foraiproject`
- Unity 版本：2022.3.62f2
- 渲染管线：Universal Render Pipeline
- Unity 测试包：`com.unity.test-framework`
- 现有网关：`Packages/com.forai.roslyn-gateway`
- 当前设计规格：`docs/superpowers/specs/2026-06-08-ai-friendly-unity-engineering-design.md`

## 当前重要路径

```text
Assets/
  Scenes/
  Settings/
Packages/
  com.forai.roslyn-gateway/
  manifest.json
  packages-lock.json
ProjectSettings/
docs/
  ai/
  superpowers/
```

## 目标项目 Unity 结构

```text
Assets/_Project/
  Runtime/
  Editor/
  Tests/
    EditMode/
    PlayMode/
  Scenes/
  Prefabs/
  ScriptableObjects/
  Art/
```

`Assets/_Project` 用于存放项目自有代码和内容。Runtime、Editor、Tests、Scenes、Prefabs、ScriptableObjects 和 Art 分开，便于 AI 按需扫描上下文。

## 目标 Gateway Package 结构

```text
Packages/com.forai.roslyn-gateway/
  package.json
  Editor/
  Tests/Editor/
  Python~/
  Documentation~/
```

`Python~` 和 `Documentation~` 使用 `~` 后缀，表示这些目录不需要被 Unity 作为资产导入。

## 目标 AI 工具结构

```text
tools/ai/
  cli/
  workflow_engine/
  agents/
  schemas/
  scanners/
  validators/
  unity_gateway_client/
```

## 验证命令

Schema 解析检查：

```powershell
Get-ChildItem tools\ai\schemas\*.json | ForEach-Object {
  Get-Content -Raw $_.FullName | ConvertFrom-Json | Out-Null
  Write-Output "OK $($_.Name)"
}
```

当 Unity 网关可用时，Unity 编译验证优先使用现有辅助脚本：

```powershell
python Packages\com.forai.roslyn-gateway\Python~\check_unity_compile.py --project-root "D:\foraiproject"
```

Unity Test Framework 的命令行验证应在后续 CLI wrapper 建立后加入。
