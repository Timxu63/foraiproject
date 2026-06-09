# AI-Friendly Unity Structure Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish the first enforceable layer of the AI-friendly Unity engineering structure: project instructions, AI docs, schemas, artifact policy, and ignore rules.

**Architecture:** Phase 1 intentionally avoids moving Unity assets or gateway code. It creates human-readable and machine-readable contracts so later implementation phases can safely migrate `RoslynGateway`, add CLI commands, and enforce Unity Adapter boundaries.

**Tech Stack:** Unity 2022.3.62f2, Python-oriented AI tooling, JSON Schema Draft 2020-12, Markdown documentation.

---

## File Structure

- Create `AGENTS.md`: root AI project instructions and required workflow boundaries.
- Create `docs/ai/architecture.md`: layer responsibilities and allowed dependencies.
- Create `docs/ai/project-map.md`: current project map and future target layout.
- Create `docs/ai/capability-registry.md`: tool capabilities and mutation boundaries.
- Create `docs/ai/risk-policy.md`: risk levels and confirmation rules.
- Create `docs/ai/workflows.md`: standard AI workflow stages.
- Create `tools/ai/schemas/*.schema.json`: versioned contract skeletons for the workflow.
- Create or modify `.gitignore`: Unity generated folders and AI run artifacts.

## Task 1: Root AI Project Instructions

**Files:**
- Create: `AGENTS.md`

- [ ] **Step 1: Create `AGENTS.md`**

Write a concise AI-facing project contract. It must state that agents do not directly mutate Unity assets and that Unity asset changes go through the Unity Editor Adapter.

- [ ] **Step 2: Verify the file is readable**

Run: `Get-Content -Raw AGENTS.md`

Expected: The file prints without encoding errors and includes "Unity Editor Adapter".

## Task 2: AI Documentation Set

**Files:**
- Create: `docs/ai/architecture.md`
- Create: `docs/ai/project-map.md`
- Create: `docs/ai/capability-registry.md`
- Create: `docs/ai/risk-policy.md`
- Create: `docs/ai/workflows.md`

- [ ] **Step 1: Create the documentation directory**

Run: `New-Item -ItemType Directory -Force docs\ai`

- [ ] **Step 2: Write the five documentation files**

Each file should be short, specific to this project, and consistent with the approved design spec.

- [ ] **Step 3: Verify docs exist**

Run: `Get-ChildItem docs\ai`

Expected: The five Markdown files are listed.

## Task 3: Schema Skeletons

**Files:**
- Create: `tools/ai/schemas/intent-analysis.v1.schema.json`
- Create: `tools/ai/schemas/context-pack.v1.schema.json`
- Create: `tools/ai/schemas/requirement-check.v1.schema.json`
- Create: `tools/ai/schemas/domain-spec.v1.schema.json`
- Create: `tools/ai/schemas/execution-plan.v1.schema.json`
- Create: `tools/ai/schemas/risk-review.v1.schema.json`
- Create: `tools/ai/schemas/unity-execution.v1.schema.json`
- Create: `tools/ai/schemas/validation-report.v1.schema.json`

- [ ] **Step 1: Create the schema directory**

Run: `New-Item -ItemType Directory -Force tools\ai\schemas`

- [ ] **Step 2: Add JSON Schema Draft 2020-12 files**

Each schema must include `$schema`, `$id`, `title`, `type`, `required`, and `additionalProperties`.

- [ ] **Step 3: Parse every schema as JSON**

Run:

```powershell
Get-ChildItem tools\ai\schemas\*.json | ForEach-Object {
  Get-Content -Raw $_.FullName | ConvertFrom-Json | Out-Null
  Write-Output "OK $($_.Name)"
}
```

Expected: Each schema prints `OK <file>`.

## Task 4: Ignore Rules

**Files:**
- Create or modify: `.gitignore`

- [ ] **Step 1: Add Unity and AI artifact ignore rules**

Rules must include Unity generated folders such as `Library/`, `Temp/`, `Logs/`, `Obj/`, `Build/`, `Builds/`, and AI run artifacts under `artifacts/ai-runs/`.

- [ ] **Step 2: Verify ignore file content**

Run: `Get-Content -Raw .gitignore`

Expected: The output includes `Library/` and `artifacts/ai-runs/`.

## Task 5: Phase 1 Verification

**Files:**
- Read: `AGENTS.md`
- Read: `docs/ai/*.md`
- Read: `tools/ai/schemas/*.schema.json`
- Read: `.gitignore`

- [ ] **Step 1: Scan for unfinished markers**

Run: `rg -n "T[B]D|TO[D]O|FIX[M]E|待[定]|占[位]" AGENTS.md docs\ai tools\ai\schemas .gitignore`

Expected: No matches.

- [ ] **Step 2: List created files**

Run: `Get-ChildItem AGENTS.md,docs\ai,tools\ai\schemas,.gitignore -Recurse | Select-Object FullName`

Expected: Root instructions, five docs, eight schemas, and `.gitignore` are present.

- [ ] **Step 3: Note repository limitation**

Run: `git rev-parse --show-toplevel`

Expected in current workspace: fails with `not a git repository`. This explains why no commit is made in Phase 1.
