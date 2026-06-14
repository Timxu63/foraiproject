from forai.paths import find_project_root
from forai.schemas import load_schema, validate_payload


def test_unity_compile_failure_report_shape():
    root = find_project_root()
    payload = {
        "version": "validation-report/v1",
        "runId": "unity-offline-test",
        "status": "failed",
        "checks": [
            {
                "name": "unity-compile",
                "status": "failed",
                "evidence": "Gateway unavailable: Offline No Unity agent matches projectRoot",
            }
        ],
    }
    validate_payload(load_schema(root, "validation-report/v1"), payload)
