# AI-Friendly Unity Engineering Structure Design

Date: 2026-06-08
Project: `D:\foraiproject`
Unity: 2022.3.62f2

## Goal

Create an AI-friendly engineering structure for a Unity project where AI agents can analyze, plan, validate, and request changes without directly mutating Unity assets or relying on fragile free-form edits.

The design keeps Unity-specific mutations inside one trusted execution layer, makes all AI-facing data contract-driven, and records enough evidence to debug or repair failed runs.

## Current Project Baseline

The project already has several good foundations:

- Unity uses `Visible Meta Files` and text serialization in `ProjectSettings/EditorSettings.asset`.
- `com.unity.test-framework` is installed.
- `Packages/com.forai.roslyn-gateway` already separates external Python gateway calls from Unity Editor execution.
- Gateway request and response models already exist in both Python and C#.

Current gaps:

- `RoslynGateway` is still stored directly under `Assets/Editor` instead of an isolated package.
- No `.asmdef` files are present, so editor tooling is not compile-isolated.
- AI-facing contracts are mixed with gateway implementation details.
- There is no top-level documentation for AI workflows, capability boundaries, risk policy, or context packaging.
- The workspace is not currently a git repository, so spec commits and change review must be handled after version control is initialized or from the actual repository root.

## Design Principles

1. The workflow engine schedules stages; it does not know Unity APIs.
2. Agents read context and produce structured results; they do not edit files or assets directly.
3. The CLI is the stable public entry point for humans, agents, CI, and future MCP tools.
4. The Unity Editor Adapter is the only layer allowed to create, modify, move, or delete Unity assets, scenes, prefabs, project settings, or editor-only state.
5. All cross-layer messages use versioned schemas.
6. Every modifying run produces evidence: inputs, plan, risk decision, Unity execution result, compile result, tests, changed files, and repair hints.
7. Prefer simple, deterministic workflows before introducing autonomous multi-agent behavior.

## Recommended Repository Layout

```text
D:\foraiproject
  Assets/
    _Project/
      Runtime/
      Editor/
      Tests/
        EditMode/
        PlayMode/
      Scenes/
      Prefabs/
      ScriptableObjects/
      Art/
  Packages/
    com.forai.roslyn-gateway/
      package.json
      Editor/
      Tests/
        Editor/
      Python~/
      Documentation~/
  tools/
    ai/
      cli/
      workflow_engine/
      agents/
      schemas/
      scanners/
      validators/
      unity_gateway_client/
  docs/
    ai/
      architecture.md
      project-map.md
      capability-registry.md
      risk-policy.md
      workflows.md
    superpowers/
      specs/
  artifacts/
    ai-runs/
```

### Unity Project Area

`Assets/_Project` contains game code and content owned by this project. Runtime code, editor extensions, tests, scenes, prefabs, ScriptableObjects, and art assets are separated so context scans can select only relevant slices.

Recommended assembly definitions:

- `ForAI.Project.Runtime.asmdef`
- `ForAI.Project.Editor.asmdef`
- `ForAI.Project.Tests.EditMode.asmdef`
- `ForAI.Project.Tests.PlayMode.asmdef`

The editor and test assemblies should reference runtime assemblies explicitly. Runtime assemblies must not reference editor assemblies.

### Gateway Package Area

Move `Packages/com.forai.roslyn-gateway` into `Packages/com.forai.roslyn-gateway` after this design is approved and an implementation plan exists.

Recommended package contents:

- `Editor/`: Unity Editor C# adapter, Roslyn execution, gateway agent, control window.
- `Tests/Editor/`: edit-mode tests for adapter behavior and serialization contracts.
- `Python~/`: Python gateway server, CLI client, Pydantic models, tests, requirements.
- `Documentation~/`: usage, protocol, security mode, troubleshooting.

The `~` suffix is intentional for non-Unity-imported package folders such as Python and documentation.

Recommended assembly definition:

- `ForAI.RoslynGateway.Editor.asmdef`

### AI Tools Area

`tools/ai` contains non-Unity orchestration code. It is the place for workflow logic, scanners, validators, schemas, and CLI commands.

It must not directly edit Unity assets. If it needs to perform a Unity mutation, it calls the CLI command that reaches the Unity Editor Adapter.

### Documentation Area

`docs/ai` becomes the AI-readable operations manual:

