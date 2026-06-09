# AI CLI 确定性管线 第 3 阶段实施计划

> **给 Agent 工作者：**实现本计划时必须使用 `superpowers:subagent-driven-development`（推荐）或 `superpowers:executing-plans`，并按任务逐项执行。步骤使用复选框（`- [ ]`）格式，便于追踪进度。

**目标：**为当前 Unity 项目建立第一条可用的确定性 AI 工作流管线：稳定的本地 CLI 能扫描项目上下文、校验 schema 产物、评审执行风险，并调用已迁移到 package 的 Unity Roslyn Gateway 做状态检查和编译验证。

**架构：**保持 Agent 输出和真实执行解耦。`tools/ai/ai.py` 作为稳定 CLI 入口，`tools/ai/forai/*` 承载确定性项目逻辑，`Packages/com.forai.roslyn-gateway/Python~/` 保持为 Unity Editor 通信层。本阶段不允许 Agent 直接修改 Unity 资产。

**技术栈：**Python 3.11+、标准库 `argparse/json/pathlib/subprocess/urllib`、`jsonschema`、现有 Unity Roslyn Gateway package、Unity 2022.3.62f2。

---

## 当前状态

- Unity 项目根目录：`D:\foraiproject`
- Unity 版本：`2022.3.62f2`
- Gateway package：`Packages/com.forai.roslyn-gateway`
- 机器协议：`tools/ai/schemas/*.schema.json`
- 人类文档：`AGENTS.md`、`docs/ai/*.md`

Gateway 已经移动到 package，但当前打开的 Unity Editor 仍需要重新加载 package 后，编译验证结果才可信。因此必须先完成任务 0，再继续搭建上层 CLI。

## 文件结构

- 新增：`tools/ai/requirements.txt`
  - AI 确定性工具的 Python 依赖。
- 新增：`tools/ai/ai.py`
  - 稳定本地 CLI 入口。
- 新增：`tools/ai/forai/__init__.py`
  - Python package 标记。
- 新增：`tools/ai/forai/paths.py`
  - 项目根目录、schema 目录、Gateway 目录解析。
- 新增：`tools/ai/forai/json_io.py`
  - UTF-8 JSON 读写工具。
- 新增：`tools/ai/forai/schemas.py`
  - JSON Schema 加载和校验。
- 新增：`tools/ai/forai/scanner.py`
  - 确定性 Unity 项目上下文扫描器。
- 新增：`tools/ai/forai/risk.py`
  - 确定性 execution-plan 风险评审器。
- 新增：`tools/ai/forai/artifacts.py`
  - run id 和 `artifacts/ai-runs` 目录工具。
- 新增：`tools/ai/forai/unity_gateway.py`
  - 对现有 Gateway CLI/scripts 的薄封装。
- 新增：`tools/ai/tests/test_paths.py`
- 新增：`tools/ai/tests/test_schemas.py`
- 新增：`tools/ai/tests/test_scanner.py`
- 新增：`tools/ai/tests/test_risk.py`
- 新增：`tools/ai/tests/test_artifacts.py`
- 新增：`tools/ai/examples/execution-plan.low-risk.json`
- 修改：`docs/ai/capability-registry.md`
  - 注册新的 CLI 能力。
- 修改：`docs/ai/workflows.md`
  - 增加 第 3 阶段的确定性命令序列。
- 修改：`AGENTS.md`
  - 声明 `tools/ai/ai.py` 是稳定工具入口。

---

## 任务 0：先验证迁移后的 Gateway

**文件：**
- 不修改文件。

- [ ] **步骤 1：关闭并重启 Unity Editor**

关闭当前打开的 `D:\foraiproject` Unity Editor，重新打开项目，并等待 package import 和脚本编译完成。

- [ ] **步骤 2：必要时启动 package-local Gateway server**

运行：

```powershell
Start-Process -FilePath "python" -ArgumentList "gateway_server.py" -WorkingDirectory "D:\foraiproject\Packages\com.forai.roslyn-gateway\Python~" -WindowStyle Hidden
```

期望：命令返回，且不弹出可见窗口。

- [ ] **步骤 3：确认 Unity 目标在线**

运行：

```powershell
python "D:\foraiproject\Packages\com.forai.roslyn-gateway\Python~\ai_gateway_client.py" list-unities
```

期望：JSON 输出至少包含一个 Unity 实例，且 `projectRoot` 等于 `D:\foraiproject`。

