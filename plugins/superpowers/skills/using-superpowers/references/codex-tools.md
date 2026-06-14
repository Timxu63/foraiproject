# Codex Tool Mapping

Skills use Claude Code tool names. When you encounter these in a skill, use your platform equivalent:

| Skill references | Codex equivalent |
|-----------------|------------------|
| `Task` tool (dispatch subagent) | `spawn_agent` (see [Subagent dispatch requires multi-agent support](#subagent-dispatch-requires-multi-agent-support)) |
| Multiple `Task` calls (parallel) | Multiple `spawn_agent` calls |
| Task returns result | `wait_agent` |
| Task completes automatically | `close_agent` to free slot |
| `TodoWrite` (task tracking) | `update_plan` |
| `Skill` tool (invoke a skill) | Skills load natively — just follow the instructions |
| `Read`, `Write`, `Edit` (files) | Use your native file tools |
| `Bash` (run commands) | Use your native shell tools |

## Subagent dispatch requires multi-agent support

Add to your Codex config (`~/.codex/config.toml`):

```toml
[features]
multi_agent = true
```

This enables `spawn_agent`, `wait_agent`, and `close_agent` for skills like `dispatching-parallel-agents` and `subagent-driven-development`.

Legacy note: Codex builds before `rust-v0.115.0` exposed spawned-agent
waiting as `wait`. Current Codex uses `wait_agent` for spawned agents. The
`wait` name now belongs to code-mode `exec/wait`, which resumes a yielded exec
cell by `cell_id`; it is not the spawned-agent result tool.

## Environment Detection

Skills that create worktrees or finish branches should first get an
explicit user git-topology decision, then detect their environment with
read-only git commands before proceeding:

```bash
GIT_DIR=$(cd "$(git rev-parse --git-dir)" 2>/dev/null && pwd -P)
GIT_COMMON=$(cd "$(git rev-parse --git-common-dir)" 2>/dev/null && pwd -P)
BRANCH=$(git branch --show-current)
```

- `GIT_DIR != GIT_COMMON` → already in a linked worktree (skip creation)
- `BRANCH` empty → detached HEAD (cannot branch/push/PR from sandbox)

See `using-git-worktrees` Step 0 and `finishing-a-development-branch`
Step 1 for how each skill uses these signals.

Plan approval, implementation approval, and being on `main`/`master` are
not consent to create or switch branches/worktrees.

## ForAI Universal Workflow

In `D:\foraiproject`, every AI request must enter the project workflow engine
before substantial reasoning, planning, editing, or execution:

```powershell
python tools\ai\ai.py workflow begin --profile question --intent "<intent>" --project-root "D:\foraiproject"
python tools\ai\ai.py workflow begin --profile plan --intent "<intent>" --project-root "D:\foraiproject"
python tools\ai\ai.py workflow begin --profile change --intent "<intent>" --project-root "D:\foraiproject"
```

Use `question` for explanation and analysis, `plan` for planning/design mode,
and `change` for any request that may edit files or execute project changes.
Before mutation in a `change` workflow, run:

```powershell
python tools\ai\ai.py workflow preflight --run-id <run-id> --project-root "D:\foraiproject"
```

`question` and `plan` workflows must not mutate files or Unity state.
`change` workflows must pass context, execution-plan, risk-review, and gate
checks before execution.

## Codex App Finishing

When the sandbox blocks branch/push operations (detached HEAD in an
externally managed worktree), the agent commits all work and informs
the user to use the App's native controls:

- **"Create branch"** — names the branch, then commit/push/PR via App UI
- **"Hand off to local"** — transfers work to the user's local checkout

The agent can still run tests, stage files, and output suggested branch
names, commit messages, and PR descriptions for the user to copy.
