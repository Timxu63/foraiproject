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