- [ ] **步骤 4：确认 Gateway 状态**

运行：

```powershell
python "D:\foraiproject\Packages\com.forai.roslyn-gateway\Python~\ai_gateway_client.py" status --project-root "D:\foraiproject"
```

期望：JSON 输出显示当前 Unity 项目处于在线或可执行状态。

- [ ] **步骤 5：确认 Unity 编译通过**

运行：

```powershell
python "D:\foraiproject\Packages\com.forai.roslyn-gateway\Python~\check_unity_compile.py" --project-root "D:\foraiproject"
```

期望：退出码为 `0`，没有编译错误。如果出现 package 引用错误，先修复 `Packages/com.forai.roslyn-gateway/Editor/ForAI.RoslynGateway.Editor.asmdef`，再继续后续任务。

---

## 任务 1：声明 Python 工具依赖

**文件：**
- 新增：`tools/ai/requirements.txt`

- [ ] **步骤 1：创建依赖文件**

写入：

```text
jsonschema>=4.22,<5
pytest>=8,<10
```

- [ ] **步骤 2：按需安装依赖**

运行：

```powershell
python -m pip install -r "D:\foraiproject\tools\ai\requirements.txt"
```

期望：安装成功，或提示依赖已经满足。

---

## 任务 2：建立 CLI 骨架和路径解析

**文件：**
- 新增：`tools/ai/ai.py`
- 新增：`tools/ai/forai/__init__.py`
- 新增：`tools/ai/forai/paths.py`
- 新增：`tools/ai/tests/test_paths.py`

- [ ] **步骤 1：先写失败测试**

创建 `tools/ai/tests/test_paths.py`：

```python
from pathlib import Path

from forai.paths import find_project_root, gateway_python_dir, schema_dir


def test_find_project_root_from_tools_ai():
    root = find_project_root(Path(__file__))
    assert (root / "ProjectSettings" / "ProjectVersion.txt").exists()
    assert (root / "tools" / "ai" / "schemas").is_dir()


def test_schema_dir_points_to_contracts():
    root = find_project_root(Path(__file__))
    assert schema_dir(root).name == "schemas"
    assert (schema_dir(root) / "context-pack.v1.schema.json").exists()


def test_gateway_python_dir_points_to_package():
    root = find_project_root(Path(__file__))
    assert gateway_python_dir(root).name == "Python~"
    assert (gateway_python_dir(root) / "ai_gateway_client.py").exists()
```

- [ ] **步骤 2：运行测试并确认失败**

运行：

```powershell
$env:PYTHONPATH="D:\foraiproject\tools\ai"
python -m pytest "D:\foraiproject\tools\ai\tests\test_paths.py" -q
```

期望：失败，原因是 `forai.paths` 尚不存在。

- [ ] **步骤 3：实现路径解析**

创建 `tools/ai/forai/paths.py`：

```python
from __future__ import annotations

from pathlib import Path


def find_project_root(start: Path | None = None) -> Path:
    current = (start or Path.cwd()).resolve()
    if current.is_file():
        current = current.parent

    for candidate in [current, *current.parents]:
        if (candidate / "ProjectSettings" / "ProjectVersion.txt").exists():
            return candidate

    raise FileNotFoundError("Could not find Unity project root from current path.")


def schema_dir(project_root: Path) -> Path:
    return project_root / "tools" / "ai" / "schemas"


def gateway_python_dir(project_root: Path) -> Path:
    return project_root / "Packages" / "com.forai.roslyn-gateway" / "Python~"
```

创建空文件 `tools/ai/forai/__init__.py`。

- [ ] **步骤 4：实现最小 CLI**

创建 `tools/ai/ai.py`：

```python
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from forai.paths import find_project_root


def print_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def handle_root(args: argparse.Namespace) -> int:
    root = find_project_root(Path(args.from_path) if args.from_path else None)
    print_json({"projectRoot": str(root)})
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="ForAI deterministic Unity workflow CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    root_parser = subparsers.add_parser("root", help="Print detected Unity project root")
    root_parser.add_argument("--from-path")
    root_parser.set_defaults(handler=handle_root)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.handler(args)


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **步骤 5：运行测试和 CLI**

运行：

```powershell
$env:PYTHONPATH="D:\foraiproject\tools\ai"
python -m pytest "D:\foraiproject\tools\ai\tests\test_paths.py" -q
python "D:\foraiproject\tools\ai\ai.py" root
```

期望：测试通过，CLI 输出 `D:\foraiproject`。

---

## 任务 3：加入 JSON IO 和 Schema 校验

**文件：**
- 新增：`tools/ai/forai/json_io.py`
- 新增：`tools/ai/forai/schemas.py`
- 新增：`tools/ai/tests/test_schemas.py`
- 修改：`tools/ai/ai.py`

- [ ] **步骤 1：先写 schema 测试**

创建 `tools/ai/tests/test_schemas.py`：

```python
import pytest

