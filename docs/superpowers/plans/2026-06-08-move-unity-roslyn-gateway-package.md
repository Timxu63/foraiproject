# Move Unity Roslyn Gateway Package Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move `Assets/Editor/RoslynGateway` into `Packages/com.forai.roslyn-gateway` while preserving Unity metadata, Python gateway files, skill documentation, and editor execution behavior.

**Architecture:** The package keeps Unity Editor C# code under `Editor/`, Python gateway files under `Python~/`, and skill/docs under `Documentation~/`. `UnityGatewayPaths` becomes package-location aware instead of relying on `Application.dataPath/Editor/RoslynGateway`. Existing generated `.csproj` files are not manually maintained because Unity regenerates them.

**Tech Stack:** Unity 2022.3.62f2, Unity package layout, Editor assembly definition, PowerShell file moves, Python gateway scripts.

---

## File Structure

- Move: `Assets/Editor/RoslynGateway/*.cs` -> `Packages/com.forai.roslyn-gateway/Editor/*.cs`
- Move: `Assets/Editor/RoslynGateway/RoslynOfficial` -> `Packages/com.forai.roslyn-gateway/Editor/RoslynOfficial`
- Move: `Assets/Editor/RoslynGateway/Newtonsoft.Json.13.0.4` -> `Packages/com.forai.roslyn-gateway/Editor/Newtonsoft.Json.13.0.4`
- Move: `Assets/Editor/RoslynGateway/PyScripts` -> `Packages/com.forai.roslyn-gateway/Python~`
- Move: `Assets/Editor/RoslynGateway/skill` -> `Packages/com.forai.roslyn-gateway/Documentation~/skill`
- Create: `Packages/com.forai.roslyn-gateway/package.json`
- Create: `Packages/com.forai.roslyn-gateway/Editor/ForAI.RoslynGateway.Editor.asmdef`
- Modify: `Packages/com.forai.roslyn-gateway/Editor/UnityGatewayPaths.cs`
- Modify: `AGENTS.md`
- Modify: `docs/ai/project-map.md`

## Task 1: Safety Checks

- [ ] Resolve absolute source and destination paths.
- [ ] Confirm source is under `D:\foraiproject\Assets\Editor\RoslynGateway`.
- [ ] Confirm destination is under `D:\foraiproject\Packages\com.forai.roslyn-gateway`.
- [ ] Confirm destination does not already exist.

## Task 2: Move Files

- [ ] Create `Packages/com.forai.roslyn-gateway`.
- [ ] Create `Packages/com.forai.roslyn-gateway/Editor`.
- [ ] Move C# files and their `.meta` files to package `Editor/`.
- [ ] Move `RoslynOfficial` and `.meta` to package `Editor/`.
- [ ] Move `Newtonsoft.Json.13.0.4` and `.meta` to package `Editor/`.
- [ ] Move `PyScripts` to `Python~`.
- [ ] Move `skill` to `Documentation~/skill`.
- [ ] Remove now-empty `Assets/Editor/RoslynGateway`.

## Task 3: Add Package Metadata

- [ ] Add `package.json` with package name `com.forai.roslyn-gateway`.
- [ ] Add `Editor/ForAI.RoslynGateway.Editor.asmdef`.

## Task 4: Update Runtime Paths

- [ ] Update `UnityGatewayPaths.cs` so `RoslynGatewayRoot` is resolved from the compiled assembly path.
- [ ] Set `GatewayToolDirectory` to `Python~`.
- [ ] Set `SkillSourceDirectory` to `Documentation~/skill/unity-roslyn-gateway`.
- [ ] Set `GatewayCliProjectRelativePath` to `Packages/com.forai.roslyn-gateway/Python~/ai_gateway_client.py`.

## Task 5: Update Human and AI Docs

- [ ] Update `AGENTS.md` current gateway path.
- [ ] Update `docs/ai/project-map.md` current gateway path and validation command.
- [ ] Update package-local skill and README references from old path to new path.

## Task 6: Verification

- [ ] Confirm old source directory no longer exists.
- [ ] Confirm package files exist.
- [ ] Parse `package.json`.
- [ ] Parse all JSON schemas.
- [ ] Run Python tests in `Python~/tests`.
- [ ] Try Unity compile validation through the new `Python~/check_unity_compile.py` path.
- [ ] If Unity is offline, report that compile validation could not be completed.

## Known Constraints

- The workspace is not currently a git repository, so this migration cannot be committed or protected by a git worktree.
- Generated solution/project files are ignored and are not updated manually.
- Python `__pycache__` files may be moved with the source tree if present; they are ignored by `.gitignore`.