- `architecture.md`: layer responsibilities and allowed dependencies.
- `project-map.md`: important folders, assemblies, scenes, packages, test commands.
- `capability-registry.md`: available tools and their permissions.
- `risk-policy.md`: what requires user confirmation.
- `workflows.md`: standard flows for feature creation, repair, validation, and refactor.

### Artifacts Area

`artifacts/ai-runs/<run-id>/` stores machine-readable outputs for each run:

```text
artifacts/ai-runs/2026-06-08T12-00-00Z-example/
  intent.json
  context-pack.json
  requirement-check.json
  domain-spec.json
  validation-report.json
  execution-plan.json
  risk-review.json
  unity-execution.json
  compile-report.json
  test-results.xml
  final-report.md
```

This directory should be ignored by version control unless a specific run is intentionally attached to a bug report.

## Layer Responsibilities

### User Intent Layer

Converts a natural language request into a first structured object.

Output: `IntentAnalysis`

Fields include:

- `goal`
- `domain`
- `requested_changes`
- `constraints`
- `unknowns`
- `risk_hints`

### Context Scan Layer

Builds a small context pack instead of dumping the whole project into a model.

Output: `ContextPack`

Included context should be selected by relevance:

- Unity version and packages.
- Assembly definitions.
- Known scenes, prefabs, ScriptableObjects, and tests.
- Existing code references.
- Gateway status, if Unity execution may be needed.

### Completeness And Gap Layer

Checks whether the request is implementable.

Output: `RequirementCheck`

It decides:

- `ready`: enough detail to continue.
- `needs_clarification`: user input required.
- `defaultable`: missing detail can be safely defaulted.
- `blocked`: cannot proceed without external setup.

### Domain Spec Layer

Produces the domain-level desired state without implementation steps.

Output: `DomainSpec`

Example:

```json
{
  "version": "ai-domain-spec/v1",
  "goal": "Create a collectible item prefab",
  "objects": [
    {
      "type": "prefab",
      "path": "Assets/_Project/Prefabs/Items/Coin.prefab",
      "components": ["SpriteRenderer", "CircleCollider2D"]
    }
  ],
  "acceptanceCriteria": [
    "Prefab exists at the requested path",
    "Prefab has a SpriteRenderer",
    "EditMode validation passes"
  ]
}
```

### Plan Layer

Converts a validated domain spec into steps.

Output: `ExecutionPlan`

Each step must be one of:

- Read-only scan.
- CLI operation.
- Unity Adapter operation.
- Validation operation.

No step may contain arbitrary direct edits to `.unity`, `.prefab`, `.asset`, `.meta`, or `ProjectSettings` files.

### Risk Layer

Classifies actions before execution.

Risk levels:

- `low`: read-only or generated docs.
- `medium`: creating new assets, tests, or scripts in project-owned folders.
- `high`: deleting, moving, or overwriting assets; changing scenes; changing prefabs; changing project settings; bulk operations.
- `blocked`: secrets, destructive operations outside the project, ambiguous multi-Unity targets, or unsafe code execution.

High-risk actions require explicit user confirmation unless the user has already approved the exact plan.

### Execution Layer

The CLI executes approved plans.

Allowed mutation paths:

- Ordinary source/documentation files may be edited by normal file tools when scoped and reviewed.
- Unity assets and editor state must be changed through the Unity Editor Adapter.
- Package manifest or project settings changes should go through a dedicated command that previews and validates the diff.

### Unity Editor Adapter Layer

The adapter is responsible for Unity-aware changes:

- Create, modify, move, or delete Unity assets.
- Create or modify prefabs.
- Read active scene or selection state.
- Trigger asset refresh.
- Trigger script compilation.
- Run editor-side validation.

Adapter operations should be idempotent where practical. Re-running the same operation should not duplicate objects or corrupt assets.

### Validation Layer

Validation must collect evidence, not only return success text.

Minimum checks:

- Unity gateway request result.
- Unity compilation diagnostics.
- EditMode tests when editor code or assets are changed.
- PlayMode tests when runtime behavior is changed.
- Changed file summary.

The project should use Unity Test Framework command-line execution for CI and local automation.

## CLI Shape

Recommended top-level commands:

```text
ai scan project
ai intent analyze
ai requirements check
ai spec generate
ai spec validate
ai plan generate
ai risk review
ai unity status
ai unity execute
ai validate compile
ai validate tests
ai report show
```

Command rules:

- Every command emits JSON with a stable `version` field.
- Every modifying command accepts `--dry-run`.
- Every run has a `runId`.
- Every Unity-targeting command accepts `--project-root` and optionally `--unity-id`.
- Human-readable output is allowed, but machine-readable output is primary.

## Schema Strategy

Use versioned schemas for all cross-layer objects:

```text
tools/ai/schemas/
  intent-analysis.v1.schema.json
  context-pack.v1.schema.json
  requirement-check.v1.schema.json
  domain-spec.v1.schema.json
  execution-plan.v1.schema.json
  risk-review.v1.schema.json
  unity-execution.v1.schema.json
  validation-report.v1.schema.json
```

The Python implementation should use Pydantic models generated from or aligned with these schemas. The Unity C# adapter should mirror only the gateway protocol schemas it actually consumes.

Schema compatibility rules:

- Additive optional fields are allowed within the same major version.
- Removing or renaming fields requires a new version.
- Execution must reject unknown major versions.
- Reports must preserve raw adapter responses for debugging.

## Agent Design

Start with workflow roles, not autonomous personalities:

- `IntentAgent`: converts user request to `IntentAnalysis`.
- `ContextScanner`: deterministic scanner with no LLM required where possible.
- `SpecAgent`: creates `DomainSpec`.
- `PlanAgent`: creates `ExecutionPlan`.
- `RiskReviewer`: deterministic rules first, LLM assistance second.
- `RepairAgent`: proposes fixes from validation evidence.

Agents cannot:

- Write Unity assets.
- Run arbitrary shell commands directly.
- Decide to skip validation.
- Hide uncertainty by inventing project state.

Agents must:

- Return structured output.
- Cite the context pack fields they used.
- Mark assumptions explicitly.
- Escalate when a decision is high risk or ambiguous.

## Unity Adapter Contract

The existing Roslyn gateway can remain the underlying execution mechanism, but it should expose higher-level operations over time.

Phase 1 operations:

- `do-code`
- `status`
- `list-unities`
- `check-compile`

Phase 2 operations:

- `create-folder`
- `create-prefab-from-spec`
- `modify-prefab-from-spec`
- `create-scriptable-object`
- `read-scene-summary`
- `run-editmode-tests`
- `run-playmode-tests`

Phase 2 operations should call Unity APIs internally instead of asking the model to generate arbitrary C# snippets for common tasks.

## Safety Policy

Blocked by default:

- Modifying files outside the workspace.
- Deleting assets without a plan and confirmation.
- Bulk renames without a preview.
- Editing `.meta` files directly.
- Editing `.unity` or `.prefab` YAML directly.
- Running Unity code when more than one Unity instance is online and no target is specified.
- Treating `SecurityCheck` as a compile error.

Allowed with confirmation:

- Scene changes.
- Prefab overwrites.
- ProjectSettings changes.
- Package manifest changes.
- Generated code that affects runtime behavior.

Allowed without confirmation after plan approval:

- Creating docs.
- Creating tests.
- Creating new scripts in approved project folders.
- Creating new assets in approved project folders.

## Migration Plan

1. Add documentation and schemas without moving current Unity files.
2. Add `.gitignore` entries for Unity and AI run artifacts if missing.
3. Add `.asmdef` files for gateway editor code.
4. Create `Packages/com.forai.roslyn-gateway`.
5. Move Roslyn gateway C# files into package `Editor/`.
6. Move Python files into package `Python~/`.
7. Update skill and documentation paths.
8. Add adapter contract tests.
9. Add CLI wrapper commands.
10. Add run artifact generation.

Each migration step should compile and validate before the next step starts.

## Acceptance Criteria

This design is successful when:

- AI-facing docs clearly describe allowed layers and mutation boundaries.
- Gateway code is isolated by package and assembly definition.
- CLI commands expose stable JSON contracts.
- Unity mutations go through adapter operations.
- All execution plans have risk reviews.
- Every modifying run produces evidence artifacts.
- Compile and test validation can be run from CLI or CI.

## Open Decisions

These choices can be deferred until implementation planning:

- Whether schemas are authored first as JSON Schema or Pydantic models.
- Whether the CLI is implemented in Python only, or wrapped later by Node/TypeScript.
- Whether MCP is added immediately or after the CLI stabilizes.

Recommended defaults:

- Author Pydantic models first and export JSON Schema.
- Implement the CLI in Python because the gateway already uses Python.
- Defer MCP until the CLI and adapter contracts are stable.