from forai.paths import find_project_root
from forai.schemas import SchemaValidationError, load_schema, validate_payload


def test_validate_context_pack_accepts_valid_payload():
    root = find_project_root()
    schema = load_schema(root, "context-pack/v1")
    payload = {
        "version": "context-pack/v1",
        "projectRoot": str(root),
        "unityVersion": "2022.3.62f2",
        "packages": [{"name": "com.unity.test-framework", "version": "1.1.33"}],
        "paths": ["ProjectSettings/ProjectVersion.txt"],
        "summaries": [{"source": "ProjectSettings", "summary": "Unity version file present"}],
    }
    validate_payload(schema, payload)


def test_validate_context_pack_rejects_extra_property():
    root = find_project_root()
    schema = load_schema(root, "context-pack/v1")
    payload = {
        "version": "context-pack/v1",
        "projectRoot": str(root),
        "unityVersion": "2022.3.62f2",
        "packages": [],
        "paths": [],
        "summaries": [],
        "extra": True,
    }
    with pytest.raises(SchemaValidationError):
        validate_payload(schema, payload)
```

- [ ] **步骤 2：运行测试并确认失败**

运行：

```powershell
$env:PYTHONPATH="D:\foraiproject\tools\ai"
python -m pytest "D:\foraiproject\tools\ai\tests\test_schemas.py" -q
```

期望：失败，原因是 schema helper 尚不存在。

- [ ] **步骤 3：实现 JSON helper**

创建 `tools/ai/forai/json_io.py`：

```python
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
```

- [ ] **步骤 4：实现 schema helper**

创建 `tools/ai/forai/schemas.py`：

```python
from __future__ import annotations

from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from forai.json_io import read_json
from forai.paths import schema_dir


class SchemaValidationError(ValueError):
    pass


SCHEMA_FILE_BY_ID = {
    "context-pack/v1": "context-pack.v1.schema.json",
    "domain-spec/v1": "domain-spec.v1.schema.json",
    "execution-plan/v1": "execution-plan.v1.schema.json",
    "intent-analysis/v1": "intent-analysis.v1.schema.json",
    "requirement-check/v1": "requirement-check.v1.schema.json",
    "risk-review/v1": "risk-review.v1.schema.json",
    "unity-execution/v1": "unity-execution.v1.schema.json",
    "validation-report/v1": "validation-report.v1.schema.json",
}


def load_schema(project_root: Path, schema_id: str) -> dict[str, Any]:
    try:
        filename = SCHEMA_FILE_BY_ID[schema_id]
    except KeyError as exc:
        raise KeyError(f"Unknown schema id: {schema_id}") from exc
    return read_json(schema_dir(project_root) / filename)


def validate_payload(schema: dict[str, Any], payload: dict[str, Any]) -> None:
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(payload), key=lambda error: list(error.path))
    if errors:
        first = errors[0]
        location = ".".join(str(part) for part in first.path) or "<root>"
        raise SchemaValidationError(f"{location}: {first.message}")
```

- [ ] **步骤 5：给 CLI 增加 `validate file` 命令**

在 `tools/ai/ai.py` 中加入：

```python
from forai.json_io import read_json
from forai.schemas import SchemaValidationError, load_schema, validate_payload


def handle_validate_file(args: argparse.Namespace) -> int:
    root = find_project_root(Path(args.project_root) if args.project_root else None)
    payload = read_json(Path(args.input))
    schema = load_schema(root, args.schema)
    try:
        validate_payload(schema, payload)
    except SchemaValidationError as exc:
        print_json({"status": "failed", "error": str(exc)})
        return 1
    print_json({"status": "passed", "schema": args.schema, "input": args.input})
    return 0
