from forai.risk import review_execution_plan


def step(
    target: str,
    kind: str = "cli",
    description: str = "Run step",
    outputs: list[str] | None = None,
    dry_run_supported: bool = False,
) -> dict:
    return {
        "id": "step",
        "kind": kind,
        "description": description,
        "target": target,
        "command": "command",
        "inputs": {},
        "outputs": outputs or [],
        "dryRunSupported": dry_run_supported,
        "validation": [],
        "requiresConfirmation": False,
    }


def test_read_only_plan_is_low_risk():
    plan = {
        "version": "execution-plan/v1",
        "runId": "risk-low",
        "steps": [
            step("docs/ai/workflows.md", kind="read_only", dry_run_supported=True)
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
            step(
                "Assets/_Project/ScriptableObjects/Item.asset",
                kind="unity_adapter",
                description="Create a new ScriptableObject",
            )
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
            step("ProjectSettings/ProjectSettings.asset", kind="unity_adapter", description="Modify project settings")
        ],
    }
    review = review_execution_plan(plan)
    assert review["overallRisk"] == "high"
    assert review["confirmationRequired"] is True


def test_cli_direct_prefab_edit_is_blocked():
    plan = {
        "version": "execution-plan/v1",
        "runId": "risk-blocked-prefab",
        "steps": [
            step("Assets/_Project/Prefabs/Hero.prefab", kind="cli", description="Edit prefab YAML directly")
        ],
    }
    review = review_execution_plan(plan)
    assert review["overallRisk"] == "blocked"
    assert review["confirmationRequired"] is True


def test_parent_directory_target_is_blocked():
    plan = {
        "version": "execution-plan/v1",
        "runId": "risk-blocked-parent",
        "steps": [
            step("../outside.txt", kind="cli", description="Write outside workspace")
        ],
    }
    review = review_execution_plan(plan)
    assert review["overallRisk"] == "blocked"
    assert review["confirmationRequired"] is True


def test_package_manifest_change_is_high_risk_and_requires_preview():
    plan = {
        "version": "execution-plan/v1",
        "runId": "risk-manifest",
        "steps": [step("Packages/manifest.json", kind="cli", description="Modify package manifest")],
    }
    review = review_execution_plan(plan)
    assert review["overallRisk"] == "high"
    assert review["confirmationRequired"] is True
    assert review["previewRequired"] is True
    assert "dry-run-preview" in review["previewArtifacts"]


def test_unity_adapter_prefab_overwrite_is_high_risk():
    plan = {
        "version": "execution-plan/v1",
        "runId": "risk-prefab-overwrite",
        "steps": [
            step(
                "Assets/_Project/Prefabs/Hero.prefab",
                kind="unity_adapter",
                description="Overwrite existing prefab",
            )
        ],
    }
    review = review_execution_plan(plan)
    assert review["overallRisk"] == "high"
    assert review["confirmationRequired"] is True


def test_bulk_operation_is_high_risk():
    plan = {
        "version": "execution-plan/v1",
        "runId": "risk-bulk",
        "steps": [step("Assets/_Project", kind="unity_adapter", description="Bulk rename project assets")],
    }
    review = review_execution_plan(plan)
    assert review["overallRisk"] == "high"
    assert review["previewRequired"] is True
