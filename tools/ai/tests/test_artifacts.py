import pytest

from forai.artifacts import artifact_dir, normalize_run_id
from forai.paths import find_project_root


def test_normalize_run_id_keeps_safe_characters():
    assert normalize_run_id("phase-3_manual.01") == "phase-3_manual.01"


def test_normalize_run_id_replaces_unsafe_characters():
    assert normalize_run_id("phase 3/compile") == "phase-3-compile"


def test_normalize_run_id_rejects_empty_safe_result():
    with pytest.raises(ValueError):
        normalize_run_id("../")


def test_artifact_dir_points_under_project_artifacts():
    root = find_project_root()
    path = artifact_dir(root, "phase 3/compile")
    assert path == root / "artifacts" / "ai-runs" / "phase-3-compile"