```

在 `build_parser()` 中注册：

```python
    validate_parser = subparsers.add_parser("validate", help="Validate structured AI artifacts")
    validate_subparsers = validate_parser.add_subparsers(dest="validate_command", required=True)
    validate_file_parser = validate_subparsers.add_parser("file", help="Validate one JSON file")
    validate_file_parser.add_argument("--schema", required=True)
    validate_file_parser.add_argument("--input", required=True)
    validate_file_parser.add_argument("--project-root")
    validate_file_parser.set_defaults(handler=handle_validate_file)
```

- [ ] **步骤 6：运行测试**

运行：

```powershell
$env:PYTHONPATH="D:\foraiproject\tools\ai"
python -m pytest "D:\foraiproject\tools\ai\tests\test_schemas.py" -q
```

期望：测试通过。

---

## 任务 4：加入确定性 Context Scanner

**文件：**
- 新增：`tools/ai/forai/scanner.py`
- 新增：`tools/ai/tests/test_scanner.py`
- 修改：`tools/ai/ai.py`

- [ ] **步骤 1：先写 scanner 测试**

创建 `tools/ai/tests/test_scanner.py`：

```python
from forai.paths import find_project_root
from forai.scanner import scan_context_pack
from forai.schemas import load_schema, validate_payload


def test_scan_context_pack_matches_schema():
    root = find_project_root()
    payload = scan_context_pack(root)
    assert payload["version"] == "context-pack/v1"
    assert payload["projectRoot"] == str(root)
    assert payload["unityVersion"].startswith("2022.3.")
    assert any(pkg["name"] == "com.unity.test-framework" for pkg in payload["packages"])
    validate_payload(load_schema(root, "context-pack/v1"), payload)
```

- [ ] **步骤 2：运行测试并确认失败**

运行：

```powershell
$env:PYTHONPATH="D:\foraiproject\tools\ai"
python -m pytest "D:\foraiproject\tools\ai\tests\test_scanner.py" -q
```

期望：失败，原因是 scanner 尚不存在。

- [ ] **步骤 3：实现 scanner**

创建 `tools/ai/forai/scanner.py`：

```python
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def read_unity_version(project_root: Path) -> str:
    version_file = project_root / "ProjectSettings" / "ProjectVersion.txt"
    for line in version_file.read_text(encoding="utf-8-sig").splitlines():
        if line.startswith("m_EditorVersion:"):
            return line.split(":", 1)[1].strip()
    return ""


def read_packages(project_root: Path) -> list[dict[str, str]]:
    manifest = json.loads((project_root / "Packages" / "manifest.json").read_text(encoding="utf-8-sig"))
    dependencies = manifest.get("dependencies", {})
    return [
        {"name": name, "version": str(version)}
        for name, version in sorted(dependencies.items())
    ]


def scan_paths(project_root: Path) -> list[str]:
    candidates = [
        "AGENTS.md",
        "docs/ai/architecture.md",
        "docs/ai/project-map.md",
        "docs/ai/capability-registry.md",
        "docs/ai/risk-policy.md",
        "docs/ai/workflows.md",
        "Packages/manifest.json",
        "ProjectSettings/ProjectVersion.txt",
        "Packages/com.forai.roslyn-gateway/package.json",
        "tools/ai/schemas/context-pack.v1.schema.json",
        "tools/ai/schemas/execution-plan.v1.schema.json",
        "tools/ai/schemas/risk-review.v1.schema.json",
    ]
    return [path for path in candidates if (project_root / path).exists()]


def scan_context_pack(project_root: Path) -> dict[str, Any]:
    paths = scan_paths(project_root)
    return {
        "version": "context-pack/v1",
        "projectRoot": str(project_root),
        "unityVersion": read_unity_version(project_root),
        "packages": read_packages(project_root),
        "paths": paths,
        "summaries": [
            {"source": "ProjectSettings/ProjectVersion.txt", "summary": "Unity editor version source."},
            {"source": "Packages/manifest.json", "summary": "Unity Package Manager dependency source."},
            {"source": "tools/ai/schemas", "summary": "Machine-readable AI workflow contracts."},
            {"source": "Packages/com.forai.roslyn-gateway", "summary": "Unity Editor execution adapter package."},
        ],
    }
```

- [ ] **步骤 4：给 CLI 增加 `scan context` 命令**

在 `tools/ai/ai.py` 中加入：

```python
from forai.json_io import write_json
from forai.scanner import scan_context_pack


def handle_scan_context(args: argparse.Namespace) -> int:
    root = find_project_root(Path(args.project_root) if args.project_root else None)
    payload = scan_context_pack(root)
    if args.out:
        write_json(Path(args.out), payload)
    print_json(payload)
    return 0
