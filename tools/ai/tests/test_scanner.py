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