```

在 `build_parser()` 中注册：

```python
    scan_parser = subparsers.add_parser("scan", help="Scan deterministic project context")
    scan_subparsers = scan_parser.add_subparsers(dest="scan_command", required=True)
    scan_context_parser = scan_subparsers.add_parser("context", help="Build context-pack/v1")
    scan_context_parser.add_argument("--project-root")
    scan_context_parser.add_argument("--out")
    scan_context_parser.set_defaults(handler=handle_scan_context)
```

- [ ] **步骤 5：运行测试和命令**

运行：

```powershell
$env:PYTHONPATH="D:\foraiproject\tools\ai"
python -m pytest "D:\foraiproject\tools\ai\tests\test_scanner.py" -q
python "D:\foraiproject\tools\ai\ai.py" scan context --project-root "D:\foraiproject" --out "D:\foraiproject\artifacts\ai-runs\manual\context-pack.json"
```

期望：测试通过，并写出 context artifact。

---

## 任务 5：加入确定性 Risk Review

**文件：**
- 新增：`tools/ai/forai/risk.py`
- 新增：`tools/ai/tests/test_risk.py`
- 新增：`tools/ai/examples/execution-plan.low-risk.json`
- 修改：`tools/ai/ai.py`

- [ ] **步骤 1：创建低风险示例计划**

创建 `tools/ai/examples/execution-plan.low-risk.json`：

```json
{
  "version": "execution-plan/v1",
  "runId": "example-low-risk",
  "steps": [
    {
      "id": "scan-context",
      "kind": "read_only",
      "description": "Scan project context",
      "target": "D:\\foraiproject",
      "requiresConfirmation": false
    }
  ]
}
```

- [ ] **步骤 2：先写风险评审测试**

创建 `tools/ai/tests/test_risk.py`：

```python
from forai.risk import review_execution_plan


def test_read_only_plan_is_low_risk():
    plan = {
        "version": "execution-plan/v1",
        "runId": "risk-low",
        "steps": [
            {
                "id": "read-docs",
                "kind": "read_only",
                "description": "Read docs",
                "target": "docs/ai/workflows.md",
                "requiresConfirmation": False,
            }
        ],
    }
    review = review_execution_plan(plan)
    assert review["overallRisk"] == "low"
    assert review["confirmationRequired"] is False


def test_unity_adapter_step_requires_confirmation():
    plan = {
        "version": "execution-plan/v1",
        "runId": "risk-medium",
        "steps": [
            {
                "id": "edit-prefab",
                "kind": "unity_adapter",
                "description": "Modify prefab",
                "target": "Assets/Prefabs/Hero.prefab",
                "requiresConfirmation": False,
            }
        ],
    }
    review = review_execution_plan(plan)
    assert review["overallRisk"] == "medium"
    assert review["confirmationRequired"] is True


def test_project_settings_change_is_high_risk():
    plan = {
        "version": "execution-plan/v1",
        "runId": "risk-high",
        "steps": [
            {
                "id": "edit-settings",
                "kind": "unity_adapter",
                "description": "Modify project settings",
                "target": "ProjectSettings/ProjectSettings.asset",
                "requiresConfirmation": False,
            }
        ],
    }
    review = review_execution_plan(plan)
    assert review["overallRisk"] == "high"
    assert review["confirmationRequired"] is True
```

- [ ] **步骤 3：运行测试并确认失败**

运行：

```powershell
$env:PYTHONPATH="D:\foraiproject\tools\ai"
python -m pytest "D:\foraiproject\tools\ai\tests\test_risk.py" -q
```

期望：失败，原因是 risk reviewer 尚不存在。

- [ ] **步骤 4：实现 risk reviewer**

创建 `tools/ai/forai/risk.py`：

```python
from __future__ import annotations

from typing import Any


RISK_ORDER = {"low": 0, "medium": 1, "high": 2, "blocked": 3}


def max_risk(left: str, right: str) -> str:
    return left if RISK_ORDER[left] >= RISK_ORDER[right] else right


def classify_step(step: dict[str, Any]) -> tuple[str, str]:
    kind = step.get("kind", "")
    target = str(step.get("target", "")).replace("\\", "/")
    description = str(step.get("description", ""))

    if ".." in target.split("/"):
        return "blocked", f"Step {step.get('id')} targets a parent-directory path."
    if target.startswith("ProjectSettings/") or target == "Packages/manifest.json":
        return "high", f"Step {step.get('id')} changes sensitive project configuration."
    if kind == "unity_adapter":
        return "medium", f"Step {step.get('id')} uses Unity Editor Adapter: {description}"
    if kind in {"cli", "validation"}:
        return "low", f"Step {step.get('id')} is deterministic CLI or validation work."
    if kind == "read_only":
        return "low", f"Step {step.get('id')} is read-only."
    return "medium", f"Step {step.get('id')} has unknown risk kind: {kind}"


def review_execution_plan(plan: dict[str, Any]) -> dict[str, Any]:
    overall = "low"
    findings = []
    confirmation_required = False

    for step in plan.get("steps", []):
        risk, message = classify_step(step)
        overall = max_risk(overall, risk)
        findings.append({"risk": risk, "message": message})
        if risk in {"medium", "high", "blocked"}:
            confirmation_required = True

    return {
        "version": "risk-review/v1",
        "runId": plan["runId"],
        "overallRisk": overall,
        "findings": findings,
        "confirmationRequired": confirmation_required,
    }
```

- [ ] **步骤 5：给 CLI 增加 `risk review` 命令**

在 `tools/ai/ai.py` 中加入：

```python
from forai.risk import review_execution_plan


def handle_risk_review(args: argparse.Namespace) -> int:
    root = find_project_root(Path(args.project_root) if args.project_root else None)
    plan = read_json(Path(args.plan))
    validate_payload(load_schema(root, "execution-plan/v1"), plan)
    review = review_execution_plan(plan)
    validate_payload(load_schema(root, "risk-review/v1"), review)
    if args.out:
        write_json(Path(args.out), review)
    print_json(review)
    return 2 if review["overallRisk"] == "blocked" else 0
```

在 `build_parser()` 中注册：

```python
    risk_parser = subparsers.add_parser("risk", help="Review deterministic execution risk")
    risk_subparsers = risk_parser.add_subparsers(dest="risk_command", required=True)
    risk_review_parser = risk_subparsers.add_parser("review", help="Review execution-plan/v1")
    risk_review_parser.add_argument("--plan", required=True)
    risk_review_parser.add_argument("--project-root")
    risk_review_parser.add_argument("--out")
    risk_review_parser.set_defaults(handler=handle_risk_review)
```

- [ ] **步骤 6：运行测试和命令**

运行：

```powershell
$env:PYTHONPATH="D:\foraiproject\tools\ai"
python -m pytest "D:\foraiproject\tools\ai\tests\test_risk.py" -q
python "D:\foraiproject\tools\ai\ai.py" risk review --plan "D:\foraiproject\tools\ai\examples\execution-plan.low-risk.json" --project-root "D:\foraiproject"
```

期望：测试通过，并输出合法的 `risk-review/v1`。

---

## 任务 6：加入 Artifact 工具

**文件：**
- 新增：`tools/ai/forai/artifacts.py`
- 新增：`tools/ai/tests/test_artifacts.py`

- [ ] **步骤 1：先写 artifact 测试**

创建 `tools/ai/tests/test_artifacts.py`：

```python
from forai.artifacts import artifact_dir, normalize_run_id
from forai.paths import find_project_root


def test_normalize_run_id_keeps_safe_characters():
    assert normalize_run_id("phase-3_manual.01") == "phase-3_manual.01"


def test_normalize_run_id_replaces_unsafe_characters():
    assert normalize_run_id("phase 3/compile") == "phase-3-compile"


def test_artifact_dir_points_under_project_artifacts():
    root = find_project_root()
    path = artifact_dir(root, "phase 3/compile")
    assert path == root / "artifacts" / "ai-runs" / "phase-3-compile"
```

- [ ] **步骤 2：运行测试并确认失败**

运行：

```powershell
$env:PYTHONPATH="D:\foraiproject\tools\ai"
python -m pytest "D:\foraiproject\tools\ai\tests\test_artifacts.py" -q
```

期望：失败，原因是 artifacts helper 尚不存在。

- [ ] **步骤 3：实现 artifact helper**

创建 `tools/ai/forai/artifacts.py`：

```python
from __future__ import annotations

import re
from pathlib import Path


def normalize_run_id(run_id: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9_.-]+", "-", run_id.strip())
    normalized = normalized.strip(".-")
    if not normalized:
        raise ValueError("run_id must contain at least one safe character.")
    return normalized


def artifact_dir(project_root: Path, run_id: str) -> Path:
    return project_root / "artifacts" / "ai-runs" / normalize_run_id(run_id)
```

- [ ] **步骤 4：运行测试**

运行：

```powershell
$env:PYTHONPATH="D:\foraiproject\tools\ai"
python -m pytest "D:\foraiproject\tools\ai\tests\test_artifacts.py" -q
```

期望：测试通过。

---

## 任务 7：加入 Unity Gateway 状态和编译命令

**文件：**
- 新增：`tools/ai/forai/unity_gateway.py`
- 修改：`tools/ai/ai.py`

- [ ] **步骤 1：实现 Gateway wrapper**

创建 `tools/ai/forai/unity_gateway.py`：

```python
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from forai.paths import gateway_python_dir


def run_gateway_client(project_root: Path, args: list[str], timeout_sec: int = 60) -> tuple[int, dict[str, Any]]:
    script = gateway_python_dir(project_root) / "ai_gateway_client.py"
    completed = subprocess.run(
        [sys.executable, str(script), *args],
        cwd=str(project_root),
        text=True,
        capture_output=True,
        timeout=timeout_sec,
        check=False,
    )
    output = completed.stdout.strip()
    payload = json.loads(output) if output else {}
    return completed.returncode, payload


def run_compile_check(project_root: Path, timeout_sec: int = 300) -> tuple[int, str, str]:
    script = gateway_python_dir(project_root) / "check_unity_compile.py"
    completed = subprocess.run(
        [sys.executable, str(script), "--project-root", str(project_root)],
        cwd=str(project_root),
        text=True,
        capture_output=True,
        timeout=timeout_sec,
        check=False,
    )
    return completed.returncode, completed.stdout, completed.stderr
```

- [ ] **步骤 2：给 CLI 增加 Unity 命令**

在 `tools/ai/ai.py` 中加入：

```python
from forai.unity_gateway import run_compile_check, run_gateway_client


def handle_unity_status(args: argparse.Namespace) -> int:
    root = find_project_root(Path(args.project_root) if args.project_root else None)
    code, payload = run_gateway_client(root, ["status", "--project-root", str(root)], timeout_sec=args.timeout)
    print_json(payload)
    return code


def handle_unity_compile(args: argparse.Namespace) -> int:
    root = find_project_root(Path(args.project_root) if args.project_root else None)
    code, stdout, stderr = run_compile_check(root, timeout_sec=args.timeout)
    print_json({
        "version": "validation-report/v1",
        "runId": args.run_id,
        "status": "passed" if code == 0 else "failed",
        "checks": [
            {
                "name": "unity-compile",
                "status": "passed" if code == 0 else "failed",
                "evidence": (stdout + "\n" + stderr).strip(),
            }
        ],
    })
    return code
```

在 `build_parser()` 中注册：

```python
    unity_parser = subparsers.add_parser("unity", help="Unity Editor Adapter bridge commands")
    unity_subparsers = unity_parser.add_subparsers(dest="unity_command", required=True)

    unity_status_parser = unity_subparsers.add_parser("status", help="Check Unity Gateway status")
    unity_status_parser.add_argument("--project-root")
    unity_status_parser.add_argument("--timeout", type=int, default=30)
    unity_status_parser.set_defaults(handler=handle_unity_status)

    unity_compile_parser = unity_subparsers.add_parser("compile", help="Run Unity compile validation")
    unity_compile_parser.add_argument("--project-root")
    unity_compile_parser.add_argument("--timeout", type=int, default=300)
    unity_compile_parser.add_argument("--run-id", default="manual-unity-compile")
    unity_compile_parser.set_defaults(handler=handle_unity_compile)
```

- [ ] **步骤 3：运行命令**

运行：

```powershell
$env:PYTHONPATH="D:\foraiproject\tools\ai"
python "D:\foraiproject\tools\ai\ai.py" unity status --project-root "D:\foraiproject"
python "D:\foraiproject\tools\ai\ai.py" unity compile --project-root "D:\foraiproject" --run-id "phase-3-compile-check"
```

期望：`unity status` 返回 Gateway 状态，`unity compile` 返回 `validation-report/v1`。

---

## 任务 8：更新文档入口

**文件：**
- 修改：`docs/ai/capability-registry.md`
- 修改：`docs/ai/workflows.md`
- 修改：`AGENTS.md`

- [ ] **步骤 1：更新能力注册表**

在 `docs/ai/capability-registry.md` 增加：

```markdown
## 确定性 AI CLI

- `python tools/ai/ai.py root`
- `python tools/ai/ai.py scan context --project-root "D:\foraiproject"`
- `python tools/ai/ai.py validate file --schema context-pack/v1 --input <path>`
- `python tools/ai/ai.py risk review --plan <execution-plan.json>`
- `python tools/ai/ai.py unity status --project-root "D:\foraiproject"`
- `python tools/ai/ai.py unity compile --project-root "D:\foraiproject"`
```

- [ ] **步骤 2：更新工作流文档**

在 `docs/ai/workflows.md` 增加：

```markdown
## 第 3 阶段确定性本地工作流

1. `python tools/ai/ai.py scan context --project-root "D:\foraiproject" --out artifacts/ai-runs/manual/context-pack.json`
2. `python tools/ai/ai.py validate file --schema context-pack/v1 --input artifacts/ai-runs/manual/context-pack.json`
3. 生成或提供 `execution-plan/v1`。
4. `python tools/ai/ai.py risk review --plan <execution-plan.json>`
5. 对仅验证类 Unity 工作，运行 `python tools/ai/ai.py unity compile --project-root "D:\foraiproject"`。
6. 对修改型 Unity 工作，先要求用户确认，再通过 Unity Editor Adapter 执行。
```

- [ ] **步骤 3：更新 Agent 规则**

在 `AGENTS.md` 增加：

```markdown
## 稳定工具入口

Agent 应优先使用 `python tools/ai/ai.py ...` 执行确定性项目操作。只有在调试 Gateway 本身时，才直接调用 `Packages/com.forai.roslyn-gateway/Python~` 下的脚本。
```

---

## 任务 9：最终验证

**文件：**
- 前面所有任务涉及的文件。

- [ ] **步骤 1：运行 Python 测试**

运行：

```powershell
$env:PYTHONPATH="D:\foraiproject\tools\ai"
python -m pytest "D:\foraiproject\tools\ai\tests" -q
```

期望：全部测试通过。

- [ ] **步骤 2：确认 schema 文件仍是有效 JSON**

运行：

```powershell
Get-ChildItem "D:\foraiproject\tools\ai\schemas" -Filter "*.json" | ForEach-Object {
  Get-Content $_.FullName -Raw | ConvertFrom-Json > $null
}
```

期望：无错误。

- [ ] **步骤 3：运行端到端确定性工作流**

运行：

```powershell
$env:PYTHONPATH="D:\foraiproject\tools\ai"
python "D:\foraiproject\tools\ai\ai.py" scan context --project-root "D:\foraiproject" --out "D:\foraiproject\artifacts\ai-runs\manual\context-pack.json"
python "D:\foraiproject\tools\ai\ai.py" validate file --schema context-pack/v1 --input "D:\foraiproject\artifacts\ai-runs\manual\context-pack.json" --project-root "D:\foraiproject"
python "D:\foraiproject\tools\ai\ai.py" risk review --plan "D:\foraiproject\tools\ai\examples\execution-plan.low-risk.json" --project-root "D:\foraiproject"
python "D:\foraiproject\tools\ai\ai.py" unity status --project-root "D:\foraiproject"
```

期望：context scan 通过 schema 校验，低风险评审通过，Unity status 能识别当前项目。

- [ ] **步骤 4：运行 Unity 编译验证**

运行：

```powershell
$env:PYTHONPATH="D:\foraiproject\tools\ai"
python "D:\foraiproject\tools\ai\ai.py" unity compile --project-root "D:\foraiproject" --run-id "phase-3-final"
```

期望：输出 `validation-report/v1`，且 `status` 为 `passed`。

---

## 第 3 阶段验收标准

- `tools/ai/ai.py` 成为已记录的稳定 CLI 入口。
- CLI 能生成 `context-pack/v1`。
- CLI 能用 `tools/ai/schemas` 校验 JSON 产物。
- CLI 能从 `execution-plan/v1` 生成 `risk-review/v1`。
- CLI 能调用 package-local Unity Gateway 做状态检查和编译验证。
- Python 测试通过。
- Unity Editor 重新加载迁移后的 package 后，Unity 编译验证通过。

## 第 4 阶段再做

- LLM prompt templates。
- 用 MCP server 包装 CLI。
- 修改型 Unity Adapter recipe，例如创建 prefab 或编辑 scene。
- 自动修复循环。
- 多 Agent 编排。

